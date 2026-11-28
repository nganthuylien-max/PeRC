"""Kiểm tra và thiết kế cột – TCVN 5574:2018.
- Độ lệch tâm ngẫu nhiên ea (4.2.6): ea = max(L/600, h/30, 10 mm); kết cấu siêu tĩnh e0 = max(M/N, ea)
- Uốn dọc (8.1.2.4): η = 1/(1 − N/Ncr), xét khi λ = l0/i > 14
- Hàm lượng tối thiểu (10.3.6): μmin 0.1% … 0.25% theo độ mảnh
Đơn vị: kN, kN.m, mm. Quy ước ETABS: P < 0 là nén."""
import math

from .materials import ES, bar_area
from .column_section import Section, bar_positions
from .beam_shear import shear_check

COL_DIAMS = [16, 18, 20, 22, 25, 28, 32]


def mu_min(lam):
    """10.3.6.1: 0.1% khi λ ≤ 17, 0.25% khi λ ≥ 87, nội suy ở giữa."""
    if lam <= 17:
        return 0.001
    if lam >= 87:
        return 0.0025
    return 0.001 + (lam - 17) / 70 * 0.0015


def eta(N, M, width, depth, l0, conc, Is, phi_L=2.0):
    """Hệ số uốn dọc cho 1 phương. depth = cạnh theo phương uốn, width = cạnh còn lại."""
    lam = l0 / (depth / math.sqrt(12))
    if lam <= 14 or N <= 0:
        return 1.0, lam, None
    I = width * depth ** 3 / 12
    de = min(max(abs(M) / N * 1e3 / depth, 0.15), 1.5)        # δe = e0/h, kẹp trong [0.15; 1.5]
    kb = 0.15 / (phi_L * (0.3 + de))
    D = kb * conc.Eb * I + 0.7 * ES * Is                     # độ cứng (N.mm2)
    Ncr = math.pi ** 2 * D / l0 ** 2 / 1e3                   # kN
    if N >= Ncr:
        return 99.0, lam, Ncr                                # mất ổn định
    return 1.0 / (1 - N / Ncr), lam, Ncr


def high_strength(conc):
    """Bê tông B70–B100: một số giới hạn cấu tạo chặt hơn (10.3.4)."""
    return int(conc.grade[1:]) >= 70


def crosstie_index(n_side, side_len, cover=30, dt=8, d=20):
    """Chỉ số (0..n_side-1) các thanh giữa cạnh cần 1 nhánh đai móc (đai phụ) – TCVN 5574:2018 10.3.4.5:
    các thanh dọc, ít nhất cách một thanh, nằm tại chỗ uốn của đai; các chỗ uốn cách nhau <= 400 mm.
    Ngoại lệ: mặt bên <= 400 mm và <= 4 thanh -> 1 đai ôm tất cả (không cần đai móc)."""
    if n_side <= 2 or (side_len <= 400 and n_side <= 4):
        return []
    sp = (side_len - 2 * (cover + dt + d / 2)) / (n_side - 1)     # khoảng cách tim các thanh
    k = 2 if 2 * sp <= 400 else 1                                 # nhảy cách 1 thanh nếu vẫn <= 400 mm
    out, i = [], 0
    while i + k < n_side - 1:                                     # đi từ góc này sang góc kia
        i += k
        out.append(i)
    return out


def crossties(n_side, side_len, cover=30, dt=8, d=20):
    """Số nhánh đai móc trên 1 cạnh (xem crosstie_index)."""
    return len(crosstie_index(n_side, side_len, cover, dt, d))


