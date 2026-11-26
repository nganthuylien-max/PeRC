"""Bảng tiên lượng kiểu Eta: mỗi công tác 1 dòng (STT, tên, đơn vị, khối lượng) + các dòng diễn giải.
Dùng chung cho app (xem theo tầng) và file Excel."""
ELEMENTS = ("Cột", "Dầm", "Sàn", "Vách")
GROUPS = ("d≤10", "d≤18", "d>18")
GROUP_NAME = {"d≤10": "đường kính ≤ 10 mm", "d≤18": "đường kính ≤ 18 mm", "d>18": "đường kính > 18 mm"}
EL_NAME = {"Cột": "cột", "Dầm": "dầm", "Sàn": "sàn", "Vách": "vách"}


def work_items(rows, story=None, story_order=None):
    """story=None: toàn công trình (diễn giải = khối lượng từng tầng); story="Story5": riêng tầng đó
    (diễn giải = cách tính từng nhóm cấu kiện). Bỏ công tác có khối lượng 0 trên toàn công trình."""
    order = story_order or {}
    sel = [r for r in rows if story in (None, r["story"])]
    sel.sort(key=lambda r: -order.get(r["story"], 0))           # tầng trên trước
    defs = []
    for e in ELEMENTS:
        defs.append((f"Bê tông {EL_NAME[e]}", "m³", e, "concrete", None))
    for e in ELEMENTS:
        defs.append((f"Ván khuôn {EL_NAME[e]}", "m²", e, "formwork", None))
    for e in ELEMENTS:
        for g in GROUPS:
            defs.append((f"Cốt thép {EL_NAME[e]}, {GROUP_NAME[g]}", "tấn", e, "steel", g))

    def value(r, work, g):
        return r["steel"].get(g, 0.0) / 1000 if work == "steel" else r[work]

    items = []
    for name, unit, e, work, g in defs:
        if sum(value(r, work, g) for r in rows if r["element"] == e) <= 1e-9:
            continue                                            # công tác không có trong công trình
        mine = [r for r in sel if r["element"] == e]
        qty = sum(value(r, work, g) for r in mine)
        lines = []
        if story is None:
            lines = [(r["story"], value(r, work, g)) for r in mine if value(r, work, g) > 1e-9]
        else:
            for r in mine:
                for d in r.get("details", []):
                    if d["work"] == work and (g is None or d["group"] == g):
                        v = d["value"] / 1000 if work == "steel" else d["value"]
                        lines.append((d["text"], v))
        items.append({"name": name, "unit": unit, "qty": qty, "lines": lines, "element": e, "work": work, "group": g})
    for i, it in enumerate(items, 1):
        it["stt"] = i
    return items
