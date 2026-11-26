"""Mặt cắt dọc dầm: thép theo chiều dài, vùng đai, vị trí các mặt cắt ngang."""
from .model import Drawing


def beam_elevation(res, sec, det, marks, scale=25, cover=25):
    from .sections import _mark                      # dùng chung bảng số hiệu với mặt cắt ngang
    D = Drawing(scale)
    S = scale
    h = sec["h"]
    Lc, hL, hR = det["Lc"], det["hL"], det["hR"]
    ds = res["layout"]["stirrup"]["d"]

    # bê tông: dầm + 2 gối (vẽ đoạn cột/vách cắt ngang, có nét cắt)
    D.line(0, 0, Lc, 0)
    D.line(0, h, Lc, h)
    for x0, w in ((-hL, hL), (Lc, hR)):
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
    for xa in (-hL / 2, Lc + hR / 2):
        D.line(xa, y_ax0, xa, y_ax1, "TEXT")

    # chuỗi kích thước vùng đai ở trên cùng, ghi đường kính + khoảng cách ngay dưới đường kích thước
    y_st = 1.8 * h + (5 + 5.5 * n_top) * S + 10 * S
    xs = [-hL / 2, 0] + [z["x0"] for z in det["stirrups"]][1:] + [Lc, Lc + hR / 2]
    D.dim_chain_h(xs, h, y_st)
    for z in det["stirrups"]:
        D.text((z["x0"] + z["x1"]) / 2, y_st - 1.2 * S, f"Ø{z['d']}a{z['s']:.0f}", 2.2, "THEP_DAI", "center", "top")

    # thép dọc
    y_of = {("top", 1): h - cover - ds - 12, ("top", 2): h - cover - ds - 12 - 45,
            ("bot", 1): cover + ds + 12, ("bot", 2): cover + ds + 12 + 45}
    k = {"top": 0, "bot": 0}
    for bar in det["bars"]:
        face = bar["face"]
        y = y_of[(face, bar["layer"])]
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
    D.dim((-hL, 0), (-hL, h), (-hL - 6 * S, 0), vertical=True)

    # vị trí các mặt cắt ngang
    for no, x in ((1, Lc / 8), (2, Lc / 2), (3, 7 * Lc / 8)):
        for y0, y1 in ((h + 0.3 * h, h + 0.3 * h + 3 * S), (-0.3 * h, -0.3 * h - 3 * S)):
            D.line(x, y0, x, y1, "TITLE")
        D.text(x + 1 * S, h + 0.3 * h + 3 * S, str(no), 3.0, "TITLE", "left", "middle")
        D.text(x + 1 * S, -0.3 * h - 3 * S, str(no), 3.0, "TITLE", "left", "middle")

    D.title(Lc / 2, yd - 18 * S, f"MẶT CẮT DỌC DẦM {res['label']}",
            f"Nhịp thông thủy {Lc:.0f} mm, gối trái: {det['kind_L']} {hL:.0f}, gối phải: {det['kind_R']} {hR:.0f} – TL 1:{S}")
    return D
