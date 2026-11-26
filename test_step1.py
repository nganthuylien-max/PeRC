from etabs_link.connect import connect, N_MM_C
from etabs_link.tables import read_table, to_float

pid, model = connect()
print("Đã kết nối ETABS PID", pid)
print("Đã có kết quả phân tích:", model.GetModelIsLocked())

model.SetPresentUnits(N_MM_C)                     # ép về N, mm cho chắc

stories = read_table(model, "Story Definitions")
print("Số tầng:", len(stories), "| tầng trên cùng:", stories[0]["Story"],
      "cao", to_float(stories[0]["Height"]), "mm")

cols = read_table(model, "Element Forces - Columns", combos=["Comb1"])
c = cols[0]
print("Nội lực cột Comb1:", len(cols), "dòng")
print(f"  VD {c['Story']} {c['Column']}: N = {to_float(c['P'])/1000:.1f} kN, "
      f"M3 = {to_float(c['M3'])/1e6:.1f} kN.m")