"""Mô hình bản vẽ 2D độc lập định dạng: tọa độ mm thật, trục y hướng lên.
Một Drawing chứa các đối tượng đơn giản (đường, polyline, đường tròn, chữ, đường kích thước)
-> xuất ra SVG (xem trong app) và DXF (AutoCAD).
Kích thước chữ tính theo mm GIẤY × tỉ lệ S (1:10 -> chữ 2.5 mm giấy = 25 mm thật)."""
import math

# tên layer: (màu AutoCAD ACI, màu SVG)
LAYERS = {
    "BETONG": (7, "#1b1b1b"),
    "THEP": (1, "#d0021b"),
    "THEP_DAI": (3, "#1f8f3a"),
    "DIM": (4, "#1565c0"),
    "TAG": (2, "#8a5a00"),
    "TEXT": (7, "#1b1b1b"),
    "TITLE": (6, "#6a1b9a"),
}
BULGE_90 = math.tan(math.pi / 8)        # bulge của cung 90 độ


def story_vn(name):
    """'Story12' -> 'Tầng 12' (tên tầng tiếng Việt trên bản vẽ); tên khác giữ nguyên."""
    import re
    m = re.fullmatch(r"\s*story\s*(\d+)\s*", str(name), re.I)
    return f"Tầng {m.group(1)}" if m else str(name)


