"""Vẽ mặt cắt dầm (3 mặt cắt: gối trái – giữa nhịp – gối phải) và mặt cắt cột từ kết quả thiết kế."""
from core.beam_layout import place_face, ZONES
from core.column_section import bar_positions
from .model import Drawing, rounded_rect, hook135

ZONE_NAME = {"L": "Gối trái", "M": "Giữa nhịp", "R": "Gối phải"}
COLUMN_TIES_IN_SECTION = False      # mặt cắt ngang cột: không vẽ cốt đai, chỉ ghi chữ (đai thể hiện ở mặt cắt dọc)


# ============================================================================ DẦM
def merge_close(values, tol=5.0):
    """Gộp các giá trị gần nhau (< tol mm) -> 1 giá trị; tránh đoạn kích thước 1–2 mm vô nghĩa
    khi trong cùng 1 lớp có thanh khác đường kính."""
    out = []
    for v in sorted(values):
        if not out or v - out[-1] > tol:
            out.append(v)
    return out


def beam_marks(layout):
    """Đánh số hiệu thép: 1 = suốt trên, 2 = suốt dưới, 3.. = gia cường, cuối cùng là đai.
    Thanh gia cường cùng thớ, cùng số lượng và đường kính ở 2 gối thì dùng chung 1 số hiệu."""
    marks = []

    def add(n, d, kind, face, group, zone, desc):
        for m in marks:
            if (m["n"], m["d"], m["kind"], m["face"], m["group"]) == (n, d, kind, face, group):
                m["zones"].add(zone)
                return
        marks.append({"mark": len(marks) + 1, "n": n, "d": d, "kind": kind, "face": face,
                      "group": group, "zones": {zone}, "desc": desc})

    top, bot = layout["top"], layout["bot"]
    for z in ZONES:
        add(*top["cont"], "bar", "top", "cont", z, "Thép chạy suốt thớ trên")
        add(*bot["cont"], "bar", "bot", "cont", z, "Thép chạy suốt thớ dưới")
    for face, fl, nm in (("top", top, "thớ trên"), ("bot", bot, "thớ dưới")):
        for z in ZONES:
            n, d = fl["add"][z]
            if n:
                add(n, d, "bar", face, "add", z, f"Thép gia cường {nm}")
    st = layout["stirrup"]
    for z in ZONES:
        add(1, st["d"], "stir", "", "outer", z, f"Cốt đai a{st['s_end']} (đầu dầm) / a{st['s_mid']} (giữa)")
    for m in marks:                                         # ghi rõ vùng cho thép gia cường
        if m["group"] == "add":
            m["desc"] += " – " + ", ".join(ZONE_NAME[z].lower() for z in ZONES if z in m["zones"])
    return marks


def _mark(marks, kind, face, group, zone):
    return next(m for m in marks if (m["kind"], m["face"], m["group"]) == (kind, face, group)
                and zone in m["zones"])


def section_title(D, x, y, no, scale):
    """Tên mặt cắt kiểu bản vẽ thi công: 'MẶT CẮT 1 - 1' / 'TỈ LỆ 1/10', đặt bên dưới mặt cắt."""
    D.text(x, y, f"MẶT CẮT {no} - {no}", 3.5, "TITLE", "center", "top")
    D.text(x, y - 5 * D.S, f"TỈ LỆ 1/{scale:.0f}", 3.0, "TITLE", "center", "top")


