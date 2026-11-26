"""Đọc danh sách tổ hợp tải trọng từ ETABS -> combos_available.json (dùng cho bước chọn tổ hợp trong app).
   python list_combos.py"""
import json

from etabs_link.connect import connect
from etabs_link.reader import combo_info

pid, model = connect()
info = combo_info(model)
json.dump({"model": model.GetModelFilename(True).replace(".$et", ".EDB"), "combos": info},
          open("combos_available.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{len(info)} tổ hợp, mặc định chọn {sum(c['default'] for c in info)}:")
for c in info:
    print(f"  [{'x' if c['default'] else ' '}] {c['name']:20} {c['type']}" + ("  (ETABS tự sinh)" if c["auto"] else ""))
