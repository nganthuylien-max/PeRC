"""Đọc dữ liệu công trình từ ETABS. Đơn vị đầu vào: N, mm. Đơn vị lưu: kN, kN.m, mm."""
from .tables import read_table, to_float


# ----------------------------------------------------------------- tầng, vật liệu, tiết diện
def read_stories(model):
    """Bảng xếp từ trên xuống -> đảo lại, cộng dồn chiều cao để ra cao độ (giả thiết đáy = 0)."""
    rows = read_table(model, "Story Definitions")
    stories, elev = [], 0.0
    for r in reversed(rows):
        h = to_float(r["Height"])
        elev += h
        stories.append({"name": r["Story"], "height": h, "elevation": elev})
    return stories


def read_materials(model):
    return {r["Material"]: {"fc": to_float(r["Fc"])}
            for r in read_table(model, "Material Properties - Concrete Data")}


def read_frame_sections(model):
    """Tiết diện chữ nhật. t3 = chiều cao h, t2 = bề rộng b."""
    out = {}
    for r in read_table(model, "Frame Section Property Definitions - Concrete Rectangular"):
        kind = "column" if r["DesignType"] == "Column" else "beam"
        out[r["Name"]] = {"b": to_float(r["t2"]), "h": to_float(r["t3"]),
                          "material": r["Material"], "type": kind}
    return out


def read_area_sections(model):
    out = {}
    for r in read_table(model, "Area Section Property Definitions - Summary"):
        out[r["Name"]] = {"type": r["Type"], "thickness": to_float(r["TotalThick"]),
                          "material": r["Material"]}
    return out


def read_points(model):
    return {r["UniqueName"]: (to_float(r["X"]), to_float(r["Y"]), to_float(r["Z"]))
            for r in read_table(model, "Point Object Connectivity")}


# ----------------------------------------------------------------- dầm, cột
def read_frames(model, sections, points):
    """Trả về (beams, columns) – chỉ lấy cấu kiện bê tông chữ nhật, báo số cấu kiện bị bỏ qua."""
    assign = {r["UniqueName"]: r for r in read_table(model, "Frame Assignments - Section Properties")}
    result = {"beam": [], "column": []}
    skipped = {}
    for key, kind in (("Beam Object Connectivity", "beam"), ("Column Object Connectivity", "column")):
        for r in read_table(model, key):
            a = assign.get(r["UniqueName"])
            if not a or a["SectProp"] not in sections:
                name = a["SectProp"] if a else "?"         # thép hình, cột tròn, chữ T... -> bỏ qua
                skipped[name] = skipped.get(name, 0) + 1
                continue
            result[kind].append({
                "id": r["UniqueName"], "label": a["Label"], "story": r["Story"],
                "section": a["SectProp"], "L": to_float(r["Length"]),
                "i": points.get(r["UniquePtI"]), "j": points.get(r["UniquePtJ"]),
            })
    if skipped:
        print("  Bỏ qua (không phải tiết diện bê tông chữ nhật): " +
              ", ".join(f"{n} × {k}" for n, k in sorted(skipped.items(), key=lambda x: -x[1])))
    return result["beam"], result["column"]


# ----------------------------------------------------------------- sàn, vách
def read_areas(model, area_sections, points):
    assign = {r["UniqueName"]: r for r in read_table(model, "Area Assignments - Section Properties")}
    result = {"slab": [], "wall": []}
    for key, kind in (("Floor Object Connectivity", "slab"), ("Wall Object Connectivity", "wall")):
        for r in read_table(model, key):
            a = assign.get(r["UniqueName"])
            if not a or a["SectProp"] not in area_sections:
                continue
            # số đỉnh thay đổi: lấy mọi cột UniquePt1, UniquePt2, ... có giá trị
            pts = [points[r[k]] for k in r if k.startswith("UniquePt") and r[k] in points]
            result[kind].append({
                "id": r["UniqueName"], "label": a["Label"], "story": r["Story"],
                "section": a["SectProp"], "area": to_float(r["Area"]) / 1e6,   # mm2 -> m2
                "perimeter": to_float(r["Perimeter"]), "points": pts,
            })
    return result["slab"], result["wall"]


