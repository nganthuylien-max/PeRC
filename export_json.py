"""Đọc toàn bộ công trình từ ETABS và lưu ra project.json."""
import json
import time

from etabs_link.connect import connect, N_MM_C
from etabs_link import reader

t0 = time.time()
pid, model = connect()
if not model.GetModelIsLocked():
    raise SystemExit("Model chưa chạy phân tích – nhấn F5 trong ETABS rồi chạy lại.")

old_units = model.GetPresentUnits()
model.SetPresentUnits(N_MM_C)
try:
    print("Đọc tầng, vật liệu, tiết diện, nút...")
    stories = reader.read_stories(model)
    materials = reader.read_materials(model)
    frame_secs = reader.read_frame_sections(model)
    area_secs = reader.read_area_sections(model)
    points = reader.read_points(model)

    print("Đọc dầm, cột, sàn, vách...")
    beams, columns = reader.read_frames(model, frame_secs, points)
    slabs, walls = reader.read_areas(model, area_secs, points)

    # tổ hợp thiết kế: các Comb tự đặt, bỏ BAO (tổ hợp bao) và DCon (tổ hợp mặc định của ETABS)
    # tổ hợp: theo lựa chọn trong app (combos_selected.json), không có thì chọn mặc định:
    # tổ hợp người dùng tự đặt, bỏ tổ hợp bao và tổ hợp ETABS tự sinh
    import os
    all_names = reader.list_combos(model)
    if os.path.exists("combos_selected.json"):
        chosen = json.load(open("combos_selected.json", encoding="utf-8"))
        combos = [c for c in all_names if c in chosen]
        print(f"Dùng {len(combos)} tổ hợp đã chọn trong app")
    else:
        combos = [c["name"] for c in reader.combo_info(model) if c["default"]]
        print(f"Chưa chọn tổ hợp -> dùng mặc định {len(combos)} tổ hợp (bỏ tổ hợp bao và tổ hợp tự sinh)")
    if not combos:
        raise SystemExit("Không có tổ hợp nào được chọn – vào bước 1 trong app để chọn tổ hợp.")
    print(f"Đọc nội lực {len(combos)} tổ hợp...")
    reader.read_beam_forces(model, beams, combos)
    reader.read_column_forces(model, columns, combos)

    file_name = model.GetModelFilename(True).replace(".$et", ".EDB")
finally:
    model.SetPresentUnits(old_units)          # trả lại đơn vị cũ cho người dùng

project = {"model_file": file_name, "units": "kN, kN.m, mm", "combos": combos,
           "stories": stories, "materials": materials,
           "frame_sections": frame_secs, "area_sections": area_secs,
           "beams": beams, "columns": columns, "slabs": slabs, "walls": walls}

with open("project.json", "w", encoding="utf-8") as f:
    json.dump(project, f, ensure_ascii=False)

print(f"\nXong trong {time.time() - t0:.0f} s -> project.json")
print(f"  {len(stories)} tầng | {len(beams)} dầm | {len(columns)} cột | "
      f"{len(slabs)} sàn | {len(walls)} vách")