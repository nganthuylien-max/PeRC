"""Xuất bản vẽ dầm (mặt cắt dọc + 3 mặt cắt ngang) và cột.
   python draw_sections.py              -> vài bản vẽ mẫu vào thư mục drawings/
   python draw_sections.py Story5       -> mọi dầm và cột của tầng Story5, ghép vào 1 file DXF
   python draw_sections.py cot C4                 -> mặt cắt dọc cột C4, mỗi tầng 1 file (sàn dưới -> sàn trên)
   python draw_sections.py cot C4 Story5          -> chỉ tầng Story5
   python draw_sections.py cot C4 Story5 Story6   -> các tầng được liệt kê"""
import json
import os
import sys

from core.beam_detailing import find_supports, detail_beam
from drawing.sections import beam_sheet, column_sheet, combine
from drawing.export import to_svg, to_dxf

SCALE = 10
p = json.load(open("project.json", encoding="utf-8"))
beams = json.load(open("design_beams.json", encoding="utf-8"))
cols = json.load(open("design_columns.json", encoding="utf-8"))
secs = p["frame_sections"]
supports = find_supports(p)              # bề rộng gối ở 2 đầu mỗi dầm (cột / vách / dầm)
os.makedirs("drawings", exist_ok=True)


def beam_drawing(r):
    sec = secs[r["section"]]
    det = detail_beam(r, sec, supports[r["id"]])
    return beam_sheet(r, sec, SCALE, det=det)


def save(D, name):
    open(f"drawings/{name}.svg", "w", encoding="utf-8").write(to_svg(D))
    to_dxf(D, f"drawings/{name}.dxf")
    print(f"  drawings/{name}.dxf (+ .svg)")


if len(sys.argv) > 2 and sys.argv[1] == "cot":           # mặt cắt dọc cột: mỗi tầng 1 file
    from drawing.column_elevation import column_story_sheets, column_stories
    label = sys.argv[2]
    stories = sys.argv[3:] or column_stories(p, cols, label)
    print(f"Mặt cắt dọc cột {label}: {len(stories)} tầng, mỗi tầng 1 file")
    for st in stories:
        save(column_story_sheets(p, cols, label, st, st), f"COT_DOC_{label}_{st}")
elif len(sys.argv) > 1:                                  # cả 1 tầng
    story = sys.argv[1]
    sheets = [beam_drawing(r) for r in beams if r["story"] == story and r["layout"]]
    sheets += [column_sheet(r, secs[r["section"]], SCALE) for r in cols if r["story"] == story]
    print(f"{story}: {len(sheets)} bản vẽ")
    save(combine(sheets, SCALE, per_row=2), story)
else:                                                    # vài bản vẽ mẫu
    samples = [next(r for r in beams if r["story"] == "Story5" and r["label"] == "B10"),
               next(r for r in beams if r["layout"] and not r["ok"])]
    for r in samples:
        save(beam_drawing(r), f"DAM_{r['story']}_{r['label']}")
    for name in ("Story1", "Story13"):
        r = next(c for c in cols if c["story"] == name and c["label"] == "C1")
        save(column_sheet(r, secs[r["section"]], SCALE), f"COT_{r['story']}_{r['label']}")