class Drawing:
    def __init__(self, scale=10.0):
        self.S = scale
        self.ents = []

    # ---------------------------------------------------------------- đối tượng cơ bản
    def line(self, x1, y1, x2, y2, layer="BETONG"):
        self.ents.append({"t": "line", "p": [(x1, y1), (x2, y2)], "layer": layer})

    def pline(self, pts, closed=False, layer="BETONG", bulges=None):
        self.ents.append({"t": "pline", "p": list(pts), "closed": closed, "layer": layer,
                          "b": list(bulges) if bulges else [0.0] * len(pts)})

    def rect(self, x, y, w, h, layer="BETONG"):
        self.pline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True, layer)

    def circle(self, cx, cy, r, layer="THEP", filled=False):
        self.ents.append({"t": "circle", "c": (cx, cy), "r": r, "layer": layer, "fill": filled})

    def text(self, x, y, s, h=2.5, layer="TEXT", ha="left", va="bottom", rot=0.0):
        """h = chiều cao chữ, mm giấy."""
        self.ents.append({"t": "text", "p": (x, y), "s": s, "h": h * self.S, "layer": layer,
                          "ha": ha, "va": va, "rot": rot})

    def dim(self, p1, p2, base, vertical=False, flip=False):
        """Đường kích thước giữa 2 điểm; base = 1 điểm nằm trên đường kích thước.
        flip=True: đặt chữ ở phía bên kia đường kích thước (tránh đè chữ khi đoạn quá ngắn)."""
        self.ents.append({"t": "dim", "p1": p1, "p2": p2, "base": base, "vertical": vertical,
                          "flip": flip, "S": self.S, "layer": "DIM"})

    def _short(self, span):
        """Đoạn kích thước quá ngắn so với chữ số của nó?"""
        return abs(span) < len(f"{abs(span):.0f}") * 2.2 * self.S * 0.62 + 1.5 * self.S

    # ---------------------------------------------------------------- tiện ích
    def dim_chain_h(self, xs, y_feat, y_dim):
        """Chuỗi kích thước ngang qua các điểm xs."""
        k = 0
        for a, b in zip(xs, xs[1:]):
            if abs(b - a) > 0.5:
                short = self._short(b - a)
                self.dim((a, y_feat), (b, y_feat), (a, y_dim), flip=short and k % 2 == 1)
                k = k + 1 if short else 0

    def dim_chain_v(self, ys, x_feat, x_dim):
        k = 0
        for a, b in zip(ys, ys[1:]):
            if abs(b - a) > 0.5:
                short = self._short(b - a)
                self.dim((x_feat, a), (x_feat, b), (x_dim, a), vertical=True, flip=short and k % 2 == 1)
                k = k + 1 if short else 0

    def bubble(self, x, y, mark):
        r = 2.6 * self.S
        self.circle(x, y, r, "TAG")
        self.text(x, y, str(mark), 2.5, "TAG", "center", "middle")
        return r

    def tag(self, x, y, mark, label, targets):
        """Bong bóng số hiệu + ghi chú, đường dẫn tới từng thanh. targets = [(x, y, r)]."""
        S = self.S
        r = self.bubble(x, y, mark)
        self.text(x + r + 1.2 * S, y, label, 2.5, "TAG", "left", "middle")
        for tx, ty, tr in targets:
            ang = math.atan2(ty - y, tx - x)
            self.line(x + r * math.cos(ang), y + r * math.sin(ang),
                      tx - tr * math.cos(ang), ty - tr * math.sin(ang), "TAG")
            self.circle(tx - tr * math.cos(ang), ty - tr * math.sin(ang), 0.45 * S, "TAG", True)

    def tag2(self, x, y, label, mark, targets, side="right"):
        """Ghi chú thép kiểu bản vẽ thi công: chữ nằm trên gạch ngang, số hiệu khoanh tròn ở cuối gạch.
        Đường dẫn GẤP KHÚC VUÔNG GÓC: từ thanh thép đi thẳng đứng tới cao độ gạch ngang rồi đi ngang tới gạch.
        (x, y) = đầu gạch phía thanh thép; side = phía đặt chữ."""
        S = self.S
        w = len(label) * 2.5 * S * 0.82 + 3 * S       # đủ chỗ cho chữ (font Arial) trước vòng tròn
        r = 2.4 * S
        sg = 1 if side == "right" else -1
        x_end = x + sg * w
        self.line(x, y, x_end, y, "TAG")
        self.text(x + sg * 1.0 * S, y + 0.6 * S, label, 2.5, "TAG", "left" if sg > 0 else "right", "bottom")
        if mark is not None:
            cx = x_end + sg * r
            self.circle(cx, y, r, "TAG")
            self.text(cx, y, str(mark), 2.5, "TAG", "center", "middle")
        for tx, ty, tr in targets:
            if (tx - x) * sg <= 1e-6:                       # thanh nằm phía trước gạch: đứng rồi ngang
                if abs(ty - y) > 1e-6:
                    self.line(tx, ty, tx, y, "TAG")
                if abs(tx - x) > 1e-6:
                    self.line(tx, y, x, y, "TAG")
            else:
                self.line(x, y, tx, ty, "TAG")

    def level(self, x, y, z_m, label=None, side=1, length=18):
        """Ký hiệu cao độ kiểu bản vẽ thi công: tam giác chỉ xuống mặt cao độ, gạch ngang,
        tên tầng phía trên gạch, cao độ (m) phía dưới gạch. (x, y) = điểm trên mặt cao độ."""
        S = self.S
        x2 = x + side * length * S
        tx = x + side * 3.0 * S
        self.pline([(tx, y), (tx - 1.4 * S, y + 2.4 * S), (tx + 1.4 * S, y + 2.4 * S)], True, "TEXT")
        self.line(x, y, x2, y, "TEXT")
        ha = "left" if side > 0 else "right"
        xt = x + side * 5.5 * S
        if label:
            self.text(xt, y + 0.6 * S, label, 2.5, "TEXT", ha, "bottom")
        self.text(xt, y - 0.6 * S, f"{z_m:+.3f}" if z_m else "±0.000", 2.5, "TEXT", ha, "top")

    def bubble_axis(self, x, y, name):
        """Bong bóng tên trục ở đầu đường trục (đường tròn đường kính 8 mm giấy)."""
        r = 4.0 * self.S
        self.circle(x, y - r, r, "TEXT")
        self.text(x, y - r, str(name), 3.5, "TEXT", "center", "middle")

    def cut_mark(self, x, y, no, vertical=True, text_side=1):
        """Ký hiệu vị trí mặt cắt kiểu bản vẽ thi công: vạch đậm ngắn + số mặt cắt.
        vertical=True: vạch đứng (cắt dầm); False: vạch ngang (cắt cột). (x, y) = tâm vạch."""
        S = self.S
        L, w = 4.0 * S, 0.9 * S
        n = 5
        for i in range(n):                                    # tô đậm bằng các nét sát nhau
            o = -w / 2 + i * w / (n - 1)
            if vertical:
                self.line(x + o, y - L / 2, x + o, y + L / 2, "TITLE")
            else:
                self.line(x - L / 2, y + o, x + L / 2, y + o, "TITLE")
        if vertical:
            self.text(x + text_side * 1.5 * S, y + L / 2, str(no), 3.0, "TITLE", "left" if text_side > 0 else "right", "top")
        else:
            self.text(x + text_side * (L / 2 + 1.0 * S), y, str(no), 3.0, "TITLE",
                      "left" if text_side > 0 else "right", "middle")

    def title(self, x, y, txt, sub=None):
        S = self.S
        self.text(x, y, txt, 4.0, "TITLE", "center", "bottom")
        w = len(txt) * 4.0 * S * 0.62
        self.line(x - w / 2, y - 1.2 * S, x + w / 2, y - 1.2 * S, "TITLE")
        self.line(x - w / 2, y - 1.8 * S, x + w / 2, y - 1.8 * S, "TITLE")
        if sub:
            self.text(x, y - 3.2 * S, sub, 2.5, "TEXT", "center", "top")

    def break_line(self, x1, y1, x2, y2, layer="BETONG"):
        """Nét cắt (đường gãy zig-zag "tia sét") từ (x1, y1) tới (x2, y2), thò ra 2 đầu mỗi bên 2 mm giấy."""
        S = self.S
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-6:
            return
        ux, uy = (x2 - x1) / L, (y2 - y1) / L            # phương đường cắt
        nx, ny = -uy, ux                                  # pháp tuyến
        ext, a, w = 2 * S, 2.2 * S, 1.2 * S               # thò ra, biên độ, nửa bề rộng răng
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        P = lambda t, n=0.0: (mx + ux * t + nx * n, my + uy * t + ny * n)
        self.pline([(x1 - ux * ext, y1 - uy * ext), P(-1.5 * w), P(-0.5 * w, a), P(0.5 * w, -a), P(1.5 * w),
                    (x2 + ux * ext, y2 + uy * ext)], False, layer)

    def bbox(self):
        xs, ys = [], []
        for e in self.ents:
            if e["t"] in ("line", "pline"):
                xs += [p[0] for p in e["p"]]
                ys += [p[1] for p in e["p"]]
            elif e["t"] == "circle":
                xs += [e["c"][0] - e["r"], e["c"][0] + e["r"]]
                ys += [e["c"][1] - e["r"], e["c"][1] + e["r"]]
            elif e["t"] == "text":
                w = len(e["s"]) * e["h"] * 0.72
                x, y = e["p"]
                x0 = x - (w if e["ha"] == "right" else w / 2 if e["ha"] == "center" else 0)
                xs += [x0, x0 + w]
                ys += [y - e["h"], y + e["h"] * 1.2]
            elif e["t"] == "dim":
                xs += [e["p1"][0], e["p2"][0], e["base"][0]]
                ys += [e["p1"][1], e["p2"][1], e["base"][1]]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 1, 1)

    def merge(self, other, dx=0.0, dy=0.0, k=1.0):
        """Chép bản vẽ khác vào: phóng k lần rồi dịch (dx, dy).
        Phóng hình (k > 1) để mặt cắt 1:10 đặt cạnh mặt cắt dọc 1:25 -> đường kích thước
        vẫn ghi số thật nhờ hệ số lfac = 1/k (giống biến DIMLFAC của AutoCAD)."""
        mv = lambda p: (p[0] * k + dx, p[1] * k + dy)
        for e in other.ents:
            e2 = dict(e)
            if e["t"] in ("line", "pline"):
                e2["p"] = [mv(p) for p in e["p"]]
            elif e["t"] == "circle":
                e2["c"], e2["r"] = mv(e["c"]), e["r"] * k
            elif e["t"] == "text":
                e2["p"], e2["h"] = mv(e["p"]), e["h"] * k
            elif e["t"] == "dim":
                e2["p1"], e2["p2"], e2["base"] = mv(e["p1"]), mv(e["p2"]), mv(e["base"])
                e2["S"] = e.get("S", other.S) * k
                e2["lfac"] = e.get("lfac", 1.0) / k
            self.ents.append(e2)


def rounded_rect(D, x0, y0, x1, y1, r, layer="THEP_DAI"):
    """Cốt đai: hình chữ nhật bo góc (đường tim thanh)."""
    pts = [(x0 + r, y0), (x1 - r, y0), (x1, y0 + r), (x1, y1 - r), (x1 - r, y1),
           (x0 + r, y1), (x0, y1 - r), (x0, y0 + r)]
    D.pline(pts, True, layer, [0, BULGE_90] * 4)


def hook135(D, x, y, dx, dy, length, layer="THEP_DAI"):
    """Móc 135 độ của cốt đai: 1 đoạn chéo vào lõi tiết diện."""
    D.line(x, y, x + dx * length, y + dy * length, layer)
