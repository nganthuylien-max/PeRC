"""Bóc tách khối lượng bê tông, ván khuôn, cốt thép cho dầm, cột, sàn, vách.

Quy tắc đo bóc (đơn giản hóa, ghi rõ để giải trình):
- Cột : bê tông b·h·H (H = chiều cao tầng, tính hết qua nút dầm–sàn);
        ván khuôn chu vi × H; thép dọc nối chồng 40d mỗi tầng; đai theo vùng đầu cột / giữa cột.
- Dầm : tính phần DƯỚI sàn: b·(h − t_sàn)·Lc, Lc = nhịp thông thủy giữa 2 gối;
        ván khuôn đáy + 2 thành: (b + 2(h − t_sàn))·Lc; thép lấy từ beam_detailing (khớp bản vẽ).
- Sàn : bê tông = diện tích sàn − diện tích cột, vách chiếm chỗ, × chiều dày
        (phần sàn trên dầm tính cho sàn vì dầm đã tính phần dưới sàn);
        ván khuôn = diện tích trên − thêm phần đáy dầm; thép theo bố trí mặc định (kg/m²).
- Vách: bê tông = diện tích mặt đứng × chiều dày; ván khuôn 2 mặt; thép theo bố trí mặc định.
Thép chia theo nhóm đường kính dùng trong định mức: d ≤ 10, d ≤ 18, d > 18 mm."""
import math
from collections import Counter, defaultdict

from core.column_design import crossties
from core.beam_detailing import detail_beam, unit_weight
from core.column_section import bar_positions

LAP = 40   # nối chồng thép dọc cột (theo d)


def group_of(d):
    return "d≤10" if d <= 10 else ("d≤18" if d <= 18 else "d>18")


def mesh_kg_m2(d, s, layers, dirs=2, extra=1.10):
    """Lưới thép: số lớp × số phương × (1000/s thanh mỗi m) × kg/m; +10% nối, móc."""
    return layers * dirs * (1000 / s) * unit_weight(d) * extra


DEFAULTS = {
    "slab": {"d": 10, "s": 200, "layers": 2},                     # sàn: Ø10a200, 2 lớp, 2 phương
    "wall_v": {"d": 14, "s": 200, "layers": 2},                   # vách: thép đứng Ø14a200, 2 lớp
    "wall_h": {"d": 10, "s": 200, "layers": 2},                   # vách: thép ngang Ø10a200, 2 lớp
}


class Book:
    """Sổ khối lượng: (tầng, cấu kiện) -> bê tông, ván khuôn, thép theo nhóm + dòng diễn giải."""
    def __init__(self):
        self.q = defaultdict(lambda: {"concrete": 0.0, "formwork": 0.0,
                                      "steel": defaultdict(float), "notes": [], "details": []})

    def detail(self, story, elem, work, text, value, group=None):
        """Dòng diễn giải: work = concrete | formwork | steel (group = nhóm đường kính), value theo đơn vị
        của công tác (m³, m², kg)."""
        self.q[(story, elem)]["details"].append({"work": work, "group": group, "text": text, "value": value})

    def add(self, story, elem, concrete=0.0, formwork=0.0, steel=None, note=None):
        r = self.q[(story, elem)]
        r["concrete"] += concrete
        r["formwork"] += formwork
        for g, kg in (steel or {}).items():
            r["steel"][g] += kg
        if note:
            r["notes"].append(note)

    def rows(self):
        out = []
        for (story, elem), r in self.q.items():
            out.append({"story": story, "element": elem, "concrete": r["concrete"],
                        "formwork": r["formwork"], "steel": dict(r["steel"]), "notes": r["notes"],
                        "details": r["details"]})
        return out


def slab_thickness_by_story(p):
    """Chiều dày sàn phổ biến nhất mỗi tầng (bỏ ô sàn diện tích 0 hoặc dày 0)."""
    t = {}
    for story, secs in _group(p["slabs"], "story").items():
        secs = [s for s in secs if s["area"] > 0 and p["area_sections"][s["section"]]["thickness"] > 0]
        if secs:
            name = Counter(s["section"] for s in secs).most_common(1)[0][0]
            t[story] = p["area_sections"][name]["thickness"]
    return t


def _group(items, key):
    g = defaultdict(list)
    for it in items:
        g[it[key]].append(it)
    return g


