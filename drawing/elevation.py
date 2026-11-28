"""Mặt cắt dọc dầm: thép theo chiều dài, vùng đai, vị trí các mặt cắt ngang."""
from .model import Drawing


def beam_elevation(res, sec, det, marks, scale=25, cover=25, axes=None, level=None):
    """axes = (tên trục gối trái, tên trục gối phải, tên trục dầm nằm trên) -> bong bóng trục;
    level = (tên tầng, cao độ mặt dầm m) -> ký hiệu cao độ ở mặt dầm."""
    from .sections import _mark                      # dùng chung bảng số hiệu với mặt cắt ngang
    D = Drawing(scale)
    S = scale
    h = sec["h"]
    Lc, hL, hR = det["Lc"], det["hL"], det["hR"]
    ds = res["layout"]["stirrup"]["d"]

    # bê tông: dầm + 2 gối. Gối cột/vách: vẽ đoạn cột cắt ngang có nét cắt; gối dầm: vẽ tiết diện dầm chính
    D.line(0, 0, Lc, 0)
    D.line(0, h, Lc, h)
    for x0, w, kind, hg in ((-hL, hL, det["kind_L"], det.get("depth_L", 0)), (Lc, hR, det["kind_R"], det.get("depth_R", 0))):
        if kind == "liên tục":                               # dầm liên tục qua điểm chia (không có gối): nét cắt
            D.break_line(x0, 0, x0, h)
            continue
        if kind == "dầm":
            hg = hg or h
            D.rect(x0, h - hg, w, hg)                        # mặt cắt ngang dầm chính (đỉnh ngang đỉnh dầm)
            D.line(x0, h - hg, x0 + w, h, "TEXT")             # gạch chéo ký hiệu mặt cắt
            D.line(x0, h, x0 + w, h - hg, "TEXT")
            continue
        D.line(x0, -0.8 * h, x0, 1.8 * h)
        D.line(x0 + w, -0.8 * h, x0 + w, 1.8 * h)
        for yb in (-0.8 * h, 1.8 * h):                  # nét cắt zig-zag ở đầu đoạn cột
            m = x0 + w / 2
            D.pline([(x0 - 2 * S, yb), (m - 1.5 * S, yb), (m - 0.5 * S, yb + 2 * S),
                     (m + 0.5 * S, yb - 2 * S), (m + 1.5 * S, yb), (x0 + w + 2 * S, yb)])

    # cốt đai
    for z in det["stirrups"]:
        x = z["x0"]
        while x <= z["x1"] + 1e-6:
            D.line(x, cover, x, h - cover, "THEP_DAI")
            x += z["s"]

    # đường trục ở tâm 2 gối
    n_top = sum(1 for bar in det["bars"] if bar["face"] == "top")
    y_ax0, y_ax1 = -0.8 * h - 30 * S, 1.8 * h + (5 + 5.5 * n_top) * S + 22 * S
    for k, xa in enumerate((-hL / 2, Lc + hR / 2)):
        D.line(xa, y_ax0, xa, y_ax1, "TEXT")
    if level:                                             # cao độ mặt dầm (= mặt sàn), bên trái ngoài thép neo
        x_left = min([-hL - 10 * S] + [bar["x0"] for bar in det["bars"]]) - 4 * S   # tránh kích thước chiều cao dầm
        D.level(x_left, h, level[1], level[0], side=-1)

    # chuỗi kích thước vùng đai ở trên cùng, ghi đường kính + khoảng cách ngay dưới đường kích thước
    y_st = 1.8 * h + (5 + 5.5 * n_top) * S + 10 * S
    xs = [-hL / 2, 0] + [z["x0"] for z in det["stirrups"]][1:] + [Lc, Lc + hR / 2]
    D.dim_chain_h(xs, h, y_st)
    for z in det["stirrups"]:
        D.text((z["x0"] + z["x1"]) / 2, y_st - 1.2 * S, f"Ø{z['d']}a{z['s']:.0f}", 2.2, "THEP_DAI", "center", "top")

    # thép dọc: mỗi nhóm thép 1 "làn" riêng để nhìn tách bạch (thép suốt sát mép, gia cường lùi vào trong);
    # các nhóm không chồng nhau theo chiều dài (gia cường gối trái / gối phải) dùng chung 1 làn
    zones = {f: {bar["key"][2] for bar in det["bars"] if bar["face"] == f and len(bar["key"]) > 2} for f in ("top", "bot")}
    def track(face, zone):
        if zone is None:
            return 0
        first = ("L", "R") if face == "top" else ("M",)
        if zone in first or not (zones[face] & set(first)):
            return 1
        return 2
    y_edge = {"top": h - cover - ds - 12, "bot": cover + ds + 12}
    n_tr = max([track(f, z) for f in zones for z in zones[f]] + [1])
    step = min(max(45, 2.2 * S), (h / 2 - cover - ds - 12) / (n_tr + 0.5))
    k = {"top": 0, "bot": 0}
    for bar in det["bars"]:
        face = bar["face"]
        if face == "side":                                  # thép cấu tạo mặt bên: nét đứt mảnh ở từng cao độ
            m = _mark(marks, "bar", "side", "side", "M")
            for i, ys in enumerate(det.get("side_y", [])):
                x = bar["x0"]
                while x < bar["x1"]:
                    D.line(x, ys, min(x + 6 * S, bar["x1"]), ys, "THEP")
                    x += 9 * S
            xm = bar["x0"] + 0.62 * (bar["x1"] - bar["x0"])
            yt = -0.8 * h - (5 + 5.5 * k["bot"]) * S          # ghi chú xếp chung hàng với thép thớ dưới
            D.tag2(xm + 4 * S, yt, f"{bar['n']}Ø{bar['d']}", m["mark"], [(xm, y, 0) for y in det.get("side_y", [])])
            k["bot"] += 1
            continue
        tr = track(face, bar["key"][2] if len(bar["key"]) > 2 else None)
        y = y_edge[face] + (-1 if face == "top" else 1) * tr * step
        sg = -1 if face == "top" else 1                 # móc: thép trên bẻ xuống, thép dưới bẻ lên
        pts = []
        if bar["hook0"]:
            pts.append((bar["x0"], y + sg * min(bar["hook0"], 0.4 * h)))   # vẽ ngắn cho dễ nhìn
        pts += [(bar["x0"], y), (bar["x1"], y)]
        if bar["hook1"]:
            pts.append((bar["x1"], y + sg * min(bar["hook1"], 0.4 * h)))
        D.pline(pts, False, "THEP")
        zone = bar["key"][2] if len(bar["key"]) > 2 else "L"
        m = _mark(marks, "bar", face, bar["key"][1], zone)
        xm = bar["x0"] + (bar["x1"] - bar["x0"]) * (0.3 + 0.2 * (k[face] % 3))
        yt = h + 0.8 * h + (5 + 5.5 * k[face]) * S if face == "top" else -0.8 * h - (5 + 5.5 * k[face]) * S
        D.tag2(xm + 4 * S, yt, f"{bar['n']}Ø{bar['d']}", m["mark"], [(xm, y, 0)])
        k[face] += 1

    # kích thước: vùng đai + nhịp thông thủy
    yd = -0.8 * h - (5 + 5.5 * k["bot"]) * S - 6 * S
    D.dim_chain_h([-hL / 2, 0, Lc, Lc + hR / 2], 0, yd)                 # trục – mép gối – mép gối – trục
    D.dim((-hL / 2, 0), (Lc + hR / 2, 0), (-hL / 2, yd - 6 * S))        # nhịp theo trục
    if axes:                                              # bong bóng tên trục: kéo đường trục xuống dưới kích thước
        for xa, nm in ((-hL / 2, axes[0]), (Lc + hR / 2, axes[1])):
            if nm:
                D.line(xa, y_ax0, xa, yd - 9 * S, "TEXT")
                D.bubble_axis(xa, yd - 9 * S, nm)
    D.dim((-hL, 0), (-hL, h), (-hL - 6 * S, 0), vertical=True)

    # vị trí các mặt cắt ngang: vạch đậm trên và dưới dầm (như bản vẽ mẫu)
    for no, x in ((1, Lc / 8), (2, Lc / 2), (3, 7 * Lc / 8)):
        D.cut_mark(x, h + 0.3 * h + 2 * S, no)
        D.cut_mark(x, -0.3 * h - 2 * S, no)

    gd = lambda k, w: "dầm liên tục (không có gối)" if k == "liên tục" else f"{k} {w:.0f}"
    D.title(Lc / 2, yd - 22 * S, f"MẶT CẮT DỌC DẦM {res['label']}",
            f"Nhịp thông thủy {Lc:.0f} mm, gối trái: {gd(det['kind_L'], hL)}, gối phải: {gd(det['kind_R'], hR)} – TL 1:{S}")
    return D
