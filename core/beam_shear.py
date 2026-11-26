"""Tính cốt đai chịu cắt – TCVN 5574:2018 mục 8.1.3. Q (kN), kích thước (mm)."""
import math
from .materials import bar_area


def shear_check(Q_kN, b, h0, conc, steel_w, d_sw, legs, s):
    """Kiểm tra 1 bố trí đai: đường kính d_sw, số nhánh legs, bước s."""
    Q = abs(Q_kN) * 1e3                       # kN -> N
    Rb, Rbt = conc.Rb, conc.Rbt
    Asw = legs * bar_area(d_sw)
    qsw = steel_w.Rsw * Asw / s               # N/mm
    Q_strut = 0.3 * Rb * b * h0               # dải nén nghiêng
    use_sw = qsw >= 0.25 * Rbt * b            # đai đủ dày mới được kể

    worst = None
    c = h0
    while c <= 3 * h0 + 1e-6:                 # thử các tiết diện nghiêng, tìm cái yếu nhất
        Qb = 1.5 * Rbt * b * h0 ** 2 / c
        Qb = min(max(Qb, 0.5 * Rbt * b * h0), 2.5 * Rbt * b * h0)
        c0 = min(c, 2 * h0)
        Qsw = 0.75 * qsw * c0 if use_sw else 0.0
        if worst is None or Qb + Qsw < worst["Qu"]:
            worst = {"c": c, "Qb": Qb, "Qsw": Qsw, "Qu": Qb + Qsw}
        c += h0 / 20

    sw_max = Rbt * b * h0 ** 2 / Q if Q > 0 else 1e9
    util = max(Q / worst["Qu"], Q / Q_strut) if Q > 0 else 0.0
    return {"Q": abs(Q_kN), "qsw": qsw, "use_sw": use_sw,
            "Q_strut": Q_strut / 1e3, "c": worst["c"],
            "Qb": worst["Qb"] / 1e3, "Qsw": worst["Qsw"] / 1e3, "Qu": worst["Qu"] / 1e3,
            "sw_max": sw_max, "util": util,
            "ok": util <= 1.0 and s <= sw_max}


MARGIN = 0.97        # chọn đai chừa 3% dự phòng: h0 thực tế tính lại sau khi xếp thép có thể nhỏ hơn h0 giả thiết


def choose_stirrups(V_end, V_mid, b, h, h0, conc, steel_w, d_main):
    """Chọn đai dầm theo TCVN 5574:2018: đường kính nhỏ nhất, bước lớn nhất mà vẫn đạt cắt (8.1.3).
    - 10.3.4.2: đường kính ≥ 6 mm (≥ 8 mm với B70–B100).
    - 10.3.4.3: đoạn cần cốt đai chịu cắt (đầu dầm): bước ≤ 0,5h0 và ≤ 300 mm (250 với B70–B100);
      đoạn chỉ bê tông chịu cắt (giữa nhịp, h ≥ 150): bước ≤ 0,75h0 và ≤ 500 mm (400 với B70–B100).
    V_end: lực cắt lớn nhất ở 2 gối, V_mid: ở giữa nhịp (kN)."""
    hi = int(conc.grade[1:]) >= 70
    legs = 2 if b < 400 else 4
    d_min = 8 if hi else 6
    end_limit = min(0.5 * h0, 250 if hi else 300)
    mid_limit = min(0.75 * h0, 400 if hi else 500)
    for lim in (MARGIN, 1.0):                 # ưu tiên chừa dự phòng; không được thì chấp nhận hệ số ≤ 1
        for d in (6, 8, 10, 12, 14):
            if d < d_min:
                continue
            s_end = next((s for s in (300, 250, 200, 150, 100) if s <= end_limit
                          and shear_check(V_end, b, h0, conc, steel_w, d, legs, s)["util"] <= lim), None)
            if s_end is None:
                continue                          # đường kính này không đủ -> thử lớn hơn
            s_mid = next((s for s in (500, 450, 400, 350, 300, 250, 200, 150, 100) if s_end <= s <= mid_limit
                          and shear_check(V_mid, b, h0, conc, steel_w, d, legs, s)["util"] <= lim), s_end)
            return {"d": d, "legs": legs, "s_end": s_end, "s_mid": s_mid, "ok": True}
    return {"d": 14, "legs": legs, "s_end": 100, "s_mid": 100, "ok": False}