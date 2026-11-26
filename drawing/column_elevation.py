"""Mặt cắt dọc 1 trục cột qua mọi tầng + mặt cắt ngang từng đoạn + mặt cắt tại vùng nối khi đổi tiết diện.

Quy tắc cấu tạo dùng ở đây (đều là hằng số, sửa được):
- Nối chồng thép dọc ngay trên mặt sàn, chiều dài nối l_lap = max(40·d_max, 500), làm tròn 50 mm.
- Ở nút, thép tầng dưới bẻ xiên độ dốc 1:6 vào trong để nằm cạnh thép tầng trên
  (độ dịch = phần thu tiết diện mỗi bên + 1 đường kính). Nếu độ dịch > 75 mm hoặc đoạn bẻ (6 × độ dịch)
  dài hơn chiều cao dầm thì không bẻ: thép dưới dừng ở đỉnh nút có móc vào trong,
  thép tầng trên cắm xuống nút (thép chờ) một đoạn neo 40d.
- Cốt đai theo TCVN 5574:2018 (core/column_design.tie_for): bước đều ≤ 15d (10d khi thép 1 mặt > 1,5%),
  trong vùng nối chồng dày hơn (s_lap, 10.3.6.2). Kết quả thiết kế cũ có s_end < s_mid thì vẫn vẽ vùng đai dày
  ở 2 đầu cột trong đoạn l_end = max(b, h, Hc/6, 500).
- Chân cột tầng 1 neo xuống móng 40d, có móc 12d.
- Nút tầng trên cùng (TCVN 5574:2018 mục 10.4.11): ở mặt cột không có dầm (nút biên/góc khung),
  thép cột uốn 90° qua nút và neo vào dầm đủ 40d tính từ đáy dầm; mặt có dầm thì móc 12d vào trong;
  đặt cốt đai tăng cường trong vùng neo (cả chiều cao nút).
- Mặt phẳng vẽ: trục X toàn cục; dầm chỉ vẽ ở phía có dầm gối vào cột.
"""
import math

from core.column_section import bar_positions
from .model import Drawing

COVER = 30
LAP = 40            # nối chồng 40d
ANCHOR = 40         # neo 40d
HOOK = 12           # móc 12d
MAX_CRANK = 75      # độ dịch lớn nhất cho phép bẻ xiên (mm)
STUB = 600          # đoạn dầm vẽ ra 2 bên nút
TOP_STUB = 300      # mỗi bản vẽ chỉ 1 tầng: phía trên chừa 300 mm trên mặt sàn rồi cắt
LOW_STUB = 150      # phía dưới cắt dưới đáy dầm tầng dưới 150 mm


def draw_node(D, z, b_low, b_up, hb, t, side):
    """Nút cột – dầm ở cao độ mặt sàn z (giống cách vẽ gối ở mặt cắt dọc dầm):
    mặt cột chạy liên tục (vẽ riêng), dầm + sàn là đoạn cụt 2 bên dừng ở mặt cột, đầu ngoài có nét cắt.
    b_low: bề rộng cột dưới nút, b_up: cột trên nút (None = mái)."""
    for sg in (-1, 1):
        xf = sg * b_low / 2                                  # mặt cột dưới
        xu = sg * (b_up / 2 if b_up else 0)                  # mặt cột trên (mái: tới tim)
        if side[sg]:
            xe = sg * (b_low / 2 + STUB)                     # đầu đoạn dầm
            D.line(xf, z - hb, xe, z - hb)                   # đáy dầm
            D.line(xe, z, xu, z)                             # mặt sàn tới mặt cột trên
            if t and t < hb:
                D.line(xf, z - t, xe, z - t, "TEXT")         # đáy sàn (nét mảnh)
            D.break_line(xe, z - hb, xe, z)                  # ký hiệu cắt dầm
        elif xu != xf:
            D.line(xf, z, xu, z)                             # bậc thu tiết diện / đỉnh cột mái


def ceil50(x):
    return math.ceil(x / 50) * 50


