"""In nội lực các dầm không đạt / lỗi để tìm nguyên nhân."""
import json

p = json.load(open("project.json", encoding="utf-8"))
d = {r["id"]: r for r in json.load(open("design_beams.json", encoding="utf-8"))}

bad = [bm for bm in p["beams"] if bm["id"] not in d or not d[bm["id"]]["ok"]]
print(f"{len(bad)} dầm cần xem\n")
print(f"{'Tầng':8} {'Dầm':5} {'Tiết diện':9} {'L (mm)':>7} | {'M trên L':>8} {'M trên R':>8} {'M dưới M':>8} {'Q max':>7}")
for bm in sorted(bad, key=lambda b: -max(b['env'][z]['Mtop'] for z in 'LR'))[:25]:
    e = bm["env"]
    print(f"{bm['story']:8} {bm['label']:5} {bm['section']:9} {bm['L']:7.0f} | "
          f"{e['L']['Mtop']:8.0f} {e['R']['Mtop']:8.0f} {e['M']['Mbot']:8.0f} "
          f"{max(e[z]['V'] for z in 'LMR'):7.0f}")

# thống kê nhanh
from collections import Counter
print("\nTheo tiết diện:", Counter(bm["section"] for bm in bad))
print("Theo tên dầm  :", Counter(bm["label"] for bm in bad).most_common(8))