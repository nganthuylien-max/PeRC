"""Triển khai thép dầm theo chiều dài: neo, cắt thép, chia vùng đai.
Dùng CHUNG cho bản vẽ mặt cắt dọc và bóc khối lượng -> 2 kết quả luôn khớp nhau.

Quy ước (thực hành cấu tạo, TCVN 5574:2018 mục 10.3.5 về neo cốt thép):
- Gối = cột (hoặc vách) ở 2 đầu dầm; Lc = nhịp thông thủy = L - nửa bề rộng 2 gối.
- Thép chạy suốt: đi hết nhịp, neo vào gối: đoạn thẳng (bề rộng gối - lớp bảo vệ)
  + đoạn bẻ móc, tổng chiều dài neo không nhỏ hơn 40d (móc tối thiểu 10d).
- Thép gia cường thớ trên ở gối: từ trong gối vươn ra nhịp Lc/4 + 20d.
- Thép gia cường thớ dưới giữa nhịp: từ 0.15Lc đến 0.85Lc.
- Thép gia cường thớ dưới ở gối: neo vào gối như thép suốt, vươn ra nhịp Lc/4 + 20d.
- Đai: vùng đầu dầm dài Lc/4 dùng bước s_end, giữa dùng s_mid, đai đầu tiên cách mép gối 50 mm."""
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
    """Bề rộng gối ở 2 đầu mỗi dầm: tìm cột có đỉnh trùng đầu dầm, hoặc vách đi qua đầu dầm."""
    secs, asec = project["frame_sections"], project["area_sections"]
    cols = {}
    for c in project["columns"]:                                # cột theo tầng: (tâm x, tâm y, b, h)
        s = secs[c["section"]]
        cols.setdefault(c["story"], []).append((c["j"][0], c["j"][1], s["b"], s["h"]))
    walls = {}
    for w in project["walls"]:
        xy = sorted({(round(p[0]), round(p[1])) for p in w["points"]})
        if len(xy) == 2:
            walls.setdefault(w["story"], []).append((xy[0], xy[1], asec[w["section"]]["thickness"]))

    def at(story, pt):
        x, y = round(pt[0]), round(pt[1])
        for cx, cy, cb, ch in cols.get(story, []):               # đầu dầm nằm trong tiết diện cột?
            if abs(x - cx) <= max(cb, ch) / 2 + 1 and abs(y - cy) <= max(cb, ch) / 2 + 1:
                return max(cb, ch), "cột"
        for (x1, y1), (x2, y2), t in walls.get(story, []):       # điểm nằm trên đoạn vách?
            if min(x1, x2) - 1 <= x <= max(x1, x2) + 1 and min(y1, y2) - 1 <= y <= max(y1, y2) + 1 \
                    and abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) < 1e-3 * math.hypot(x2 - x1, y2 - y1) * 1000:
                return t, "vách"
        return DEFAULT_SUPPORT, "dầm"

    return {b["id"]: (at(b["story"], b["i"]), at(b["story"], b["j"])) for b in project["beams"]}


def detail_beam(res, sec, supports, cover=COVER):
    """Trả về {Lc, hL, hR, bars:[...], stirrups:[...]}; tọa độ x = 0 tại mép gối trái."""
    (hL, kL), (hR, kR) = supports
    L, b, h = res["L"], sec["b"], sec["h"]
    Lc = max(L - hL / 2 - hR / 2, 0.5 * L)
    lay = res["layout"]
    st = lay["stirrup"]
    ds = st["d"]

    def anchored(d, h_sup):
        """Đoạn thẳng trong gối + móc: tổng >= 40d."""
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
        sL, hkL = anchored(d, hL)
        sR, hkR = anchored(d, hR)
        add((face, "cont"), n, d, face, -sL, Lc + sR, hkL, hkR)

    # gia cường thớ trên ở 2 gối
    for z, side in (("L", -1), ("R", 1)):
        n, d = lay["top"]["add"][z]
        s_, hk = anchored(d, hL if z == "L" else hR)
        reach = Lc / 4 + EXTEND * d
        if z == "L":
            add(("top", "add", "L"), n, d, "top", -s_, reach, hk, 0, layer=2)
        else:
            add(("top", "add", "R"), n, d, "top", Lc - reach, Lc + s_, 0, hk, layer=2)
    # gia cường thớ dưới giữa nhịp
    n, d = lay["bot"]["add"]["M"]
    add(("bot", "add", "M"), n, d, "bot", 0.15 * Lc, 0.85 * Lc, 0, 0, layer=2)
    # gia cường thớ dưới ở gối (khi có mômen dương ở gối)
    for z in ("L", "R"):
        n, d = lay["bot"]["add"][z]
        if n:
            s_, hk = anchored(d, hL if z == "L" else hR)
            reach = Lc / 4 + EXTEND * d
            x0, x1 = (-s_, reach) if z == "L" else (Lc - reach, Lc + s_)
            add(("bot", "add", z), n, d, "bot", x0, x1, hk if z == "L" else 0, hk if z == "R" else 0, layer=2)

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
    return {"Lc": Lc, "hL": hL, "hR": hR, "kind_L": kL, "kind_R": kR, "bars": bars, "stirrups": stirrups}