def column_stack(project, cols_res, label):
    """Các đoạn cột cùng tên, xếp từ dưới lên, kèm chiều cao dầm lớn nhất và chiều dày sàn ở đỉnh mỗi đoạn."""
    from quantity.takeoff import slab_thickness_by_story
    elev = {s["name"]: s["elevation"] for s in project["stories"]}
    z_prev = {}
    last = 0.0
    for s in project["stories"]:                         # stories xếp từ dưới lên
        z_prev[s["name"]] = last
        last = s["elevation"]
    geo = {c["id"]: c for c in project["columns"]}
    secs = project["frame_sections"]
    t_slab = slab_thickness_by_story(project)

    segs = []
    for r in cols_res:
        if r["label"] != label:
            continue
        g = geo[r["id"]]
        sec = secs[r["section"]]
        cx, cy = g["i"][0], g["i"][1]
        hb = 0.0                                          # dầm lớn nhất gối vào cột ở đỉnh đoạn này
        side = {-1: False, 1: False}                      # có dầm phương X ở bên trái / bên phải
        for bm in project["beams"]:
            if bm["story"] != r["story"]:
                continue
            for pt, other in ((bm["i"], bm["j"]), (bm["j"], bm["i"])):
                if abs(pt[0] - cx) <= sec["b"] / 2 + 1 and abs(pt[1] - cy) <= sec["h"] / 2 + 1:
                    hb = max(hb, secs[bm["section"]]["h"])
                    if abs(other[1] - pt[1]) < 1 and abs(other[0] - cx) > 1:      # dầm theo phương X
                        side[1 if other[0] > cx else -1] = True
        t = t_slab.get(r["story"], 0.0)
        segs.append({"res": r, "sec": sec, "z0": z_prev[r["story"]], "z1": elev[r["story"]],
                     "hb": hb or t or 200.0, "t": t, "side": side})
    segs.sort(key=lambda s: s["z0"])
    return segs


def _same(a, b):
    la, lb = a["res"]["layout"], b["res"]["layout"]
    return (a["res"]["section"], la["d"], la["nb"], la["nh"], la["tie"]) == \
           (b["res"]["section"], lb["d"], lb["nb"], lb["nh"], lb["tie"])


def group_segments(segs):
    """Gộp các tầng liền nhau giống hệt tiết diện + bố trí thép -> 1 mặt cắt ngang."""
    groups = []
    for s in segs:
        if groups and _same(groups[-1][-1], s):
            groups[-1].append(s)
        else:
            groups.append([s])
    return groups


def joints(segs):
    """Thông tin mỗi nút giữa đoạn i và i+1."""
    out = []
    for lo, up in zip(segs, segs[1:]):
        dl, du = lo["res"]["layout"]["d"], up["res"]["layout"]["d"]
        e = (lo["sec"]["b"] - up["sec"]["b"]) / 2          # thu tiết diện mỗi bên
        shift = e + (dl + du) / 2                          # thép dưới dịch vào để nằm cạnh thép trên
        crank = e <= MAX_CRANK and 6 * shift <= lo["hb"]
        out.append({"lap": ceil50(max(LAP * max(dl, du), 500)), "e": e, "shift": shift, "crank": crank,
                    "dowel": 0 if crank else ceil50(ANCHOR * du)})
    return out


