"""Vẽ mặt cắt dầm (3 mặt cắt: gối trái – giữa nhịp – gối phải) và mặt cắt cột từ kết quả thiết kế."""
from core.beam_layout import place_face, ZONES
from core.column_section import bar_positions
from .model import Drawing, rounded_rect, hook135, story_vn

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


def beam_marks(layout, side=None):
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
    if side:
        for z in ZONES:
            add(side[0], side[1], "bar", "side", "side", z, "Thép cấu tạo 2 mặt bên (dầm cao > 700 mm)")
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
    """Tên mặt cắt kiểu bản vẽ thi công: 'MC 1-1' chữ lớn, tỉ lệ '1 : 10' bên dưới."""
    D.text(x, y, f"MC {no}-{no}", 5.0, "TITLE", "center", "top")
    D.text(x, y - 7.5 * D.S, f"1 : {scale:.0f}", 3.0, "TEXT", "center", "top")


def _tags_ortho(D, items, x_start, y_first, step, up=True):
    """Ghi chú thép kiểu đường dẫn vuông góc. items = [(chữ, số hiệu, (x, y) thanh đại diện)].
    Thanh nằm càng bên phải thì gạch ngang càng gần tiết diện -> các đường dẫn không cắt nhau."""
    items = sorted(items, key=lambda t: -t[2][0])
    for i, (label, mark, (x, y)) in enumerate(items):
        yy = y_first + (i * step if up else -i * step)
        D.tag2(x_start, yy, label, mark, [(x, y, 0)])
    return len(items)


