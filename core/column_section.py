"""Mặt tương tác N–M3–M2 cho cột chữ nhật – mô hình biến dạng (TCVN 5574:2018).
Hệ trục: z theo cạnh b (t2, nằm ngang), y theo cạnh h (t3, đứng). N > 0 là NÉN."""
import math
import numpy as np

from .materials import bar_area, ES, EPS_B2

EPS_B0 = 0.0020       # biến dạng khi nén đều
EPS_B1_RED = 0.0015   # điểm gãy của biểu đồ 2 đoạn thẳng


def bar_positions(b, h, cover, d_tie, d, nb, nh):
    """Thép đặt đều chu vi: nb thanh trên mỗi cạnh b, nh thanh trên mỗi cạnh h (kể cả góc)."""
    c = cover + d_tie + d / 2
    zs = np.linspace(-b / 2 + c, b / 2 - c, nb)
    ys = np.linspace(-h / 2 + c, h / 2 - c, nh)
    bars = []
    for z in zs:                                   # 2 cạnh trên, dưới
        bars += [{"z": float(z), "y": float(ys[-1]), "d": d}, {"z": float(z), "y": float(ys[0]), "d": d}]
    for y in ys[1:-1]:                             # 2 cạnh trái, phải (bỏ góc đã có)
        bars += [{"z": float(zs[0]), "y": float(y), "d": d}, {"z": float(zs[-1]), "y": float(y), "d": d}]
    return bars


class Section:
    def __init__(self, b, h, bars, conc, steel, n_fib=24):
        self.b, self.h, self.conc, self.steel = b, h, conc, steel
        # lưới thớ bê tông n_fib × n_fib
        dz, dy = b / n_fib, h / n_fib
        Z, Y = np.meshgrid(-b / 2 + dz * (np.arange(n_fib) + 0.5),
                           -h / 2 + dy * (np.arange(n_fib) + 0.5))
        self.cz, self.cy, self.cA = Z.ravel(), Y.ravel(), np.full(Z.size, dz * dy)
        # thép
        self.sz = np.array([t["z"] for t in bars])
        self.sy = np.array([t["y"] for t in bars])
        self.sA = np.array([bar_area(t["d"]) for t in bars])
        self.As = float(self.sA.sum())
        # 2 điểm đặc biệt: nén đúng tâm, kéo đúng tâm (kN)
        self.N0 = (conc.Rb * (b * h - self.As) + steel.Rsc * self.As) / 1e3
        self.Nt = -steel.Rs * self.As / 1e3
        self.corners = np.array([[-b / 2, -h / 2], [b / 2, -h / 2], [b / 2, h / 2], [-b / 2, h / 2]])
        self._curves = None

    def _sigma_c(self, eps):
        """Bê tông – biểu đồ 2 đoạn thẳng, không chịu kéo."""
        Rb = self.conc.Rb
        return np.where(eps <= 0, 0.0, np.minimum(Rb / EPS_B1_RED * eps, Rb))

    def _sigma_s(self, eps):
        """Thép đàn dẻo lý tưởng."""
        return np.clip(ES * eps, -self.steel.Rs, self.steel.Rsc)

    def curves(self, n_ang=36, n_x=40):
        """Với mỗi góc trục trung hòa -> 1 đường (N, M3, M2) sắp theo N tăng dần."""
        if self._curves is not None:
            return self._curves
        out = []
        for th in np.linspace(0, 2 * np.pi, n_ang, endpoint=False):
            u = np.array([math.sin(th), math.cos(th)])        # hướng về phía thớ nén
            dc = self.cz * u[0] + self.cy * u[1]               # khoảng cách theo hướng u
            ds = self.sz * u[0] + self.sy * u[1]
            dtop = (self.corners @ u).max()
            D = dtop - (self.corners @ u).min()                # chiều cao tiết diện theo hướng u
            xs = np.concatenate([D * np.geomspace(0.02, 1.0, n_x - 8),
                                 D * np.array([1.1, 1.25, 1.5, 2, 3, 5, 10, 1e3])])
            na = dtop - xs                                     # vị trí trục trung hòa
            # x <= D: thớ ngoài cùng đạt εb2; x > D: quay quanh điểm có ε = εb0
            k = np.where(xs <= D, EPS_B2 / xs, EPS_B0 / (xs - (1 - EPS_B0 / EPS_B2) * D))
            eps_c = k[:, None] * (dc[None, :] - na[:, None])   # ma trận: (số vị trí x) × (số thớ)
            eps_s = k[:, None] * (ds[None, :] - na[:, None])
            Fc = self._sigma_c(eps_c) * self.cA
            Fs = (self._sigma_s(eps_s) - self._sigma_c(eps_s)) * self.sA   # trừ phần bê tông bị thép chiếm chỗ
            N = (Fc.sum(1) + Fs.sum(1)) / 1e3
            M3 = (Fc @ self.cy + Fs @ self.sy) / 1e6
            M2 = (Fc @ self.cz + Fs @ self.sz) / 1e6
            pts = np.vstack([[self.Nt, 0, 0], np.column_stack([N, M3, M2]), [self.N0, 0, 0]])
            out.append(pts[np.argsort(pts[:, 0])])
        self._curves = out
        return out

    def contour(self, N):
        """Cắt mặt tương tác tại mức N -> đa giác (M3, M2)."""
        poly = []
        for cv in self.curves():
            if not cv[0, 0] <= N <= cv[-1, 0]:
                return None
            poly.append((np.interp(N, cv[:, 0], cv[:, 1]), np.interp(N, cv[:, 0], cv[:, 2])))
        return np.array(poly)

    def util(self, N, M3, M2):
        """Hệ số sử dụng tại (N, M3, M2). Trả về (hệ số, Mu theo hướng tải)."""
        if N >= self.N0:
            return N / self.N0, 0.0
        if N <= self.Nt:
            return N / self.Nt, 0.0
        poly = self.contour(N)
        M = math.hypot(M3, M2)
        if poly is None:
            return 9.99, 0.0
        if M < 1e-9:
            return (N / self.N0 if N > 0 else N / self.Nt), 0.0
        # bắn tia từ gốc theo hướng (M3, M2), tìm giao điểm gần nhất với các cạnh đa giác
        dvec = np.array([M3, M2]) / M
        P, E = poly, np.roll(poly, -1, axis=0) - poly
        det = -dvec[0] * E[:, 1] + dvec[1] * E[:, 0]
        with np.errstate(divide="ignore", invalid="ignore"):
            s = (-P[:, 0] * E[:, 1] + P[:, 1] * E[:, 0]) / det
            t = (dvec[0] * P[:, 1] - dvec[1] * P[:, 0]) / det
        hit = (np.abs(det) > 1e-12) & (s > 0) & (t >= -1e-9) & (t <= 1 + 1e-9)
        if not hit.any():
            return 9.99, 0.0
        Mu = float(s[hit].min())
        return M / Mu, Mu