"""Bóc khối lượng toàn công trình -> quantities.json + PeRC_KhoiLuong.xlsx + in bảng tổng hợp."""
import json
from collections import defaultdict

from core.beam_detailing import find_supports
from quantity.excel_export import write_quantity_excel
from quantity.takeoff import takeoff

p = json.load(open("project.json", encoding="utf-8"))
beams = json.load(open("design_beams.json", encoding="utf-8"))
cols = json.load(open("design_columns.json", encoding="utf-8"))

rows, info = takeoff(p, beams, cols, find_supports(p))
json.dump(rows, open("quantities.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
write_quantity_excel(rows, p, "PeRC_KhoiLuong.xlsx")

tot = defaultdict(lambda: defaultdict(float))
for r in rows:
    t = tot[r["element"]]
    t["concrete"] += r["concrete"]
    t["formwork"] += r["formwork"]
    for g, kg in r["steel"].items():
        t[g] += kg

print(f"{'Cấu kiện':8} {'Bê tông m³':>11} {'Ván khuôn m²':>13} {'Thép d≤10 T':>12} {'d≤18 T':>9} {'d>18 T':>9} {'kg/m³':>7}")
G = defaultdict(float)
for e in ("Cột", "Dầm", "Sàn", "Vách"):
    t = tot[e]
    steel = t["d≤10"] + t["d≤18"] + t["d>18"]
    print(f"{e:8} {t['concrete']:11.1f} {t['formwork']:13.1f} {t['d≤10']/1e3:12.2f} {t['d≤18']/1e3:9.2f} "
          f"{t['d>18']/1e3:9.2f} {(steel / t['concrete'] if t['concrete'] else 0):7.0f}")
    for k in ("concrete", "formwork", "d≤10", "d≤18", "d>18"):
        G[k] += t[k]
steel = G["d≤10"] + G["d≤18"] + G["d>18"]
print(f"{'TỔNG':8} {G['concrete']:11.1f} {G['formwork']:13.1f} {G['d≤10']/1e3:12.2f} {G['d≤18']/1e3:9.2f} "
      f"{G['d>18']/1e3:9.2f} {(steel / G['concrete'] if G['concrete'] else 0):7.0f}")
print(f"\nTổng thép: {steel/1e3:.1f} tấn. Sàn {info['slab_kg_m2']:.1f} kg/m², vách {info['wall_kg_m2']:.1f} kg/m².")
if info["beams_without_steel"]:
    print(f"Lưu ý: {info['beams_without_steel']} dầm không đạt (không xếp đủ thép) chưa tính thép.")

print("\nVí dụ diễn giải tầng Story5:")
for r in rows:
    if r["story"] == "Story5":
        for n in r["notes"][:3]:
            print(f"  [{r['element']}] {n}")

print("\nĐã ghi quantities.json và PeRC_KhoiLuong.xlsx")
