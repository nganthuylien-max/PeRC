"""Kiểm tra 1 cột thật: cột chịu nén lớn nhất của công trình."""
import json
from core.materials import Concrete, Steel
from core.column_design import check_column, tie_for

p = json.load(open("project.json", encoding="utf-8"))
col = max(p["columns"], key=lambda c: max(-f["P"] for f in c["forces"]))
sec = p["frame_sections"][col["section"]]
print(f"Cột nén lớn nhất: {col['story']} {col['label']} {col['section']} ({sec['b']:.0f}×{sec['h']:.0f}), "
      f"L = {col['L']:.0f} mm, {len(col['forces'])} dòng nội lực")

for d, nb in ((25, 4), (28, 5), (32, 6)):
    layout = {"d": d, "nb": nb, "nh": nb, "tie": tie_for(d, 0.02)}
    r = check_column(col, sec, layout, Concrete(sec["material"]), Steel("CB400-V"), Steel("CB240-T"))
    w = r["worst"]
    print(f"\n{r['n_bars']}Ø{d}: As = {r['As']:.0f} mm2, μ = {r['mu']*100:.2f}% (μmin {r['mu_min']*100:.2f}%), "
          f"λ = {r['lambda']:.1f}, ea = {r['ea3']:.0f} mm")
    print(f"  Nguy hiểm: {w['combo']} N = {w['N']:.0f} kN, M3 = {w['M3']:.0f}, M2 = {w['M2']:.0f} kN.m")
    print(f"  Kể ea + uốn dọc: η3 = {w['eta3']:.3f}, η2 = {w['eta2']:.3f} -> M3d = {w['M3d']:.0f}, M2d = {w['M2d']:.0f}")
    print(f"  Mu = {w['Mu']:.0f} kN.m -> hệ số N–M {w['util']:.3f} | cắt {r['shear2']['util']:.2f}/{r['shear3']['util']:.2f} "
          f"-> {'ĐẠT' if r['ok'] else 'KHÔNG ĐẠT'}")