def draw_beam_section(D, ox, oy, b, h, cover, layout, zone, marks, no):
    """Mặt cắt dầm kiểu bản vẽ thi công, góc dưới trái tại (ox, oy): khung đai, thép chấm đặc,
    ghi chú thép bên phải (chữ + số hiệu khoanh tròn), kích thước bên trái và bên dưới, tên ở dưới."""
    S, st = D.S, layout["stirrup"]
    ds = st["d"]
    D.rect(ox, oy, b, h)
    c = cover + ds / 2                                       # đường tim cốt đai
    D.rect(ox + c, oy + c, b - 2 * c, h - 2 * c, "THEP_DAI")
    if st["legs"] >= 4:                                      # đai trong cho dầm rộng
        D.rect(ox + b / 3, oy + c, b / 3, h - 2 * c, "THEP_DAI")

    groups, rows = {}, {}
    for face in ("top", "bot"):
        fl = layout[face]
        pf = place_face(b, cover, ds, fl["cont"], fl["add"][zone], face)
        for t in pf["bars"]:
            x = ox + t["x"]
            y = oy + h - t["y"] if face == "top" else oy + t["y"]
            D.circle(x, y, t["d"] / 2, "THEP", filled=True)
            m = _mark(marks, "bar", face, t["group"], zone)
            groups.setdefault((face, m["mark"]), (m, []))[1].append((x, y, t["d"] / 2))
            rows.setdefault(face, []).append((x, y, t["layer"]))

    # ghi chú thép bên phải: thớ trên xếp từ trên xuống, thớ dưới xếp từ dưới lên
    xt = ox + b + 6 * S
    tops = [g for k, g in sorted(groups.items(), key=lambda kv: kv[0][1]) if k[0] == "top"]
    bots = [g for k, g in sorted(groups.items(), key=lambda kv: kv[0][1]) if k[0] == "bot"]
    for i, (m, pts) in enumerate(tops):
        D.tag2(xt, oy + h + 3 * S - i * 6 * S, f"{len(pts)}Ø{m['d']}", m["mark"], pts)
    for i, (m, pts) in enumerate(bots):
        D.tag2(xt, oy - 3 * S + i * 6 * S, f"{len(pts)}Ø{m['d']}", m["mark"], pts)

    # kích thước: trái = lớp bảo vệ – khoảng thép – lớp bảo vệ + tổng; dưới = tương tự
    yb1 = min(y for x, y, l in rows["bot"] if l == 1)
    yt1 = max(y for x, y, l in rows["top"] if l == 1)
    D.dim_chain_v([oy, yb1, yt1, oy + h], ox, ox - 6 * S)
    D.dim((ox, oy), (ox, oy + h), (ox - 12 * S, oy), vertical=True)
    xs = sorted(x for x, y, l in rows["bot"] if l == 1)
    D.dim_chain_h([ox, xs[0], xs[-1], ox + b], oy, oy - 6 * S)
    D.dim((ox, oy), (ox + b, oy), (ox, oy - 12 * S))
    section_title(D, ox + b / 2, oy - 17 * S, no, D.S)


def legend(D, x, y, marks):
    S = D.S
    D.text(x, y, "GHI CHÚ SỐ HIỆU THÉP", 3.0, "TITLE")
    for i, m in enumerate(marks):
        yy = y - 8 * S - i * 6.5 * S
        D.bubble(x + 2.6 * S, yy, m["mark"])
        spec = f"{m['n']}Ø{m['d']}" if m["kind"] == "bar" else f"Ø{m['d']}"
        D.text(x + 7 * S, yy, f"{spec}  –  {m['desc']}", 2.5, "TEXT", "left", "middle")


def beam_sheet(res, sec, scale=10, cover=25, det=None):
    """1 dầm = (mặt cắt dọc 1:25 nếu có det) + 3 mặt cắt ngang 1:10 + tiêu đề + ghi chú."""
    S = scale
    b, h = sec["b"], sec["h"]
    layout = res["layout"]
    marks = beam_marks(layout)
    secs = Drawing(scale)
    gap = b + 50 * S
    for i, z in enumerate(ZONES):
        draw_beam_section(secs, i * gap, 0, b, h, cover, layout, z, marks, i + 1)
    legend(secs, -20 * S, -40 * S, marks)

    if det is None:
        D = Drawing(scale)
        D.merge(secs)
        top = secs.bbox()[3]
    else:
        # mặt cắt dọc 1:25 ở trên; mặt cắt ngang 1:10 phóng 2.5 lần đặt bên dưới
        from .elevation import beam_elevation
        ES = 25
        k = ES / scale
        E = beam_elevation(res, sec, det, marks, ES, cover)
        D = Drawing(ES)
        D.merge(E)
        ex0, ey0, ex1, ey1 = E.bbox()
        sx0, sy0, sx1, sy1 = secs.bbox()
        D.merge(secs, ex0 - sx0 * k, ey0 - 15 * ES - sy1 * k, k)
        top = ey1
        S = ES
    status = "ĐẠT" if res["ok"] else "KHÔNG ĐẠT"
    D.text(-20 * S, top + 20 * S, f"DẦM {res['label']} – {res['story']} – {res['section']} "
           f"({b:.0f}×{h:.0f}), L = {res['L']:.0f} mm", 5.0, "TITLE")
    D.text(-20 * S, top + 13 * S, f"Bê tông {sec['material']}, thép CB400-V, đai CB240-T – TCVN 5574:2018 – "
           f"hệ số sử dụng {res['util']:.3f} ({status})", 2.8, "TEXT")
    return D


