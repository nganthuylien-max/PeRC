"""Thiết kế mọi cột trong project.json -> design_columns.json"""
import json
import time
from collections import Counter

from core.materials import Concrete, Steel
from core.column_design import design_column

with open("project.json", encoding="utf-8") as f:
    p = json.load(f)

steel, steel_w = Steel("CB400-V"), Steel("CB240-T")
_conc = {}


def concrete_of(mat):
    """Cấp bê tông theo tên vật liệu, không có thì suy từ fc' trong project.json."""
    if mat not in _conc:
        _conc[mat] = Concrete(mat, fc=p.get("materials", {}).get(mat, {}).get("fc"))
        print(f"  Vật liệu {mat}: {_conc[mat].grade} (theo {_conc[mat].source})")
    return _conc[mat]
t0 = time.time()
results = []
for k, col in enumerate(p["columns"], 1):
    sec = p["frame_sections"][col["section"]]
    r = design_column(col, sec, concrete_of(sec["material"]), steel, steel_w)
    results.append({"id": col["id"], "label": col["label"], "story": col["story"],
                    "section": col["section"], "L": col["L"], **r})
    if k % 50 == 0:
        print(f"  {k}/{len(p['columns'])} cột – {time.time() - t0:.0f} s")

with open("design_columns.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, default=float)

ok = sum(r["ok"] for r in results)
print(f"\nThiết kế {len(results)} cột trong {time.time() - t0:.0f} s: {ok} ĐẠT, {len(results) - ok} KHÔNG ĐẠT")

print("\nThép cột theo tầng (cột C1):")
for r in sorted([r for r in results if r["label"] == "C1"], key=lambda r: -int(r["story"][5:]))[::4]:
    L = r["layout"]
    print(f"  {r['story']:8} {r['section']:7} {r['n_bars']:2}Ø{L['d']}  μ = {r['mu']*100:.2f}%  "
          f"hệ số {r['util']:.3f}  đai Ø{L['tie']['d']}a{L['tie']['s_end']}/{L['tie']['s_mid']}  "
          f"nguy hiểm: {r['worst']['combo']} N = {r['worst']['N']:.0f} kN")

print("\nPhân bố bố trí thép:", Counter(f"{r['n_bars']}Ø{r['layout']['d']}" for r in results).most_common(6))
bad = [r for r in results if not r["ok"]]
for r in bad[:5]:
    print("  KHÔNG ĐẠT:", r["story"], r["label"], r["section"], r["warnings"])