def draw_beam_section(D, ox, oy, b, h, cover, layout, zone, marks, no, side_y=(), side_d=0, slab_t=0, bot_rows=0):
    """Mặt cắt dầm kiểu bản vẽ thi công (giống bản vẽ mẫu), góc dưới trái tại (ox, oy):
    bê tông (kèm cánh sàn nếu có), khung đai, thép chấm đặc; ghi chú bên phải bằng đường dẫn vuông góc
    (mỗi nhóm thép 1 đường dẫn, số hiệu khoanh tròn); kích thước tổng bên trái và bên dưới; tên ở dưới."""
    S, st = D.S, layout["stirrup"]
    ds = st["d"]
    t = slab_t if 0 < slab_t < h else 0
    ext = 0.45 * b if t else 0                               # đoạn sàn vẽ thêm mỗi bên
    if t:
        D.pline([(ox, oy + h - t), (ox, oy), (ox + b, oy), (ox + b, oy + h - t)])
        D.line(ox - ext, oy + h, ox + b + ext, oy + h)
        D.line(ox - ext, oy + h - t, ox, oy + h - t)
        D.line(ox + b, oy + h - t, ox + b + ext, oy + h - t)
        for xe in (ox - ext, ox + b + ext):                    # nét cắt sàn
            D.break_line(xe, oy + h - t, xe, oy + h)
    else:
        D.rect(ox, oy, b, h)
    c = cover + ds / 2                                       # đường tim cốt đai
    rounded_rect(D, ox + c, oy + c, ox + b - c, oy + h - c, 2 * ds)
    if st["legs"] >= 4:                                      # đai trong cho dầm rộng
        D.rect(ox + b / 3, oy + c, b / 3, h - 2 * c, "THEP_DAI")

    groups = {}
    for face in ("top", "bot"):
        fl = layout[face]
        pf = place_face(b, cover, ds, fl["cont"], fl["add"][zone], face)
        for tb in pf["bars"]:
            x = ox + tb["x"]
            y = oy + h - tb["y"] if face == "top" else oy + tb["y"]
            D.circle(x, y, tb["d"] / 2, "THEP", filled=True)
            m = _mark(marks, "bar", face, tb["group"], zone)
            groups.setdefault((face, m["mark"]), (m, []))[1].append((x, y))

    xt = ox + b + ext + 4 * S                                # đầu các gạch ghi chú
    def rep(face, pts):                                      # thanh đại diện: bên phải nhất, sát mép nhất
        return max(pts, key=lambda p: (round(p[0]), p[1] if face == "top" else -p[1]))
    tops = [(f"{len(p)}Ø{m['d']}", m["mark"], rep("top", p)) for (f, _), (m, p) in groups.items() if f == "top"]
    bots = [(f"{len(p)}Ø{m['d']}", m["mark"], rep("bot", p)) for (f, _), (m, p) in groups.items() if f == "bot"]
    _tags_ortho(D, tops, xt, oy + h + 4 * S, 6 * S, up=True)
    n_bot = _tags_ortho(D, bots, xt, oy - 4 * S, 6 * S, up=False)

    # thép cấu tạo mặt bên + cốt đai: gạch ngang đi thẳng từ mặt bên phải
    m_st = _mark(marks, "stir", "", "outer", zone)
    s_z = st["s_mid"] if zone == "M" else st["s_end"]
    y_st = oy + 0.62 * h
    if side_y:
        m = _mark(marks, "bar", "side", "side", zone)
        for y in side_y:
            for x in (ox + cover + ds + side_d / 2, ox + b - cover - ds - side_d / 2):
                D.circle(x, oy + y, side_d / 2, "THEP", filled=True)
        ys = oy + side_y[len(side_y) // 2]
        D.tag2(xt, ys, f"{2 * len(side_y)}Ø{side_d}", m["mark"], [(ox + b - cover - ds - side_d / 2, ys, 0)])
        if abs(y_st - ys) < 6 * S:
            y_st = ys + 7 * S
    D.tag2(xt, y_st, f"Ø{ds}a{s_z:.0f}", m_st["mark"], [(ox + b - c, y_st, 0)])

    # kích thước: chỉ kích thước tổng (và chiều dày sàn) như bản vẽ mẫu
    D.dim((ox, oy), (ox, oy + h), (ox - ext - 10 * S, oy), vertical=True)
    if t:
        D.dim((ox, oy + h - t), (ox, oy + h), (ox - ext - 4 * S, oy), vertical=True)
    yd = oy - 4 * S - max(max(n_bot, bot_rows) - 1, 0) * 6 * S - 5 * S     # cùng cao độ ở cả 3 mặt cắt
    D.dim((ox, oy), (ox + b, oy), (ox, yd))
    section_title(D, ox + b / 2, yd - 6 * S, no, D.S)


def legend(D, x, y, marks):
    S = D.S
    D.text(x, y, "GHI CHÚ SỐ HIỆU THÉP", 3.0, "TITLE")
    for i, m in enumerate(marks):
        yy = y - 8 * S - i * 6.5 * S
        D.bubble(x + 2.6 * S, yy, m["mark"])
        spec = f"{m['n']}Ø{m['d']}" if m["kind"] == "bar" else f"Ø{m['d']}"
        D.text(x + 7 * S, yy, f"{spec}  –  {m['desc']}", 2.5, "TEXT", "left", "middle")


def beam_sheet(res, sec, scale=10, cover=25, det=None, slab_t=0, axes=None, level=None, es=25):
    """scale = tỉ lệ mặt cắt ngang (1:10), es = tỉ lệ mặt cắt dọc (1:25)."""
    """1 dầm = mặt cắt dọc 1:25 (nếu có det) + 3 mặt cắt ngang 1:10 + bảng thống kê thép + ghi chú.
    slab_t: chiều dày sàn để vẽ cánh sàn ở mặt cắt ngang (0 = không vẽ)."""
    from .schedule import steel_table, notes, beam_rows, general_notes
    S = scale
    b, h = sec["b"], sec["h"]
    layout = res["layout"]
    from core.beam_detailing import side_bars
    side_y, side_d = side_bars(b, h, cover, layout["stirrup"]["d"], layout)
    marks = beam_marks(layout, (2 * len(side_y), side_d) if side_y else None)
    secs = Drawing(scale)
    gap = b + (0.9 * b if slab_t else 0) + 55 * S
    bot_rows = max(1 + (layout["bot"]["add"][z][0] > 0) for z in ZONES)
    for i, z in enumerate(ZONES):
        draw_beam_section(secs, i * gap, 0, b, h, cover, layout, z, marks, i + 1, side_y, side_d, slab_t, bot_rows)

    if det is None:
        D = Drawing(scale)
        D.merge(secs)
        top = secs.bbox()[3]
        sx0, sy0, sx1, sy1 = secs.bbox()
        k, ox, oy = 1.0, 0.0, 0.0
    else:
        # mặt cắt dọc 1:25 ở trên; mặt cắt ngang 1:10 phóng 2.5 lần đặt bên dưới
        from .elevation import beam_elevation
        ES = es
        k = ES / scale
        E = beam_elevation(res, sec, det, marks, ES, cover, axes, level)
        D = Drawing(ES)
        D.merge(E)
        ex0, ey0, ex1, ey1 = E.bbox()
        sx0, sy0, sx1, sy1 = secs.bbox()
        ox, oy = ex0 - sx0 * k, ey0 - 15 * ES - sy1 * k
        D.merge(secs, ox, oy, k)
        top = ey1
        S = ES
    # dưới các mặt cắt: ghi chú số hiệu + ghi chú chung; bên phải: bảng thống kê thép
    left, bottom, right = ox + sx0 * k, oy + sy0 * k, ox + sx1 * k
    legend(D, left, bottom - 10 * S, marks)
    notes(D, left + 150 * S, bottom - 10 * S, general_notes(sec["material"], cover))
    if det is not None:
        steel_table(D, right + 20 * S, oy + sy1 * k, beam_rows(det, marks, b, h, cover),
                    f"BẢNG THỐNG KÊ CỐT THÉP DẦM {res['label']}")
    status = "ĐẠT" if res["ok"] else "KHÔNG ĐẠT"
    where = story_vn(res["story"]).upper()
    if axes and axes[2]:                                   # vị trí theo lưới trục: trục dầm + nhịp giữa 2 trục
        span = f", NHỊP {axes[0]}–{axes[1]}" if axes[0] and axes[1] else ""
        where = f"TRỤC {axes[2]}{span} – {where}"
    D.text(-20 * S, top + 20 * S, f"DẦM {res['label']} – {where} – {res['section']} "
           f"({b:.0f}×{h:.0f}), L = {res['L']:.0f} mm", 5.0, "TITLE")
    D.text(-20 * S, top + 13 * S, f"Bê tông {sec['material']}, thép CB400-V, đai CB240-T – TCVN 5574:2018 – "
           f"hệ số sử dụng {res['util']:.3f} ({status})", 2.8, "TEXT")
    return D


# ============================================================================ CỘT
def column_section_simple(b, h, cover, dt, bars, d, tags, scale, hollow=(), d_hollow=0, outer=None):
    """Mặt cắt cột kiểu bản vẽ thi công (giống bản vẽ mẫu): bê tông, khung đai, thép dọc chấm đặc;
    ghi chú bên phải bằng đường dẫn vuông góc; chỉ ghi kích thước tổng b, h.
    tags = [(chữ, số hiệu, "bars" | "tie")]."""
    D = Drawing(scale)
    S = scale
    x0, y0 = -b / 2, -h / 2
    D.rect(x0, y0, b, h)
    c = cover + dt / 2
    rounded_rect(D, x0 + c, y0 + c, -x0 - c, -y0 - c, 2 * dt)
    for tb in bars:
        D.circle(tb["z"], tb["y"], d / 2, "THEP", filled=True)
    corner = max(bars, key=lambda t: (round(t["z"]), t["y"]))           # thanh góc trên phải
    xt = -x0 + 5 * S
    for label, mark, kind in tags:
        if kind == "bars":
            D.tag2(xt, -y0 + 4 * S, label, mark, [(corner["z"], corner["y"], 0)])
        elif kind == "tie":
            D.tag2(xt, 0.25 * h, label, mark, [(-x0 - c, 0.25 * h, 0)])
    D.dim((x0, y0), (x0, -y0), (x0 - 8 * S, y0), vertical=True)         # trái: cạnh h
    D.dim((x0, y0), (-x0, y0), (x0, y0 - 7 * S))                        # dưới: cạnh b
    return D


def column_sheet(res, sec, scale=10, cover=30, zone=None, compact=False, tie_mark=2):
    """zone: "end" (đầu cột, đai dày) | "mid" (giữa cột, đai thưa) | None (ghi cả 2).
    compact=True: mặt cắt kiểu bản vẽ thi công (dùng khi đặt cạnh mặt cắt dọc)."""
    if compact:
        L = res["layout"]
        tie = L["tie"]
        bars = bar_positions(sec["b"], sec["h"], cover, tie["d"], L["d"], L["nb"], L["nh"])
        sp = {"end": tie["s_end"], "mid": tie["s_mid"]}.get(zone)
        if not sp and tie["s_end"] == tie["s_mid"]:
            sp = tie["s_mid"]
        tie_txt = f"Đai Ø{tie['d']}a{sp}" if sp else f"Đai Ø{tie['d']}a{tie['s_end']}/{tie['s_mid']}"
        return column_section_simple(sec["b"], sec["h"], cover, tie["d"], bars, L["d"],
                                     [(f"{len(bars)}Ø{L['d']}", 1, "bars"), (tie_txt.replace("Đai ", ""), tie_mark, "tie")],
                                     scale)
    # bản vẽ cột đầy đủ (bản vẽ theo tầng, xem trước trong app): mặt cắt + tên + thông tin cột
    D = column_sheet(res, sec, scale, cover, zone=zone, compact=True)   # 1 = thép dọc, 2 = đai
    S = scale
    x0, y0, x1, y1 = D.bbox()
    D.text(0, y0 - 3 * S, f"MẶT CẮT CỘT {res['label']} – {story_vn(res['story']).upper()}", 3.5, "TITLE", "center", "top")
    D.text(0, y0 - 8 * S, f"1 : {scale:.0f}", 3.0, "TEXT", "center", "top")
    status = "ĐẠT" if res["ok"] else "KHÔNG ĐẠT"
    D.text(x0, y1 + 12 * S, f"CỘT {res['label']} – {story_vn(res['story']).upper()} – {res['section']} "
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