# ----------------------------------------------------------------- nội lực
def list_combos(model):
    res = model.RespCombo.GetNameList(0, [])
    names = [x for x in res if isinstance(x, (list, tuple))]
    return list(names[0]) if names else []


COMBO_TYPES = {0: "Cộng tuyến tính", 1: "Bao (Envelope)", 2: "Cộng trị tuyệt đối", 3: "SRSS", 4: "Range"}
AUTO_PREFIX = ("DCON", "DSTL", "DWAL", "DSLB", "DCMP", "UDCON", "UDSTL")   # tổ hợp ETABS tự sinh cho thiết kế


def combo_info(model):
    """Danh sách tổ hợp kèm loại. Mặc định chọn: tổ hợp người dùng tự đặt, không phải tổ hợp bao
    (bao chỉ là lấy max/min của các tổ hợp khác -> thừa) và không phải tổ hợp ETABS tự sinh."""
    out = []
    for name in list_combos(model):
        t = None
        try:
            res = model.RespCombo.GetTypeOfCombo(name, 0)
            ints = [x for x in res if isinstance(x, int)]
            t = ints[0] if len(ints) >= 2 else None        # [ComboType, ret]
        except Exception:
            pass
        auto = name.upper().startswith(AUTO_PREFIX)
        envelope = t == 1 or "BAO" in name.upper() or "ENV" in name.upper()
        out.append({"name": name, "type": COMBO_TYPES.get(t, "?"), "auto": auto,
                    "default": not auto and not envelope})
    return out


def zone_of(station, L):
    r = station / L if L else 0.5
    return "L" if r <= 0.25 else ("R" if r >= 0.75 else "M")


def read_beam_forces(model, beams, combos):
    """Đọc TỪNG tổ hợp, chỉ giữ giá trị bao theo vùng -> tiết kiệm bộ nhớ.
    Quy ước ETABS: M3 < 0 căng thớ trên, M3 > 0 căng thớ dưới."""
    by_id = {b["id"]: b for b in beams}
    for b in beams:
        b["env"] = {z: {"Mtop": 0.0, "Mtop_combo": "", "Mbot": 0.0, "Mbot_combo": "",
                        "V": 0.0, "V_combo": ""} for z in ("L", "M", "R")}
    for k, combo in enumerate(combos, 1):
        rows = read_table(model, "Element Forces - Beams", combos=[combo])
        for r in rows:
            b = by_id.get(r["UniqueName"])
            if not b:
                continue
            e = b["env"][zone_of(to_float(r["Station"]), b["L"])]
            m = to_float(r["M3"]) / 1e6          # N.mm -> kN.m
            v = abs(to_float(r["V2"])) / 1e3     # N -> kN
            if -m > e["Mtop"]:
                e["Mtop"], e["Mtop_combo"] = -m, combo
            if m > e["Mbot"]:
                e["Mbot"], e["Mbot_combo"] = m, combo
            if v > e["V"]:
                e["V"], e["V_combo"] = v, combo
        print(f"  dầm: {combo} ({k}/{len(combos)}) – {len(rows)} dòng")


def read_column_forces(model, columns, combos):
    """Cột: giữ đủ mọi dòng (cặp N–M phải đi cùng nhau). P < 0 là nén."""
    by_id = {c["id"]: c for c in columns}
    for c in columns:
        c["forces"] = []
    rows = read_table(model, "Element Forces - Columns", combos=combos)
    for r in rows:
        c = by_id.get(r["UniqueName"])
        if c:
            c["forces"].append({
             "combo": r["OutputCase"] + (" " + r["StepType"] if r.get("StepType") else ""),
                "station": to_float(r["Station"]),
                "P": to_float(r["P"]) / 1e3, "M2": to_float(r["M2"]) / 1e6,
                "M3": to_float(r["M3"]) / 1e6, "V2": to_float(r["V2"]) / 1e3,
                "V3": to_float(r["V3"]) / 1e3})
    print(f"  cột: {len(rows)} dòng")