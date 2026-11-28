"""Triển khai thép dầm theo chiều dài: neo, cắt thép, chia vùng đai.
Dùng CHUNG cho bản vẽ mặt cắt dọc và bóc khối lượng -> 2 kết quả luôn khớp nhau.

Quy ước (thực hành cấu tạo, TCVN 5574:2018 mục 10.3.5 về neo cốt thép):
- Gối = cột (hoặc vách) ở 2 đầu dầm; Lc = nhịp thông thủy = L - nửa bề rộng 2 gối.
- Thép chạy suốt: đi hết nhịp, neo vào gối: đoạn thẳng (bề rộng gối - lớp bảo vệ)
  + đoạn bẻ móc, tổng chiều dài neo không nhỏ hơn 40d (móc tối thiểu 10d).
- Thép gia cường thớ trên ở gối: từ trong gối vươn ra nhịp Lc/4 + 20d.
- Thép gia cường thớ dưới giữa nhịp: từ 0.15Lc đến 0.85Lc.
- Thép gia cường thớ trên giữa nhịp (nếu có): từ Lc/4 - 20d đến 3Lc/4 + 20d.
- Thép gia cường thớ dưới ở gối: neo vào gối như thép suốt, vươn ra nhịp Lc/4 + 20d.
- Đai: vùng đầu dầm dài Lc/4 dùng bước s_end, giữa dùng s_mid, đai đầu tiên cách mép gối 50 mm.
- Dầm cao > 700 mm: thép cấu tạo 2 mặt bên, cách nhau theo chiều cao <= 400 mm."""
import math

ANCHOR = 40          # chiều dài neo tính theo d
HOOK_MIN = 10        # móc tối thiểu
EXTEND = 20          # đoạn kéo dài thêm của thép gia cường
COVER = 25
DEFAULT_SUPPORT = 300   # bề rộng gối khi đầu dầm không gặp cột/vách (gối lên dầm khác)


def unit_weight(d):
    """Khối lượng 1 m thép đường kính d (kg/m) = 0.00617·d²."""
    return 0.00617 * d * d


def find_supports(project):
    """Gối ở 2 đầu mỗi dầm -> (bề rộng gối theo phương dầm, loại, chiều cao gối):
    cột có đỉnh trùng đầu dầm; vách đi qua đầu dầm; hoặc dầm khác (dầm chính) đỡ đầu dầm."""
    secs, asec = project["frame_sections"], project["area_sections"]
    cols = {}
    for c in project["columns"]:                                # cột theo tầng: (tâm x, tâm y, b, h)
        if not c.get("j") or c["section"] not in secs:
            continue
        s = secs[c["section"]]
        cols.setdefault(c["story"], []).append((c["j"][0], c["j"][1], s["b"], s["h"]))
    walls = {}
    for w in project["walls"]:
        xy = sorted({(round(p[0]), round(p[1])) for p in w["points"]})
        if len(xy) == 2:
            walls.setdefault(w["story"], []).append((xy[0], xy[1], asec[w["section"]]["thickness"]))
    beams = {}
    for bm in project["beams"]:
        if not bm.get("i") or not bm.get("j"):
            continue
        s = secs.get(bm["section"], {})
        beams.setdefault(bm["story"], []).append((bm["id"], bm["i"][:2], bm["j"][:2], s.get("b", 0), s.get("h", 0)))

    def on_segment(x, y, x1, y1, x2, y2, tol=1.0):
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-6:
            return False
        t = ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / (L * L)
        dist = abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) / L
        return -tol / L <= t <= 1 + tol / L and dist <= tol

    def at(bid, story, pt, other):
        if not pt or not other:                                  # thiếu tọa độ nút -> gối mặc định
            return DEFAULT_SUPPORT, "dầm", 0
        x, y = round(pt[0]), round(pt[1])
        for cx, cy, cb, ch in cols.get(story, []):               # đầu dầm nằm trong tiết diện cột?
            if abs(x - cx) <= max(cb, ch) / 2 + 1 and abs(y - cy) <= max(cb, ch) / 2 + 1:
                return max(cb, ch), "cột", 0
        for (x1, y1), (x2, y2), t in walls.get(story, []):       # điểm nằm trên đoạn vách?
            if on_segment(x, y, x1, y1, x2, y2):
                return t, "vách", 0
        ux, uy = other[0] - pt[0], other[1] - pt[1]
        for gid, (x1, y1), (x2, y2), gb, gh in beams.get(story, []):   # dầm chính (không cùng phương) đỡ đầu dầm
            if gid == bid or not on_segment(x, y, x1, y1, x2, y2):
                continue
            cross = abs(ux * (y2 - y1) - uy * (x2 - x1)) / (math.hypot(ux, uy) * math.hypot(x2 - x1, y2 - y1) + 1e-9)
            if cross > 0.5:                                      # góc giữa 2 dầm > 30°
                return gb, "dầm", gh
        for gid, (x1, y1), (x2, y2), gb, gh in beams.get(story, []):   # chỉ có dầm cùng phương nối tiếp:
            if gid != bid and (math.dist((x, y), (x1, y1)) < 2 or math.dist((x, y), (x2, y2)) < 2):
                return 0, "liên tục", 0                          # dầm liên tục qua điểm chia, không có gối
        return DEFAULT_SUPPORT, "dầm", 0

    return {b["id"]: (at(b["id"], b["story"], b["i"], b["j"]), at(b["id"], b["story"], b["j"], b["i"]))
            for b in project["beams"]}


