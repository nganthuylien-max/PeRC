import time
from core.materials import Concrete, Steel, bar_area
from core.column_section import Section, bar_positions

c, s = Concrete("B30"), Steel("CB400-V")

print("--- Cột 400×400, 8Ø20 (3 thanh/cạnh) ---")
bars = bar_positions(400, 400, 30, 8, 20, 3, 3)
sec = Section(400, 400, bars, c, s)
As = 8 * bar_area(20)
print(f"Số thanh: {len(bars)}, As = {sec.As:.0f} mm2")
print(f"N0 máy = {sec.N0:.1f} kN | tính tay = {(17*(160000-As) + 350*As)/1e3:.1f} kN")

t = time.time()
u1, Mu1 = sec.util(1500, 150, 0)
print(f"\nN=1500, M3=150, M2=0   -> hệ số {u1:.3f}, Mu = {Mu1:.1f} kN.m  ({(time.time()-t)*1000:.0f} ms)")
u2, Mu2 = sec.util(1500, 0, 150)
print(f"N=1500, M3=0,   M2=150 -> hệ số {u2:.3f}  (tiết diện vuông -> phải ≈ dòng trên)")
u3, Mu3 = sec.util(1500, 150, 150)
print(f"N=1500, M3=150, M2=150 -> hệ số {u3:.3f}, Mu = {Mu3:.1f}  (xiên -> nguy hiểm hơn)")