COL_HOOK = 12     # móc thép cột ở chân móng / đỉnh mái (theo d) – khớp bản vẽ mặt cắt dọc cột


def column_items(r, s, first_story, cover_col=30, top_story=False):
    """Thép của 1 cột 1 tầng, dùng CHUNG cho bóc khối lượng và bảng thống kê trên bản vẽ:
    [{"mark", "kind", "d", "n", "length" (mm), "shape"}].
    Thép dọc: chân tầng 1 neo xuống móng 40d + móc 12d; tầng trên cùng dừng dưới đỉnh mái + móc 12d;
    các tầng khác vươn lên tầng trên 1 đoạn nối chồng (như bản vẽ)."""
    L = r["layout"]
    d, dt, tie = L["d"], L["tie"]["d"], L["tie"]
    lap = tie.get("lap", LAP * d)
    hk0 = COL_HOOK * d if first_story else 0
    bot = LAP * d if first_story else 0                                          # neo xuống móng
    if top_story:
        straight, hk1 = bot + r["L"] - cover_col - d / 2, COL_HOOK * d
    else:
        straight, hk1 = bot + r["L"] + lap, 0
    items = [{"mark": 1, "kind": "long", "d": d, "n": r["n_bars"], "length": round(straight + hk0 + hk1),
              "shape": ("bar", hk0, round(straight), hk1, False)}]
    bw, bh = s["b"] - 2 * cover_col, s["h"] - 2 * cover_col
    per = 2 * bw + 2 * bh + 20 * dt                                              # đai chu vi + 2 móc
    # đai móc giằng theo 10.3.4.5 (thanh cách thanh, chỗ uốn cách nhau <= 400 mm)
    cb = crossties(L["nb"], s["b"], cover_col, dt, d)
    ch = crossties(L["nh"], s["h"], cover_col, dt, d)
    # số đai: vùng nối chồng (s_lap) + phần còn lại (s_mid); thiết kế cũ có vùng đầu cột s_end
    lap = tie.get("lap", 0) if not first_story else 0
    s_lap = min(tie.get("s_lap", tie["s_end"]), tie["s_end"])
    l_end = max(s["b"], s["h"], r["L"] / 6, 500) if tie["s_end"] < tie["s_mid"] else 0
    cnt = (math.ceil(lap / s_lap) + math.ceil(l_end / tie["s_end"])
           + math.ceil(max(r["L"] - lap - l_end, 0) / tie["s_mid"]))
    items.append({"mark": 2, "kind": "tie", "d": dt, "n": cnt, "length": per, "shape": ("stir", bw, bh, 10 * dt)})
    if cb:
        items.append({"mark": 3, "kind": "cross", "face": "b", "d": dt, "n": cnt * cb, "length": bh + 20 * dt,
                      "shape": ("bar", 10 * dt, bh, 10 * dt, True)})
    if ch:
        items.append({"mark": 3 if not cb else 4, "kind": "cross", "face": "h", "d": dt, "n": cnt * ch, "length": bw + 20 * dt,
                      "shape": ("bar", 10 * dt, bw, 10 * dt, True)})
    for it in items:
        it["kg"] = it["n"] * it["length"] / 1e3 * unit_weight(it["d"])
    return items