SIDE_MIN_H = 700     # dầm cao hơn 700 mm: đặt thép cấu tạo ở 2 mặt bên (quy định cấu tạo dầm, TCVN 5574:2018)
SIDE_MAX_S = 400     # khoảng cách theo chiều cao giữa các thanh <= 400 mm


def side_bars(b, h, cover, ds, lay):
    """Thép cấu tạo mặt bên (thép giá) cho dầm cao > 700 mm.
    Diện tích 1 thanh >= 0.1% · s · min(b/2, 200), s = khoảng cách theo chiều cao (<= 400).
    Trả về (danh sách cao độ y đo từ đáy dầm, đường kính) – mỗi cao độ có 2 thanh (2 mặt bên)."""
    if h <= SIDE_MIN_H:
        return [], 0
    y0 = cover + ds + lay["bot"]["cont"][1] / 2
    y1 = h - cover - ds - lay["top"]["cont"][1] / 2
    n = max(math.ceil((y1 - y0) / SIDE_MAX_S) - 1, 1)
    s = (y1 - y0) / (n + 1)
    need = 0.001 * s * min(b / 2, 200)
    d = next(d for d in (10, 12, 14, 16, 18, 20) if math.pi * d * d / 4 >= need)
    return [y0 + s * (i + 1) for i in range(n)], d