def check_column(col, sec, layout, conc, steel, steel_w, cover=30, psi=0.7, quick=None):
    b, h, L = sec["b"], sec["h"], col["L"]
    d, nb, nh, tie = layout["d"], layout["nb"], layout["nh"], layout["tie"]
    bars = bar_positions(b, h, cover, tie["d"], d, nb, nh)
    S = Section(b, h, bars, conc, steel)
    l0 = psi * L
    ea3, ea2 = max(L / 600, h / 30, 10), max(L / 600, b / 30, 10)
    Is3 = sum(bar_area(t["d"]) * t["y"] ** 2 for t in bars)
    Is2 = sum(bar_area(t["d"]) * t["z"] ** 2 for t in bars)

    def one(i):
        f = col["forces"][i]
        N, M3, M2 = -f["P"], f["M3"], f["M2"]
        if N > 0:                                            # nén: M không nhỏ hơn N·ea
            M3 = math.copysign(max(abs(M3), N * ea3 / 1e3), M3 or 1)
            M2 = math.copysign(max(abs(M2), N * ea2 / 1e3), M2 or 1)
        e3, lam3, _ = eta(N, M3, b, h, l0, conc, Is3)
        e2, lam2, _ = eta(N, M2, h, b, l0, conc, Is2)
        u, Mu = (9.99, 0.0) if max(e3, e2) >= 99 else S.util(N, M3 * e3, M2 * e2)
        return {"i": i, "combo": f["combo"], "station": f["station"], "N": N, "M3": f["M3"], "M2": f["M2"],
                "M3d": M3 * e3, "M2d": M2 * e2, "eta3": e3, "eta2": e2, "util": u, "Mu": Mu}

    if quick:                                               # thử nhanh các tổ hợp từng nguy hiểm trước
        for i in quick:
            r = one(i)
            if r["util"] > 1:
                return {"ok": False, "util": r["util"], "early": True, "worst": r}

    rows = [one(i) for i in range(len(col["forces"]))]
    worst = max(rows, key=lambda r: r["util"])
    lam = max(l0 / (h / math.sqrt(12)), l0 / (b / math.sqrt(12)))
    mu = S.As / (b * h)
    mumin = mu_min(lam)

    # cắt: mỗi phương 1 kiểm tra, bỏ qua lợi ích của lực nén (thiên an toàn)
    V2 = max(abs(f["V2"]) for f in col["forces"])
    V3 = max(abs(f["V3"]) for f in col["forces"])
    dt = tie["d"]
    sh2 = shear_check(V2, b, h - cover - dt - d / 2, conc, steel_w, dt, 2 + crossties(nb, b, cover, dt, d), tie["s_mid"])
    sh3 = shear_check(V3, h, b - cover - dt - d / 2, conc, steel_w, dt, 2 + crossties(nh, h, cover, dt, d), tie["s_mid"])

    warnings = []
    if mu < mumin:
        warnings.append(f"μ = {mu*100:.2f}% < μmin = {mumin*100:.2f}%")
    if mu > 0.04:
        warnings.append(f"μ = {mu*100:.2f}% > 4% – nên tăng tiết diện")
    util = max(worst["util"], sh2["util"], sh3["util"])
    ok = util <= 1 and mu >= mumin
    if not ok and worst["util"] > 1:
        warnings.append(f"Không đủ chịu N–M ở tổ hợp {worst['combo']} (hệ số {worst['util']:.2f})")
    return {"ok": ok, "util": util, "util_NM": worst["util"], "worst": worst, "As": S.As, "mu": mu,
            "mu_min": mumin, "lambda": lam, "l0": l0, "ea3": ea3, "ea2": ea2, "N0": S.N0,
            "n_bars": len(bars), "shear2": sh2, "shear3": sh3, "warnings": warnings}