# ============================================================================ CỘT
def column_section_simple(b, h, cover, dt, bars, d, tags, scale, hollow=(), d_hollow=0, outer=None):
    """Mặt cắt cột kiểu bản vẽ thi công: khung đai chu vi, thép dọc chấm đặc (thép tầng dưới đang nối: chấm rỗng),
    ghi chú bên phải (chữ + số hiệu khoanh tròn), kích thước bên trái và bên dưới.
    tags = [(chữ, số hiệu, "bars" | "hollow" | "tie")]; outer = (b, h) mép cột tầng dưới (nét mảnh)."""
    D = Drawing(scale)
    S = scale
    x0, y0 = -b / 2, -h / 2
    D.rect(x0, y0, b, h)
    if outer:
        D.rect(-outer[0] / 2, -outer[1] / 2, outer[0], outer[1], "TEXT")
    c = cover + dt / 2
    D.rect(x0 + c, y0 + c, b - 2 * c, h - 2 * c, "THEP_DAI")
    for t in bars:
        D.circle(t["z"], t["y"], d / 2, "THEP", filled=True)
    for z, y in hollow:
        D.circle(z, y, d_hollow / 2, "THEP", filled=False)
    zs = sorted({round(t["z"], 1) for t in bars})
    ys = sorted({round(t["y"], 1) for t in bars})
    right = sorted([t for t in bars if abs(t["z"] - zs[-1]) < 1], key=lambda t: -t["y"])
    xt = -x0 + 6 * S
    yt = -y0 + 3 * S
    for label, mark, kind in tags:
        if kind == "bars":                             # chỉ tới các thanh cạnh phải (đại diện)
            tg = [(t["z"], t["y"], d / 2) for t in right[:3]]
        elif kind == "hollow" and hollow:
            hr = sorted(hollow, key=lambda p: (-p[0], -p[1]))[:2]
            tg = [(z, y, d_hollow / 2) for z, y in hr]
        else:                                          # đai
            tg = [(-x0 - c, 0, 0)]
        D.tag2(xt, yt, label, mark, tg)
        yt -= 6 * S
    D.dim_chain_v([y0, ys[0], ys[-1], -y0], x0, x0 - 6 * S)            # trái: lớp bảo vệ – khoảng thép – lớp bảo vệ
    D.dim((x0, y0), (x0, -y0), (x0 - 12 * S, y0), vertical=True)        # trái: tổng
    D.dim_chain_h([x0, zs[0], zs[-1], -x0], y0, y0 - 6 * S)            # dưới
    D.dim((x0, y0), (-x0, y0), (x0, y0 - 12 * S))                       # dưới: tổng
    if outer and (outer[0] != b or outer[1] != h):
        ox, oy = -outer[0] / 2, -outer[1] / 2
        D.dim((ox, oy), (-ox, oy), (ox, oy - 17 * S))
        D.dim((ox, oy), (ox, -oy), (ox - 17 * S, oy), vertical=True)
    return D


def column_sheet(res, sec, scale=10, cover=30, zone=None, compact=False):
    """zone: "end" (đầu cột, đai dày) | "mid" (giữa cột, đai thưa) | None (ghi cả 2).
    compact=True: mặt cắt kiểu bản vẽ thi công (dùng khi đặt cạnh mặt cắt dọc)."""
    if compact:
        L = res["layout"]
        tie = L["tie"]
        bars = bar_positions(sec["b"], sec["h"], cover, tie["d"], L["d"], L["nb"], L["nh"])
        sp = {"end": tie["s_end"], "mid": tie["s_mid"]}.get(zone)
        tie_txt = f"Đai Ø{tie['d']}a{sp}" if sp else f"Đai Ø{tie['d']}a{tie['s_end']}/{tie['s_mid']}"
        return column_section_simple(sec["b"], sec["h"], cover, tie["d"], bars, L["d"],
                                     [(f"{len(bars)}Ø{L['d']}", 1, "bars"), (tie_txt.replace("Đai ", ""), 3, "tie")],
                                     scale)
    # bản vẽ cột đầy đủ (bản vẽ theo tầng, xem trước trong app): mặt cắt + tên + thông tin cột
    D = column_sheet(res, sec, scale, cover, zone=zone, compact=True)
    S = scale
    x0, y0, x1, y1 = D.bbox()
    D.text(0, y0 - 3 * S, f"MẶT CẮT CỘT {res['label']} – {res['story']}", 3.5, "TITLE", "center", "top")
    D.text(0, y0 - 8 * S, f"TỈ LỆ 1/{scale:.0f}", 3.0, "TITLE", "center", "top")
    status = "ĐẠT" if res["ok"] else "KHÔNG ĐẠT"
    D.text(x0, y1 + 12 * S, f"CỘT {res['label']} – {res['story']} – {res['section']} "
           f"({sec['b']:.0f}×{sec['h']:.0f}), L = {res['L']:.0f} mm", 4.0, "TITLE")
    D.text(x0, y1 + 6 * S, f"Bê tông {sec['material']}, thép CB400-V – μ = {res['mu']*100:.2f}% – "
           f"hệ số sử dụng {res['util']:.3f} ({status})", 2.5, "TEXT")
    return D


def combine(sheets, scale, per_row=2):
    """Ghép nhiều bản vẽ vào 1 file, xếp lưới."""
    D = Drawing(scale)
    x = y = row_h = 0.0
    gap = 40 * scale
    for i, sh in enumerate(sheets):
        x0, y0, x1, y1 = sh.bbox()
        if i and i % per_row == 0:
            x, y, row_h = 0.0, y - row_h - gap, 0.0
        D.merge(sh, x - x0, y - y1)
        x += (x1 - x0) + gap
        row_h = max(row_h, y1 - y0)
    return D