def detail_beam(res, sec, supports, cover=COVER):
    """Trả về {Lc, hL, hR, bars:[...], stirrups:[...]}; tọa độ x = 0 tại mép gối trái."""
    (hL, kL), (hR, kR) = supports[0][:2], supports[1][:2]
    L, b, h = res["L"], sec["b"], sec["h"]
    Lc = max(L - hL / 2 - hR / 2, 0.5 * L)
    lay = res["layout"]
    st = lay["stirrup"]
    ds = st["d"]

    def anchored(d, h_sup, kind="cột"):
        """Đoạn thẳng trong gối + móc: tổng >= 40d. Đầu dầm liên tục (không có gối): kéo thẳng 40d
        sang nhịp bên cạnh để nối chồng, không bẻ móc."""
        if kind == "liên tục":
            return ANCHOR * d, 0
        straight = max(h_sup - cover, 0)
        hook = max(ANCHOR * d - straight, HOOK_MIN * d)
        return straight, hook

    bars = []

    def add(mark_key, n, d, face, x0, x1, hook0, hook1, layer=1):
        if n <= 0:
            return
        length = (x1 - x0) + hook0 + hook1
        bars.append({"key": mark_key, "n": n, "d": d, "face": face, "x0": x0, "x1": x1,
                     "hook0": hook0, "hook1": hook1, "layer": layer, "length": length,
                     "weight": n * length / 1000 * unit_weight(d)})

    for face in ("top", "bot"):
        n, d = lay[face]["cont"]
        sL, hkL = anchored(d, hL, kL)
        sR, hkR = anchored(d, hR, kR)
        add((face, "cont"), n, d, face, -sL, Lc + sR, hkL, hkR)

    # gia cường thớ trên ở 2 gối
    for z, side in (("L", -1), ("R", 1)):
        n, d = lay["top"]["add"][z]
        s_, hk = anchored(d, hL if z == "L" else hR, kL if z == "L" else kR)
        reach = Lc / 4 + EXTEND * d
        if z == "L":
            add(("top", "add", "L"), n, d, "top", -s_, reach, hk, 0, layer=2)
        else:
            add(("top", "add", "R"), n, d, "top", Lc - reach, Lc + s_, 0, hk, layer=2)
    # gia cường thớ trên giữa nhịp (khi mômen âm lớn kéo dài vào giữa nhịp): phủ vùng giữa + 20d mỗi bên
    n, d = lay["top"]["add"]["M"]
    add(("top", "add", "M"), n, d, "top", max(0.0, Lc / 4 - EXTEND * d), min(Lc, 3 * Lc / 4 + EXTEND * d), 0, 0, layer=2)
    # gia cường thớ dưới giữa nhịp
    n, d = lay["bot"]["add"]["M"]
    add(("bot", "add", "M"), n, d, "bot", 0.15 * Lc, 0.85 * Lc, 0, 0, layer=2)
    # gia cường thớ dưới ở gối (khi có mômen dương ở gối)
    for z in ("L", "R"):
        n, d = lay["bot"]["add"][z]
        if n:
            s_, hk = anchored(d, hL if z == "L" else hR, kL if z == "L" else kR)
            reach = Lc / 4 + EXTEND * d
            x0, x1 = (-s_, reach) if z == "L" else (Lc - reach, Lc + s_)
            add(("bot", "add", z), n, d, "bot", x0, x1, hk if z == "L" else 0, hk if z == "R" else 0, layer=2)

    # thép cấu tạo mặt bên (dầm cao > 700): chạy suốt, neo thẳng vào gối
    ys, d = side_bars(b, h, cover, ds, lay)
    if ys:
        add(("side", "side"), 2 * len(ys), d, "side", -max(hL - cover, 0), Lc + max(hR - cover, 0), 0, 0)

    # cốt đai theo vùng
    per = 2 * (b - 2 * cover) + 2 * (h - 2 * cover) + 2 * 10 * ds      # chu vi + 2 móc 135° (~10d)
    if st["legs"] >= 4:
        per += 2 * (b / 3) + 2 * (h - 2 * cover) + 2 * 10 * ds         # đai trong
    stirrups = []
    for name, x0, x1, s in (("Đầu trái", 50, Lc / 4, st["s_end"]), ("Giữa", Lc / 4, 3 * Lc / 4, st["s_mid"]),
                            ("Đầu phải", 3 * Lc / 4, Lc - 50, st["s_end"])):
        cnt = max(int((x1 - x0) // s) + (1 if name != "Giữa" else 0), 0)
        stirrups.append({"zone": name, "x0": x0, "x1": x1, "s": s, "count": cnt, "d": ds,
                         "length": per, "weight": cnt * per / 1000 * unit_weight(ds)})
    return {"Lc": Lc, "hL": hL, "hR": hR, "kind_L": kL, "kind_R": kR, "bars": bars, "stirrups": stirrups,
            "depth_L": supports[0][2] if len(supports[0]) > 2 else 0,
            "depth_R": supports[1][2] if len(supports[1]) > 2 else 0, "side_y": ys}