def column_elevation(project, cols_res, label, scale=50, sec_scale=20, story_from=None, story_to=None):
    """story_from / story_to: chỉ vẽ một khoảng tầng (tên tầng), mặc định cả trục cột."""
    full = column_stack(project, cols_res, label)
    if not full:
        raise ValueError(f"Không có cột {label}")
    JF = joints(full)                                      # nút tính trên cả trục cột
    names = [s["res"]["story"] for s in full]
    i0 = names.index(story_from) if story_from in names else 0
    i1 = names.index(story_to) if story_to in names else len(full) - 1
    i0, i1 = min(i0, i1), max(i0, i1)
    segs = full[i0:i1 + 1]
    S = scale
    D = Drawing(S)
    J = JF[i0:i1]                                          # các nút bên trong khoảng vẽ
    all_groups = group_segments(full)                      # đánh số mặt cắt theo cả trục cột
    gid = {}
    for k, g in enumerate(all_groups, 1):
        for s in g:
            gid[s["res"]["id"]] = k
    ids = {s["res"]["id"] for s in segs}
    groups = [g for g in all_groups if any(s["res"]["id"] in ids for s in g)]
    bmax = max(s["sec"]["b"] for s in segs)
    xl = -bmax / 2 - STUB                                  # mép trái vùng vẽ bê tông
    xr = bmax / 2 + STUB

    for i, s in enumerate(segs):
        r, sec, z0, z1, hb, t = s["res"], s["sec"], s["z0"], s["z1"], s["hb"], s["t"]
        b = sec["b"]
        lay = r["layout"]
        d, dt, tie = lay["d"], lay["tie"]["d"], lay["tie"]
        a = COVER + dt + d / 2                             # tim thép dọc tới mép cột
        gi = i0 + i                                        # chỉ số trong cả trục cột
        top = gi == len(full) - 1                          # tầng trên cùng của cột (nút mái)
        base = gi == 0                                     # tầng dưới cùng (chân cột, neo móng)
        jb = JF[gi - 1] if gi else None                    # nút dưới
        jt = None if top else JF[gi]                       # nút trên

        # ---- bê tông: 2 mặt cột + dải dầm/sàn ở đỉnh đoạn
        side = s["side"]
        for sg in (-1, 1):                                                       # mặt cột liên tục qua nút
            D.line(sg * b / 2, z0, sg * b / 2, z1)
        b_up = None if top else full[gi + 1]["sec"]["b"]
        draw_node(D, z1, b, b_up, hb, t, side)
        if base:                                                                 # mặt móng
            D.line(xl, z0, xr, z0)
            D.text(xr, z0 - 1.5 * S, "MẶT MÓNG / ĐÀI", 2.2, "TEXT", "right", "top")

        # ---- nút dưới khi vẽ riêng tầng này: đoạn cột + dầm tầng dưới, thép tầng dưới đi lên nối chồng
        if i == 0 and gi > 0:
            lo = full[gi - 1]
            bl, hbl, tl = lo["sec"]["b"], lo["hb"], lo["t"]
            dl = lo["res"]["layout"]["d"]
            al = COVER + lo["res"]["layout"]["tie"]["d"] + dl / 2
            yb = z0 - hbl - LOW_STUB                                # cắt đoạn cột dưới
            for sg in (-1, 1):
                D.line(sg * bl / 2, yb, sg * bl / 2, z0)                           # mặt cột tầng dưới
            draw_node(D, z0, bl, b, hbl, tl, lo["side"])
            D.break_line(-bl / 2, yb, bl / 2, yb)                                  # ký hiệu cắt cột dưới
            for sg in (-1, 1):
                x = sg * (bl / 2 - al)
                if jb["crank"]:
                    xe = x - sg * jb["shift"]
                    pts = [(x, yb), (x, z0 - 6 * jb["shift"]), (xe, z0), (xe, z0 + jb["lap"])]
                else:
                    yt = z0 - COVER - dl / 2
                    pts = [(x, yb), (x, yt), (x - sg * HOOK * dl, yt)]
                D.pline(pts, False, "THEP")
            c0 = COVER + lo["res"]["layout"]["tie"]["d"] / 2
            y = yb + 50
            while y < z0 - 50:                                     # đai trong nút dưới
                D.line(-bl / 2 + c0, y, bl / 2 - c0, y, "THEP_DAI")
                y += lo["res"]["layout"]["tie"]["s_end"]
            n_lo = lo["res"].get("n_bars", 0)
            D.text(-bl / 2 - 2 * S, z0 - hbl / 2, f"{lo['res']['story']}: {n_lo}Ø{dl}", 2.2, "THEP", "right", "middle")
            D.text(xl, z0 + 0.8 * S, f"{lo['res']['story']}  +{z0 / 1000:.3f}", 2.2, "TEXT", "left", "bottom")
            D.dim((xl, z0), (xl, z0 + jb["lap"]), (xl - 16 * S, z0), vertical=True)
            D.text(xl - 22 * S, z0 + jb["lap"] / 2, f"Nối chồng {jb['lap']}" +
                   (f", bẻ xiên 1:6 ({jb['shift']:.0f})" if jb["crank"] else f", thép chờ neo {jb['dowel']}"),
                   2.2, "THEP", "right", "middle")

        # ---- thép dọc (vẽ 2 thanh ở 2 mặt cột)
        for sg in (-1, 1):
            x = sg * (b / 2 - a)
            pts = []
            if base:                                       # neo xuống móng + móc ra ngoài
                yb = z0 - ANCHOR * d
                pts += [(x + sg * HOOK * d, yb), (x, yb)]
            elif not jb["crank"]:                          # thép chờ cắm xuống nút dưới
                pts.append((x, z0 - jb["dowel"]))
            else:
                pts.append((x, z0))
            if top:                                        # nút trên cùng (10.4.11)
                yt = z1 - COVER - d / 2
                if not side[sg] and side[-sg]:             # mặt ngoài nút biên: uốn qua nút, neo vào dầm
                    leg = max(ANCHOR * d - (yt - (z1 - hb)), HOOK * d) + (b - 2 * a)
                    pts += [(x, yt), (x - sg * leg, yt)]
                else:
                    pts += [(x, yt), (x - sg * HOOK * d, yt)]
            elif jt["crank"]:                              # bẻ xiên 1:6 rồi nối chồng lên tầng trên
                xe = x - sg * jt["shift"]
                y_end = z1 + jt["lap"]
                if i == len(segs) - 1:                         # bản vẽ dừng ở sàn trên: thép bị cắt ở nét cắt
                    y_end = min(y_end, z1 + TOP_STUB - 40)
                pts += [(x, z1 - 6 * jt["shift"]), (xe, z1), (xe, y_end)]
            else:                                          # dừng ở đỉnh nút, móc vào trong
                yt = z1 - COVER - d / 2
                pts += [(x, yt), (x - sg * HOOK * d, yt)]
            D.pline(pts, False, "THEP")

        # ---- cốt đai: đầu cột, giữa cột, vùng nối, trong nút
        Hc = (z1 - hb) - z0
        l_end = max(b, sec["h"], Hc / 6, 500)
        lap_len = jb["lap"] if jb else 0
        s_lap = min(tie.get("s_lap", tie["s_end"]), tie["s_end"])
        lo_zone = max(l_end, lap_len)
        if tie["s_end"] < tie["s_mid"]:                   # thiết kế cũ / kháng chấn: đai dày 2 đầu cột
            zones = [(z0 + 50, z0 + lo_zone, s_lap if jb else tie["s_end"]),
                     (z0 + lo_zone, z1 - hb - l_end, tie["s_mid"]), (z1 - hb - l_end, z1 - 50, tie["s_end"])]
        else:                                              # TCVN 5574: đai đều, dày hơn trong vùng nối (10.3.6.2)
            zones = ([(z0 + 50, z0 + lap_len, s_lap)] if jb and s_lap < tie["s_mid"] else []) + \
                    [(z0 + (lap_len if jb and s_lap < tie["s_mid"] else 50), z1 - 50, tie["s_mid"])]
        c = COVER + dt / 2
        for y0, y1, sp in zones:
            if y1 <= y0:
                continue
            n = max(int((y1 - y0) // sp), 1)
            for k in range(n + 1):
                y = y0 + k * (y1 - y0) / n
                D.line(-b / 2 + c, y, b / 2 - c, y, "THEP_DAI")
        if top:                                            # đai tăng cường trong vùng neo của nút
            n = max(int(hb // 100), 2)
            for k in range(n + 1):
                y = z1 - hb + k * (hb - 50) / n
                D.line(-b / 2 + c, y, b / 2 - c, y, "THEP_DAI")
            if not (side[-1] and side[1]):
                D.text(0, z1 + 4 * S, "Nút biên: thép cột uốn neo vào dầm, đai tăng cường trong nút (10.4.11)",
                       2.2, "THEP", "center", "bottom")
        # kích thước vùng đai (bên trái)
        marks_y = sorted({round(v) for v in [z0, z1 - hb, z1] + [zz[1] for zz in zones[:-1]]})
        D.dim_chain_v(marks_y, xl, xl - 8 * S)
        for k, (y0, y1, sp) in enumerate(zones):          # chữ ghi đai lệch khỏi vị trí vạch mặt cắt
            if y1 - y0 > 6 * S:
                f = 0.75 if (k == 0 and len(zones) > 1) else (0.15 if k == 2 else 0.3)
                D.text(-b / 2 - 2 * S, y0 + f * (y1 - y0), f"Ø{dt}a{sp}", 2.2, "THEP_DAI", "right", "middle")

        # ---- ghi chú thép (bên phải) + ký hiệu mặt cắt
        n_bars = r["n_bars"] if "n_bars" in r else 2 * (lay["nb"] + lay["nh"]) - 4
        ym = z0 + 0.35 * Hc
        xt = xr + 14 * S
        D.tag2(b / 2 + 4 * S, ym, f"{n_bars}Ø{d}" + ("  (KHÔNG ĐẠT)" if not r["ok"] else ""), 1,
               [(b / 2 - a, ym, 0)])
        mine = [x for x in next(g for g in groups if s in g) if x["res"]["id"] in ids]
        if len(segs) == 1:                                 # 1 tầng: 3 mặt cắt chân – giữa – đầu cột
            y_cuts = {1: z0 + (jb["lap"] / 2 if jb else min(l_end, 0.3 * Hc) / 2),
                      2: z0 + 0.5 * Hc, 3: z1 - hb - min(l_end, 0.3 * Hc) / 2}
            for no, y in y_cuts.items():
                for sg in (-1, 1):
                    D.line(sg * (b / 2 + 2 * S), y, sg * (b / 2 + 7 * S), y, "TITLE")
                D.text(-b / 2 - 8 * S, y, str(no), 3.0, "TITLE", "right", "middle")
                D.text(b / 2 + 8 * S, y, str(no), 3.0, "TITLE", "left", "middle")
            s["y_cuts"] = y_cuts
        elif s is mine[len(mine) // 2]:
            no = gid[r["id"]]                              # vạch mặt cắt ở tầng giữa của nhóm
            y = z0 + 0.6 * Hc
            for sg in (-1, 1):
                D.line(sg * (b / 2 + 2 * S), y, sg * (b / 2 + 7 * S), y, "TITLE")
            D.text(-b / 2 - 8 * S, y, f"{no}", 3.0, "TITLE", "right", "middle")
            D.text(b / 2 + 8 * S, y, f"{no}", 3.0, "TITLE", "left", "middle")

        # ---- cao độ sàn (bên phải ngoài cùng)
        D.line(xr, z1, xr + 10 * S, z1, "TEXT")
        D.text(xr + 1 * S, z1 + 0.8 * S, f"{r['story']}  +{z1 / 1000:.3f}", 2.2, "TEXT", "left", "bottom")

        # ---- nút: ghi chiều dài nối, cách xử lý thép
        if jt:
            note = (f"Nối chồng {jt['lap']}" + (f", bẻ xiên 1:6 ({jt['shift']:.0f})" if jt["crank"] else
                                                 f", thép chờ neo {jt['dowel']}"))
            if i == len(segs) - 1:                         # đoạn nối nằm ở tầng trên -> chỉ ghi chú
                D.text(xl - 4 * S, z1 + TOP_STUB / 2, note + f" (xem bản vẽ {full[gi + 1]['res']['story']})",
                       2.2, "THEP", "right", "middle")
            else:
                D.text(xl - 22 * S, z1 + jt["lap"] / 2, note, 2.2, "THEP", "right", "middle")
                D.dim((xl, z1), (xl, z1 + jt["lap"]), (xl - 16 * S, z1), vertical=True)

    # đoạn cột tầng trên (có nét cắt) khi bản vẽ dừng trước tầng trên cùng
    if i1 < len(full) - 1:
        up, jt = full[i1 + 1], JF[i1]
        bu, zt = up["sec"]["b"], segs[-1]["z1"]
        yc = zt + TOP_STUB
        for sg in (-1, 1):
            D.line(sg * bu / 2, zt, sg * bu / 2, yc)
        D.break_line(-bu / 2, yc, bu / 2, yc)
        du = up["res"]["layout"]["d"]
        au = COVER + up["res"]["layout"]["tie"]["d"] + du / 2
        for sg in (-1, 1):                                        # thép tầng trên bắt đầu từ mặt sàn
            D.line(sg * (bu / 2 - au), zt, sg * (bu / 2 - au), yc - 50, "THEP")
        cu = COVER + up["res"]["layout"]["tie"]["d"] / 2
        y = zt + 50
        while y < yc - 50:
            D.line(-bu / 2 + cu, y, bu / 2 - cu, y, "THEP_DAI")
            y += up["res"]["layout"]["tie"]["s_end"]
        nu = up["res"].get("n_bars", 0)
        D.text(bu / 2 + 2 * S, zt + TOP_STUB / 2, f"{up['res']['story']}: {nu}Ø{du}", 2.2, "THEP", "left", "middle")

    # nét cắt khi chỉ vẽ một khoảng tầng
    if i0 > 0:
        D.text(0, segs[0]["z0"] - full[i0 - 1]["hb"] - LOW_STUB - 4 * S,
               f"(tiếp xuống {full[i0 - 1]['res']['story']})", 2.2, "TEXT", "center", "top")
    if i1 < len(full) - 1:
        D.text(0, segs[-1]["z1"] + TOP_STUB + 4 * S, f"(tiếp lên {full[i1 + 1]['res']['story']})",
               2.2, "TEXT", "center", "bottom")
    # cao độ các sàn
    D.dim_chain_v([s["z0"] for s in segs] + [segs[-1]["z1"]], xr, xr + 60 * S)

    x0, y0, x1, y1 = D.bbox()
    rng = segs[0]["res"]["story"] if len(segs) == 1 else f"{segs[0]['res']['story']} – {segs[-1]['res']['story']}"
    sub = f"TL 1:{S}"
    if len(segs) == 1:
        r0 = segs[0]["res"]
        sub = (f"{r0['section']} – {r0.get('n_bars', 0)}Ø{r0['layout']['d']} – μ = {r0['mu'] * 100:.2f}% – "
               f"hệ số sử dụng {r0['util']:.3f} ({'ĐẠT' if r0['ok'] else 'KHÔNG ĐẠT'}) – bê tông "
               f"{segs[0]['sec'].get('material', '')} – TL 1:{S}")
    D.title((x0 + x1) / 2, y1 + 12 * S, f"MẶT CẮT DỌC CỘT {label} – {rng}", sub)

    # ---- mặt cắt ngang từng nhóm tầng + mặt cắt vùng nối khi đổi tiết diện (TL 1:sec_scale, phóng k)
    from .sections import column_sheet
    if len(segs) == 1:
        sec_scale = S                                   # 1 tầng: mặt cắt ngang cùng tỉ lệ, xếp 1 cột cạnh mặt cắt dọc
    k = S / sec_scale
    xs = x1 + 30 * S
    y_cursor = y1
    sheets = []
    if len(segs) == 1:
        sheets = story_sections(full, JF, i0, sec_scale)
        y_cursor = segs[0]["z1"] + TOP_STUB
        groups = []
    for g in reversed(groups):                                   # xếp từ trên xuống, giống mặt cắt dọc
        no = gid[g[0]["res"]["id"]]
        r = dict(g[0]["res"])
        names = [s["res"]["story"] for s in g if s["res"]["id"] in ids]
        r["story"] = names[0] if len(names) == 1 else f"{names[0]}–{names[-1]}"
        sh = column_sheet(r, g[0]["sec"], sec_scale)
        sh.text(0, sh.bbox()[3] + 4 * sec_scale, f"MẶT CẮT {no}-{no}", 5.0, "TITLE", "center", "bottom")
        sheets.append(sh)
    for gi in (range(i1, max(i0, 1) - 1, -1) if len(segs) > 1 else []):   # vùng nối ở chân đoạn tầng trên
        j = JF[gi - 1]
        if j["e"] > 0:
            sheets.append(joint_section(full[gi - 1], full[gi], j, sec_scale))
    if len(segs) == 1:                                 # bố cục giống bản vẽ dầm: hàng mặt cắt ngang + ghi chú bên dưới
        from .sections import legend
        sec_scale_row = 20
        k = S / sec_scale_row
        sheets = story_sections(full, JF, i0, sec_scale_row)[::-1]          # 1-1, 2-2, 3-3 từ trái sang phải
        x_cur = x0
        y_top = y0 - 12 * S
        row_h = 0.0
        for sh in sheets:
            bx0, by0, bx1, by1 = sh.bbox()
            D.merge(sh, x_cur - bx0 * k, y_top - by1 * k, k)
            x_cur += (bx1 - bx0) * k + 12 * S
            row_h = max(row_h, (by1 - by0) * k)
        r0 = segs[0]["res"]
        L0 = r0["layout"]
        marks = [{"mark": 1, "n": r0.get("n_bars", 0), "d": L0["d"], "kind": "bar",
                  "desc": f"Thép dọc chịu lực {r0['story']}"}]
        if i0 > 0:                                     # số hiệu: 1 thép tầng này, 2 thép tầng dưới nối, 3 cốt đai
            lo = full[i0 - 1]["res"]
            marks.append({"mark": 2, "n": lo.get("n_bars", 0), "d": lo["layout"]["d"], "kind": "bar",
                          "desc": f"Thép dọc {lo['story']} nối chồng lên (chấm rỗng ở mặt cắt 1-1)"})
        tie = L0["tie"]
        marks.append({"mark": 3, "n": 1, "d": tie["d"], "kind": "stir",
                      "desc": (f"Cốt đai a{tie['s_mid']}" + (f", vùng nối chồng a{min(tie.get('s_lap', tie['s_end']), tie['s_end'])}"
                               if i0 > 0 and tie.get('s_lap', tie['s_end']) < tie['s_mid'] else "")
                               + (f", đầu cột a{tie['s_end']}" if tie['s_end'] < tie['s_mid'] else "")
                               + " – TCVN 5574:2018 10.3.4, 10.3.6.2")})
        legend(D, x0, y_top - row_h - 10 * S, marks)
        return D
    col_w = 0.0
    for sh in sheets:
        bx0, by0, bx1, by1 = sh.bbox()
        if len(segs) > 1 and y_cursor - (by1 - by0) * k < y0 - 10 * S and col_w:   # hết chiều cao -> cột mới
            xs += col_w + 20 * S
            y_cursor, col_w = y1, 0.0
        D.merge(sh, xs - bx0 * k, y_cursor - by1 * k, k)
        y_cursor -= (by1 - by0) * k + 20 * S
        col_w = max(col_w, (bx1 - bx0) * k)
    return D


def joint_section(lo, up, j, scale, title=None, tie_txt=None):
    """Mặt cắt qua vùng nối ngay trên sàn: tiết diện tầng trên, thép tầng trên (đặc) + thép tầng dưới đang nối (rỗng)."""
    from .sections import column_section_simple
    S = scale
    b, h = up["sec"]["b"], up["sec"]["h"]
    Lu, Ll = up["res"]["layout"], lo["res"]["layout"]
    bu = bar_positions(b, h, COVER, Lu["tie"]["d"], Lu["d"], Lu["nb"], Lu["nh"])
    s = (Ll["d"] + Lu["d"]) / 2
    bl = bar_positions(b, h, COVER, Lu["tie"]["d"], Ll["d"], Ll["nb"], Ll["nh"])
    hollow = []
    for t in bl:                                       # thép dưới nằm phía trong, cạnh thép trên
        z = t["z"] - math.copysign(s, t["z"]) if abs(t["z"]) > b / 2 - 80 else t["z"]
        y = t["y"] - math.copysign(s, t["y"]) if abs(t["y"]) > h / 2 - 80 else t["y"]
        hollow.append((z, y))
    tags = [(f"{len(bu)}Ø{Lu['d']}", 1, "bars"),
            (f"{len(bl)}Ø{Ll['d']} ({lo['res']['story']}, nối)", 2, "hollow")]
    if tie_txt:
        tags.append((tie_txt.replace("Đai ", ""), 3, "tie"))
    D = column_section_simple(b, h, COVER, Lu["tie"]["d"], bu, Lu["d"], tags, scale, hollow, Ll["d"],
                              outer=(lo["sec"]["b"], lo["sec"]["h"]) if j["e"] > 0 else None)
    x0, y0, x1, y1 = D.bbox()
    D.text(0, y0 - 2 * S, (f"Nét mảnh: mép cột {lo['res']['section']} tầng dưới – " if j["e"] > 0 else "")
           + "chấm rỗng: thép tầng dưới nối chồng", 2.0, "TEXT", "center", "top")
    if title:
        D.text(0, y0 - 7 * S, title, 3.5, "TITLE", "center", "top")
        D.text(0, y0 - 12 * S, f"TỈ LỆ 1/{S:.0f}", 3.0, "TITLE", "center", "top")
    return D


def story_sections(full, JF, gi, scale):
    """3 mặt cắt ngang của 1 tầng, xếp từ trên xuống: 3-3 đầu cột, 2-2 giữa cột, 1-1 chân cột."""
    from .sections import column_sheet
    seg = full[gi]
    r, sec = seg["res"], seg["sec"]
    tie = r["layout"]["tie"]
    dt = tie["d"]
    S = scale
    out = []
    from .sections import section_title
    for no, zone, name in ((3, "end", "ĐẦU CỘT"), (2, "mid", "GIỮA CỘT")):
        sh = column_sheet(r, sec, scale, zone=zone, compact=True)
        bx0, by0, bx1, by1 = sh.bbox()
        section_title(sh, 0, by0 - 3 * S, no, scale)
        out.append(sh)
    if gi > 0:                                         # chân cột: cắt qua vùng nối chồng
        sh = joint_section(full[gi - 1], seg, JF[gi - 1], scale, title="MẶT CẮT 1 - 1",
                           tie_txt=f"Ø{dt}a{min(tie.get('s_lap', tie['s_end']), tie['s_end'])}")
    else:                                              # tầng 1: chân cột trên móng
        sh = column_sheet(r, sec, scale, zone="end", compact=True)
        bx0, by0, bx1, by1 = sh.bbox()
        section_title(sh, 0, by0 - 3 * S, 1, scale)
    out.append(sh)
    return out


def column_story_sheets(project, cols_res, label, story_from=None, story_to=None, per_row=3, scale=25):
    """Mỗi tầng 1 bản vẽ (mặt cắt dọc đoạn cột tầng đó + mặt cắt ngang + vùng nối), xếp lưới từ tầng trên xuống."""
    from .sections import combine
    full = column_stack(project, cols_res, label)
    if not full:
        raise ValueError(f"Không có cột {label}")
    names = [s["res"]["story"] for s in full]
    for st in (story_from, story_to):
        if st and st not in names:
            raise ValueError(f"Cột {label} không có ở tầng {st}")
    i0 = names.index(story_from) if story_from in names else 0
    i1 = names.index(story_to) if story_to in names else len(full) - 1
    i0, i1 = min(i0, i1), max(i0, i1)
    sheets = [column_elevation(project, cols_res, label, scale, story_from=n, story_to=n)
              for n in reversed(names[i0:i1 + 1])]
    return combine(sheets, scale, per_row=per_row)


def column_stories(project, cols_res, label):
    """Tên các tầng có cột này, từ dưới lên."""
    return [s["res"]["story"] for s in column_stack(project, cols_res, label)]
