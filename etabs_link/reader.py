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


def read_grids(model):
    """Lưới trục: [{"id": "A", "axis": "X" | "Y", "coord": mm}]. Không đọc được thì trả về [] (app tự suy trục từ cột)."""
    try:
        rows = read_table(model, "Grid Definitions - Grid Lines")
    except Exception as e:
        print("  Không đọc được lưới trục:", e)
        return []
    out = []
    for r in rows:
        kt = next((k for k in r if "type" in k.lower()), None)
        ki = next((k for k in r if k.lower() in ("id", "gridid", "grid id", "label")), None)
        ko = next((k for k in r if "ordinate" in k.lower() or k.lower() in ("coord", "x", "y")), None)
        if not (kt and ki and ko):
            continue
        t = str(r[kt]).strip().upper()
        if t[:1] in ("X", "Y"):
            try:
                out.append({"id": str(r[ki]).strip(), "axis": t[0], "coord": to_float(r[ko])})
            except ValueError:
                pass
    return out


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


def _interp(pts, x):
    """Nội suy tuyến tính (M, V) tại tọa độ x trên dãy điểm (station, M, V) đã sắp xếp."""
    for (s0, m0, v0), (s1, m1, v1) in zip(pts, pts[1:]):
        if s0 <= x <= s1:
            t = (x - s0) / (s1 - s0) if s1 > s0 else 0.0
            return m0 + t * (m1 - m0), v0 + t * (v1 - v0)
    return None


def face_samples(pts, L, fL, fR):
    """Các điểm dùng để thiết kế: nội lực TẠI MÉP GỐI (nội suy) và mọi điểm giữa 2 mép gối.
    Phần dầm nằm trong cột/vách không cần thiết kế theo mômen ở tim gối (thiên về lãng phí).
    Trả về [(vùng L/M/R, M, V)], vùng chia theo nhịp thông thủy: 1/4 – 1/2 – 1/4."""
    pts = sorted(pts)
    a, c = fL, L - fR
    if c - a < 0.3 * L:                                  # gối quá rộng so với nhịp -> dùng tim gối
        a, c = 0.0, L
    out = []
    for x in (a, c):
        v = _interp(pts, x)
        if v:
            out.append((x, *v))
    out += [p for p in pts if a < p[0] < c]
    Lc = c - a
    res = []
    for s, m, v in out:
        r = (s - a) / Lc if Lc else 0.5
        res.append(("L" if r <= 0.25 else ("R" if r >= 0.75 else "M"), m, v))
    return res


def read_beam_forces(model, beams, combos, faces=None):
    """Đọc TỪNG tổ hợp, chỉ giữ giá trị bao theo vùng -> tiết kiệm bộ nhớ.
    faces = {id dầm: (nửa bề rộng gối trái, nửa bề rộng gối phải)} -> lấy nội lực tại mép gối.
    Quy ước ETABS: M3 < 0 căng thớ trên, M3 > 0 căng thớ dưới."""
    faces = faces or {}
    by_id = {b["id"]: b for b in beams}
    for b in beams:
        b["env"] = {z: {"Mtop": 0.0, "Mtop_combo": "", "Mbot": 0.0, "Mbot_combo": "",
                        "V": 0.0, "V_combo": ""} for z in ("L", "M", "R")}
        b["design_at"] = "mép gối" if faces.get(b["id"], (0, 0)) != (0, 0) else "tim gối"
    for k, combo in enumerate(combos, 1):
        rows = read_table(model, "Element Forces - Beams", combos=[combo])
        groups = {}
        for r in rows:                                   # gom theo dầm (và Max/Min nếu tổ hợp có phổ phản ứng)
            if r["UniqueName"] in by_id:
                groups.setdefault((r["UniqueName"], r.get("StepType", "")), []).append(
                    (to_float(r["Station"]), to_float(r["M3"]) / 1e6, abs(to_float(r["V2"])) / 1e3))
        for (uid, _), pts in groups.items():
            b = by_id[uid]
            fL, fR = faces.get(uid, (0.0, 0.0))
            for z, m, v in face_samples(pts, b["L"], fL, fR):
                e = b["env"][z]
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