def takeoff(p, beams_res, cols_res, supports, opt=DEFAULTS, cover_col=30):
    fs, asec = p["frame_sections"], p["area_sections"]
    t_slab = slab_thickness_by_story(p)
    book = Book()

    def steel_lines(story, elem, who, parts):
        """parts: {(nhóm, loại thép): kg} -> diễn giải cốt thép."""
        import re
        dia = lambda k: int(re.search(r"Ø(\d+)", k[1]).group(1))   # xếp theo loại thép rồi đường kính tăng dần
        for (g, kind), kg in sorted(parts.items(), key=lambda kv: (kv[0][1].split(" Ø")[0], dia(kv[0]))):
            book.detail(story, elem, "steel", f"{who} – {kind}: {kg:.1f} kg", kg, g)

    # ---------------------------------------------------------------- CỘT
    first_story = p["stories"][0]["name"]                # tầng dưới cùng: không có nối chồng ở chân cột
    order = {st["name"]: i for i, st in enumerate(p["stories"])}
    top_of = {}                                          # tầng cao nhất của từng trục cột
    for r in cols_res:
        if order.get(r["story"], -1) > order.get(top_of.get(r["label"]), -1):
            top_of[r["label"]] = r["story"]
    for story, cols in _group(cols_res, "story").items():
        by_sec = defaultdict(lambda: [0, 0.0])
        sec_steel = defaultdict(lambda: defaultdict(float))
        for r in cols:
            s = fs[r["section"]]
            b, h, H = s["b"] / 1e3, s["h"] / 1e3, r["L"] / 1e3
            steel = defaultdict(float)
            items = column_items(r, s, story == first_story, cover_col, top_of.get(r["label"]) == story)
            d, dt = items[0]["d"], items[1]["d"]
            kg_long = items[0]["kg"]
            kg_tie = sum(it["kg"] for it in items[1:])
            steel[group_of(d)] += kg_long
            steel[group_of(dt)] += kg_tie
            book.add(story, "Cột", b * h * H, 2 * (b + h) * H, steel)
            key = (r["section"], b, h, H)
            by_sec[key][0] += 1
            sec_steel[key][(group_of(d), f"thép dọc Ø{d}")] += kg_long
            sec_steel[key][(group_of(dt), f"cốt đai Ø{dt}")] += kg_tie
        for key, (cnt, _) in by_sec.items():
            name, b, h, H = key
            v = cnt * b * h * H
            book.add(story, "Cột", note=f"{cnt} cột {name}: {cnt} × {b:.2f} × {h:.2f} × {H:.2f} = {v:.3f} m³")
            book.detail(story, "Cột", "concrete", f"{cnt} cột {name}: {cnt} × {b:.2f} × {h:.2f} × {H:.2f}", v)
            fw = cnt * 2 * (b + h) * H
            book.detail(story, "Cột", "formwork", f"{cnt} cột {name}: {cnt} × 2 × ({b:.2f} + {h:.2f}) × {H:.2f}", fw)
            steel_lines(story, "Cột", f"{cnt} cột {name}", sec_steel[key])

    # ---------------------------------------------------------------- DẦM
    beam_fp = defaultdict(float)                         # diện tích đáy dầm theo tầng (để trừ ván khuôn sàn)
    no_steel = 0
    for story, bms in _group(beams_res, "story").items():
        t = t_slab.get(story, 0) / 1e3
        by_sec = defaultdict(lambda: [0, 0.0])
        sec_steel = defaultdict(lambda: defaultdict(float))
        no_steel_story = 0
        for r in bms:
            s = fs[r["section"]]
            b, h = s["b"] / 1e3, s["h"] / 1e3
            hL, hR = supports[r["id"]][0][0], supports[r["id"]][1][0]
            Lc = max(r["L"] - hL / 2 - hR / 2, 0.5 * r["L"]) / 1e3
            steel = defaultdict(float)
            if r["layout"]:
                det = detail_beam(r, s, supports[r["id"]])
                Lc = det["Lc"] / 1e3
                k_sec = (r["section"], s["b"] / 1e3, s["h"] / 1e3)
                for bar in det["bars"]:
                    steel[group_of(bar["d"])] += bar["weight"]
                    sec_steel[k_sec][(group_of(bar["d"]), f"thép dọc Ø{bar['d']}")] += bar["weight"]
                for st in det["stirrups"]:
                    steel[group_of(st["d"])] += st["weight"]
                    sec_steel[k_sec][(group_of(st["d"]), f"cốt đai Ø{st['d']}")] += st["weight"]
            else:
                no_steel += 1
                no_steel_story += 1
            book.add(story, "Dầm", b * (h - t) * Lc, (b + 2 * (h - t)) * Lc, steel)
            beam_fp[story] += b * Lc
            by_sec[(r["section"], b, h)][0] += 1
            by_sec[(r["section"], b, h)][1] += Lc
        for (name, b, h), (cnt, sumL) in by_sec.items():
            v = b * (h - t) * sumL
            book.add(story, "Dầm", note=f"{cnt} dầm {name}: {b:.2f} × ({h:.2f} − {t:.2f}) × ΣLc {sumL:.2f} m "
                                         f"= {v:.3f} m³")
            book.detail(story, "Dầm", "concrete", f"{cnt} dầm {name}: {b:.2f} × ({h:.2f} − {t:.2f}) × ΣLc {sumL:.2f}", v)
            book.detail(story, "Dầm", "formwork",
                        f"{cnt} dầm {name}: ({b:.2f} + 2 × ({h:.2f} − {t:.2f})) × ΣLc {sumL:.2f}", (b + 2 * (h - t)) * sumL)
            steel_lines(story, "Dầm", f"{cnt} dầm {name}", sec_steel[(name, b, h)])
        if no_steel_story:
            book.detail(story, "Dầm", "steel", f"({no_steel_story} dầm không đạt chưa có thép – chưa tính)", 0.0, "d>18")

    # ---------------------------------------------------------------- VÁCH
    wall_fp = defaultdict(float)
    kg_w = mesh_kg_m2(**opt["wall_v"], dirs=1) + mesh_kg_m2(**opt["wall_h"], dirs=1)
    for story, ws in _group(p["walls"], "story").items():
        by_sec = defaultdict(float)
        for w in ws:
            t = asec[w["section"]]["thickness"] / 1e3
            st = defaultdict(float)
            st[group_of(opt["wall_v"]["d"])] += w["area"] * mesh_kg_m2(**opt["wall_v"], dirs=1)
            st[group_of(opt["wall_h"]["d"])] += w["area"] * mesh_kg_m2(**opt["wall_h"], dirs=1)
            book.add(story, "Vách", w["area"] * t, 2 * w["area"], st)
            H = max(pt[2] for pt in w["points"]) - min(pt[2] for pt in w["points"])
            wall_fp[story] += w["area"] / (H / 1e3) * t if H else 0
            by_sec[w["section"]] += w["area"]
        for name, A in by_sec.items():
            t = asec[name]["thickness"] / 1e3
            book.add(story, "Vách", note=f"Vách {name}: diện tích mặt đứng {A:.2f} m² × {t:.2f} = {A*t:.3f} m³")
            book.detail(story, "Vách", "concrete", f"Vách {name}: diện tích mặt đứng {A:.2f} m² × {t:.2f}", A * t)
            book.detail(story, "Vách", "formwork", f"Vách {name}: 2 mặt × {A:.2f} m²", 2 * A)
            for key, lab in (("wall_v", "thép đứng"), ("wall_h", "thép ngang")):
                o = opt[key]
                k = mesh_kg_m2(**o, dirs=1)
                book.detail(story, "Vách", "steel", f"Vách {name} – {lab} Ø{o['d']}a{o['s']} {o['layers']} lớp: "
                            f"{A:.2f} m² × {k:.2f} kg/m²", A * k, group_of(o["d"]))

    # ---------------------------------------------------------------- SÀN
    col_fp = defaultdict(float)
    for r in cols_res:
        s = fs[r["section"]]
        col_fp[r["story"]] += s["b"] * s["h"] / 1e6
    kg_s = mesh_kg_m2(**opt["slab"])
    for story, sl in _group(p["slabs"], "story").items():
        sl = [s for s in sl if s["area"] > 0 and asec[s["section"]]["thickness"] > 0]   # bỏ ô sàn rỗng / dày 0
        gross = sum(s["area"] for s in sl)
        if gross <= 0:
            continue                                     # tầng không có ô sàn bê tông thật
        vol_gross = sum(s["area"] * asec[s["section"]]["thickness"] / 1e3 for s in sl)
        t = vol_gross / gross
        deduct = col_fp[story] + wall_fp[story]
        net = max(gross - deduct, 0)
        form = max(net - beam_fp[story], 0)
        st = {group_of(opt["slab"]["d"]): net * kg_s}
        txt = (f"Sàn dày {t*1000:.0f}: ({gross:.2f} − cột {col_fp[story]:.2f} − vách {wall_fp[story]:.2f}) m² "
               f"× {t:.3f}")
        book.add(story, "Sàn", net * t, form, st, txt + f" = {net*t:.3f} m³")
        book.detail(story, "Sàn", "concrete", txt, net * t)
        book.detail(story, "Sàn", "formwork", f"Sàn: {net:.2f} m² − đáy dầm {beam_fp[story]:.2f} m²", form)
        o = opt["slab"]
        book.detail(story, "Sàn", "steel", f"Lưới Ø{o['d']}a{o['s']} {o['layers']} lớp 2 phương: "
                    f"{net:.2f} m² × {kg_s:.2f} kg/m²", net * kg_s, group_of(o["d"]))
    return book.rows(), {"beams_without_steel": no_steel, "slab_kg_m2": kg_s, "wall_kg_m2": kg_w}
