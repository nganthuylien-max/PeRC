"""Tính thép chịu uốn tiết diện chữ nhật – TCVN 5574:2018 mục 8.1.2.2.
Đơn vị vào: M (kN.m), kích thước (mm). Tính nội bộ: N, mm."""
import math

MU_MIN = 0.001   # hàm lượng thép tối thiểu 0.1%


def required_As(M_kNm, b, h, a, a_c, conc, steel):
    """Thép yêu cầu cho mômen M. a: tới trọng tâm thép kéo, a_c: tới trọng tâm thép nén."""
    M = abs(M_kNm) * 1e6                      # kN.m -> N.mm
    h0 = h - a
    Rb, Rs, Rsc = conc.Rb, steel.Rs, steel.Rsc
    aR, xR = steel.alpha_R, steel.xi_R
    if M == 0:
        return {"h0": h0, "alpha_m": 0.0, "xi": 0.0, "As": 0.0, "As_c": 0.0, "double": False}

    am = M / (Rb * b * h0 ** 2)
    if am <= aR:                              # cốt đơn
        xi = 1 - math.sqrt(1 - 2 * am)
        As = xi * Rb * b * h0 / Rs
        return {"h0": h0, "alpha_m": am, "xi": xi, "As": As, "As_c": 0.0, "double": False}

    # cốt kép
    As_c = (M - aR * Rb * b * h0 ** 2) / (Rsc * (h0 - a_c))
    As = (xR * Rb * b * h0 + Rsc * As_c) / Rs
    return {"h0": h0, "alpha_m": am, "xi": xR, "As": As, "As_c": As_c, "double": True}


def capacity(b, h, As, a, As_c, a_c, conc, steel):
    """Khả năng chịu mômen Mu (kN.m) của tiết diện đã bố trí thép."""
    h0 = h - a
    Rb, Rs, Rsc = conc.Rb, steel.Rs, steel.Rsc
    xR = steel.xi_R
    x = (Rs * As - Rsc * As_c) / (Rb * b)
    note = ""
    if x > xR * h0:
        x = xR * h0
        note = "x > ξR·h0 → lấy x = ξR·h0"

    if As_c > 0 and x < 2 * a_c:
        # thép nén làm việc không hết: lấy giá trị lớn hơn của 2 cách tính
        x1 = min(Rs * As / (Rb * b), xR * h0)
        Mu = max(Rb * b * x1 * (h0 - x1 / 2), Rs * As * (h0 - a_c))
        x = x1
        note = "x < 2a' → Mu = max(bỏ qua thép nén; Rs·As·(h0 − a'))"
    else:
        x = max(x, 0.0)
        Mu = Rb * b * x * (h0 - x / 2) + Rsc * As_c * (h0 - a_c)

    return {"h0": h0, "x": x, "xi": x / h0, "Mu": Mu / 1e6, "mu": As / (b * h0), "note": note}