def tie_for(d, b, h, nb, nh, conc, steel, steel_w, cover=30):
    """Cốt đai cột theo TCVN 5574:2018.
    - 10.3.4.2: đường kính ≥ 0,25·d dọc lớn nhất và ≥ 6 mm (≥ 8 mm với B70–B100).
    - 10.3.4.4: bước ≤ 15d và ≤ 500 mm (400 với B70–B100); nếu cốt thép dọc chịu nén trên 1 mặt bên > 1,5%
      thì bước ≤ 10d và ≤ 300 mm.
    - 10.3.6.2: trong vùng nối chồng, tổng nội lực các nhánh đai ≥ 1/2 nội lực cốt thép được nối
      (xét thép trên 1 mặt bên, nhánh đai vuông góc với mặt đó).
    TCVN 5574 không quy định vùng đai dày ở đầu cột (đó là yêu cầu kháng chấn TCVN 9386) -> s_end = s_mid,
    chỉ giảm khi tính cắt không đạt."""
    hi = high_strength(conc)
    A = bar_area(d)
    lap = math.ceil(max(40 * d, 500) / 50) * 50
    dt_min = max(8 if hi else 6, 0.25 * d)
    best = None
    cands = [x for x in (6, 8, 10) if x >= dt_min] or [next(x for x in (12, 14, 16) if x >= dt_min)]
    for dt in cands:                          # tối đa Ø10 (thực tế); không đủ thì giảm bước trong vùng nối
        a = cover + dt + d / 2
        ratio = max(nb * A / (b * (h - a)), nh * A / (h * (b - a)))   # cốt thép 1 mặt bên / (b·h0)
        s_max = min(10 * d, 300) if ratio > 0.015 else min(15 * d, 400 if hi else 500)
        s = int(s_max // 50 * 50)
        n_need = 0
        for n_face, width in ((nb, b), (nh, h)):                  # 10.3.6.2 cho từng mặt bên
            legs = 2 + crossties(n_face, width, cover, dt, d)
            n_need = max(n_need, math.ceil(0.5 * n_face * A * steel.Rs / (legs * bar_area(dt) * steel_w.Rsw)))
        s_lap = max(50, min(s, int(lap / max(n_need, 1) // 10 * 10)))
        best = {"d": dt, "s_end": s, "s_mid": s, "s_lap": s_lap, "lap": lap,
                "rule": "15d" if ratio <= 0.015 else "10d (thép 1 mặt > 1,5%)"}
        if s_lap >= 100:                      # tăng đường kính đai tới khi bước trong vùng nối ≥ 100 (thi công được)
            break
    return best


def candidate_layouts(b, h, cover=30, min_clear=50, max_spacing=400):
    """Mọi cách bố trí hợp lệ, sắp theo "chi phí": diện tích thép, phạt nhẹ khi nhiều thanh."""
    out = []
    for d in COL_DIAMS:
        c = cover + 8 + d / 2
        for nb in range(2, 12):
            for nh in range(2, 12):
                sb, sh = (b - 2 * c) / (nb - 1), (h - 2 * c) / (nh - 1)
                if min(sb, sh) - d < min_clear or max(sb, sh) > max_spacing:
                    continue
                if b == h and nb != nh:                    # tiết diện vuông -> bố trí đối xứng 2 phương
                    continue
                n = 2 * nb + 2 * (nh - 2)
                As = n * bar_area(d)
                out.append((As * (1 + 0.006 * n), As, d, nb, nh))
    return [t[1:] for t in sorted(out)]


def design_column(col, sec, conc, steel, steel_w, cover=30, psi=0.7):
    """Tìm phương án ít thép nhất mà đạt, bằng TÌM KIẾM NHỊ PHÂN trên danh sách đã sắp xếp."""
    b, h, L = sec["b"], sec["h"], col["L"]
    lam = max(psi * L / (h / math.sqrt(12)), psi * L / (b / math.sqrt(12)))
    As_min = mu_min(lam) * b * h
    N_max = max(-f["P"] for f in col["forces"])            # lực nén lớn nhất (kN)
    cands = [c for c in candidate_layouts(b, h, cover)
             if c[0] >= As_min and (conc.Rb * (b * h - c[0]) + steel.Rsc * c[0]) / 1e3 >= N_max]
    crit = []

    def test(i):
        As, d, nb, nh = cands[i]
        layout = {"d": d, "nb": nb, "nh": nh, "tie": tie_for(d, b, h, nb, nh, conc, steel, steel_w, cover)}
        r = check_column(col, sec, layout, conc, steel, steel_w, cover, psi, quick=crit)
        if r.get("early"):                                 # trượt ngay ở tổ hợp từng nguy hiểm
            return layout, r
        if r["util_NM"] > 1:
            crit.append(r["worst"]["i"])                   # nhớ tổ hợp nguy hiểm để loại nhanh lần sau
        if not r["ok"] and r["util_NM"] <= 1:              # N–M đạt, chỉ thiếu cắt -> dày đai cả cột
            s0 = layout["tie"]["s_mid"]
            for s_new in [x for x in (250, 200, 150, 100, 75, 50) if x < s0]:
                t2 = dict(layout["tie"], s_end=s_new, s_mid=s_new, s_lap=min(layout["tie"]["s_lap"], s_new))
                lay2 = dict(layout, tie=t2)
                r2 = check_column(col, sec, lay2, conc, steel, steel_w, cover, psi)
                if r2["ok"]:
                    return lay2, r2
        return layout, r

    if not cands:                                          # không phương án nào đủ N0 -> báo bằng phương án lớn nhất
        As, d, nb, nh = candidate_layouts(b, h, cover)[-1]
        layout = {"d": d, "nb": nb, "nh": nh, "tie": tie_for(d, b, h, nb, nh, conc, steel, steel_w, cover)}
        return {"layout": layout, **check_column(col, sec, layout, conc, steel, steel_w, cover, psi)}

    best = test(len(cands) - 1)                            # phương án nhiều thép nhất
    if not best[1]["ok"]:
        if best[1].get("early"):                           # lấy đủ thông tin để báo cáo
            best = (best[0], check_column(col, sec, best[0], conc, steel, steel_w, cover, psi))
        return {"layout": best[0], **best[1]}
    lo, hi = 0, len(cands) - 1                             # cands[hi] chắc chắn đạt
    while lo < hi:
        mid = (lo + hi) // 2
        lay, r = test(mid)
        if r["ok"]:
            hi, best = mid, (lay, r)
        else:
            lo = mid + 1
    return {"layout": best[0], **best[1]}


def _valid(b, h, d, nb, nh, cover=30, min_clear=50, max_spacing=400):
    c = cover + 8 + d / 2
    sb, sh = (b - 2 * c) / (nb - 1), (h - 2 * c) / (nh - 1)
    return min(sb, sh) - d >= min_clear and max(sb, sh) <= max_spacing


def _try(col, sec, layout, conc, steel, steel_w, cover, psi):
    """Kiểm tra 1 bố trí; nếu chỉ thiếu khả năng chịu cắt thì giảm bước đai."""
    r = check_column(col, sec, layout, conc, steel, steel_w, cover, psi)
    if not r["ok"] and r["util_NM"] <= 1:
        for s_new in [x for x in (250, 200, 150, 100, 75, 50) if x < layout["tie"]["s_mid"]]:
            t2 = dict(layout["tie"], s_end=s_new, s_mid=s_new, s_lap=min(layout["tie"]["s_lap"], s_new))
            r2 = check_column(col, sec, dict(layout, tie=t2), conc, steel, steel_w, cover, psi)
            if r2["ok"]:
                return dict(layout, tie=t2), r2
    return layout, r


def unify_stack(results, project, concrete_of, steel, steel_w, cover=30, psi=0.7):
    """Đồng bộ bố trí thép theo trục cột: các tầng liền nhau cùng tiết diện dùng CHUNG số thanh mỗi cạnh
    (nb x nh) để thép tầng trên thẳng hàng với thép tầng dưới khi nối chồng; mỗi tầng chỉ đổi đường kính.
    Bố trí chung = bố trí của tầng cần nhiều thép nhất; mỗi tầng chọn đường kính nhỏ nhất vẫn đạt.
    Trả về số tầng-cột đã đổi."""
    order = {s["name"]: i for i, s in enumerate(project.get("stories", []))}
    cols = {c["id"]: c for c in project["columns"]}
    groups = {}
    for i, r in enumerate(results):
        groups.setdefault(r["label"], []).append(i)
    changed = 0
    for label, idx in groups.items():
        idx.sort(key=lambda i: order.get(results[i]["story"], 0))
        runs, cur = [], [idx[0]]                                  # các đoạn tầng liền nhau cùng tiết diện
        for i in idx[1:]:
            if results[i]["section"] == results[cur[-1]]["section"]:
                cur.append(i)
            else:
                runs.append(cur)
                cur = [i]
        runs.append(cur)
        for run in runs:
            if len(run) < 2:
                continue
            ref = max(run, key=lambda i: results[i]["As"])
            nb, nh = results[ref]["layout"]["nb"], results[ref]["layout"]["nh"]
            for i in run:
                r = results[i]
                if (r["layout"]["nb"], r["layout"]["nh"]) == (nb, nh):
                    continue
                col = cols[r["id"]]
                sec = project["frame_sections"][r["section"]]
                b, h = sec["b"], sec["h"]
                conc = concrete_of(sec["material"])
                for d in COL_DIAMS:
                    if not _valid(b, h, d, nb, nh, cover):
                        continue
                    lay = {"d": d, "nb": nb, "nh": nh, "tie": tie_for(d, b, h, nb, nh, conc, steel, steel_w, cover)}
                    lay, chk = _try(col, sec, lay, conc, steel, steel_w, cover, psi)
                    if chk["ok"]:
                        results[i] = {k: r[k] for k in ("id", "label", "story", "section", "L")}
                        results[i].update(layout=lay, **chk)
                        changed += 1
                        break
    return changed
