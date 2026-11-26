from core.materials import Concrete, Steel, bar_area

c = Concrete("B30")
s = Steel("CB400-V")
print(f"{c.grade}: Rb = {c.Rb} MPa, Rbt = {c.Rbt} MPa")
print(f"{s.grade}: Rs = {s.Rs} MPa, ξR = {s.xi_R:.3f}, αR = {s.alpha_R:.3f}")
print(f"1 thanh Ø20: {bar_area(20):.1f} mm2 | 3Ø20: {3 * bar_area(20):.0f} mm2")

c2 = Concrete("B30", gamma_b1=0.9)
print(f"B30 với γb1 = 0.9: Rb = {c2.Rb:.2f} MPa")
from core.beam_flexure import required_As, capacity

print("\n--- VD1: cốt đơn, b×h = 300×600, a = 50, M = 250 kN.m ---")
r = required_As(250, 300, 600, 50, 40, c, s)
print(f"h0 = {r['h0']}, αm = {r['alpha_m']:.4f}, ξ = {r['xi']:.4f}, As = {r['As']:.1f} mm2, cốt kép: {r['double']}")

print("\n--- VD2: cốt kép, M = 600 kN.m ---")
r2 = required_As(600, 300, 600, 60, 40, c, s)
print(f"αm = {r2['alpha_m']:.4f} > αR → As = {r2['As']:.0f} mm2, As' = {r2['As_c']:.0f} mm2")
k2 = capacity(300, 600, r2["As"], 60, r2["As_c"], 40, c, s)
print(f"Kiểm tra lại: Mu = {k2['Mu']:.1f} kN.m (phải ≈ 600)")

print("\n--- VD3: bố trí 3Ø25, kiểm tra Mu ---")
As = 3 * bar_area(25)
k = capacity(300, 600, As, 50, 0, 40, c, s)
print(f"As = {As:.0f} mm2, x = {k['x']:.1f} mm, Mu = {k['Mu']:.1f} kN.m, μ = {k['mu']*100:.2f}%")
print(f"M/Mu = {250 / k['Mu']:.3f}")
from core.beam_shear import shear_check, choose_stirrups

w = Steel("CB240-T")          # thép đai
print("\n--- VD4: Q = 200 kN, 300×600, h0 = 550, đai Ø8 2 nhánh ---")
for s_ in (150, 100):
    k = shear_check(200, 300, 550, c, w, 8, 2, s_)
    print(f"Ø8a{s_}: qsw = {k['qsw']:.1f} N/mm, Qb = {k['Qb']:.1f}, Qsw = {k['Qsw']:.1f}, "
          f"Qu = {k['Qu']:.1f} kN, c = {k['c']:.0f} mm -> {'ĐẠT' if k['ok'] else 'KHÔNG ĐẠT'}")
print(f"Dải nén nghiêng: 0.3·Rb·b·h0 = {k['Q_strut']:.0f} kN")

st = choose_stirrups(200, 80, 300, 600, 550, c, w, 25)
print(f"Tự chọn: Ø{st['d']}a{st['s_end']} (đầu dầm) / a{st['s_mid']} (giữa), {st['legs']} nhánh")