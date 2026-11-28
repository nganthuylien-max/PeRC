"""Xuất bản vẽ DXF (AutoCAD). Mỗi dầm / mỗi cột nằm trong 1 KHUNG BẢN VẼ riêng (khổ A3–A0, có khung tên),
các khung đặt cách xa nhau.
   python draw_sections.py Story5                 -> mọi dầm + mọi cột tầng Story5 (mỗi cái 1 khung), 1 file
   python draw_sections.py dam Story5             -> mọi dầm tầng Story5, 1 file
   python draw_sections.py dam Story5 B10         -> riêng dầm B10 tầng Story5
   python draw_sections.py cot C4                 -> mặt cắt dọc cột C4, mỗi tầng 1 file
   python draw_sections.py cot C4 Story5          -> chỉ tầng Story5
   python draw_sections.py cot * Story5           -> mọi cột tầng Story5 (mặt cắt dọc, mỗi cột 1 khung), 1 file"""
import json
import os
import re
import sys

from core.beam_detailing import find_supports, detail_beam
from core.grids import Grids, beam_context
from drawing.export import to_svg, to_dxf
from drawing.frame import framed, layout_frames
from drawing.model import story_vn
from drawing.sections import beam_sheet
from quantity.takeoff import slab_thickness_by_story

# tuỳ chọn: --kho=A3|A2|A1|A0 (bỏ trống = tự chọn khổ vừa nhất)
#          dầm: --tl=25 (mặt cắt dọc), --tlmc=10 (mặt cắt ngang); cột: --tlc=25, --tlmcc=20
OPT = {k[2:]: v for k, _, v in (a.partition("=") for a in sys.argv[1:] if a.startswith("--"))}
sys.argv = [a for a in sys.argv if not a.startswith("--")]
PAPER = OPT.get("kho") or None
BEAM_ES = int(OPT.get("tl", 25))                    # dầm: mặt cắt dọc
BEAM_SEC = int(OPT.get("tlmc", 10))                 # dầm: mặt cắt ngang
COL_ES = int(OPT.get("tlc", 25))                    # cột: mặt cắt dọc
COL_SEC = int(OPT.get("tlmcc", 20))                 # cột: mặt cắt ngang
SCALE = BEAM_SEC
p = json.load(open("project.json", encoding="utf-8"))
beams = json.load(open("design_beams.json", encoding="utf-8"))
cols = json.load(open("design_columns.json", encoding="utf-8"))
secs = p["frame_sections"]
supports = find_supports(p)              # bề rộng gối ở 2 đầu mỗi dầm (cột / vách / dầm)
t_slab = slab_thickness_by_story(p)      # chiều dày sàn mỗi tầng -> vẽ cánh sàn ở mặt cắt dầm
grids = Grids(p)                         # lưới trục -> bong bóng trục, tên nhịp
PROJECT = os.path.splitext(re.split(r"[\\/]", p.get("model_file", "") or "")[-1])[0]   # tên file model ETABS
os.makedirs("drawings", exist_ok=True)


def safe(s):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", str(s))


def beam_frame(r, no=None):
    sec = secs[r["section"]]
    det = detail_beam(r, sec, supports[r["id"]])
    axes, level = beam_context(p, grids, r)
    D = beam_sheet(r, sec, BEAM_SEC, det=det, slab_t=t_slab.get(r["story"], 0), axes=axes, level=level, es=BEAM_ES)
    return framed(D, f"DẦM {r['label']} – {story_vn(r['story']).upper()}", PROJECT,
                  f"1:{BEAM_ES} (mặt cắt 1:{BEAM_SEC})", no, PAPER)


def column_frame(label, story, no=None):
    from drawing.column_elevation import column_story_sheets
    D = column_story_sheets(p, cols, label, story, story, scale=COL_ES, sec_scale=COL_SEC)
    return framed(D, f"CỘT {label} – {story_vn(story).upper()}", PROJECT,
                  f"1:{COL_ES} (mặt cắt 1:{COL_SEC})", no, PAPER)


def save(D, name):
    from drawing.frame import WARNINGS
    for w in WARNINGS:
        print("  Lưu ý:", w)
    WARNINGS.clear()
    open(f"drawings/{name}.svg", "w", encoding="utf-8").write(to_svg(D))
    to_dxf(D, f"drawings/{name}.dxf")
    print(f"  drawings/{name}.dxf (+ .svg)")


def sort_label(lb):
    m = re.match(r"([A-Za-z]*)(\d+)", lb)
    return (m.group(1), int(m.group(2))) if m else (lb, 0)


def story_beams(story, label=None):
    out = [r for r in beams if r["story"] == story and r["layout"] and (label is None or r["label"] == label)]
    return sorted(out, key=lambda r: sort_label(r["label"]))


def story_columns(story):
    return sorted({r["label"] for r in cols if r["story"] == story}, key=sort_label)


args = sys.argv[1:]
print(f"Khổ giấy: {PAPER or 'tự chọn'} – tỉ lệ dầm 1:{BEAM_ES} / mặt cắt 1:{BEAM_SEC}, cột 1:{COL_ES} / mặt cắt 1:{COL_SEC}")
if args[:1] == ["cot"] and len(args) > 1:
    from drawing.column_elevation import column_stories
    label = args[1]
    if label == "*":                                     # mọi cột của 1 tầng
        story = args[2]
        labels = story_columns(story)
        print(f"{story}: {len(labels)} cột, mỗi cột 1 khung")
        frames = [column_frame(lb, story, f"{i + 1}/{len(labels)}") for i, lb in enumerate(labels)]
        save(layout_frames(frames, per_row=4), f"COT_{safe(story)}")
    else:                                                # 1 cột: 1 tầng hoặc mỗi tầng 1 file
        stories = args[2:] or column_stories(p, cols, label)
        print(f"Mặt cắt dọc cột {label}: {len(stories)} tầng, mỗi tầng 1 file")
        for st in stories:
            save(column_frame(label, st), f"COT_{safe(label)}_{safe(st)}")
elif args[:1] == ["dam"] and len(args) > 1:
    story = args[1]
    label = args[2] if len(args) > 2 else None
    rs = story_beams(story, label)
    if not rs:
        raise SystemExit(f"Không có dầm {label or ''} có bản vẽ ở tầng {story} (dầm không xếp đủ thép thì không có bản vẽ).")
    print(f"{story}: {len(rs)} dầm, mỗi dầm 1 khung")
    frames = [beam_frame(r, f"{i + 1}/{len(rs)}") for i, r in enumerate(rs)]
    save(layout_frames(frames, per_row=3), f"DAM_{safe(label)}_{safe(story)}" if label else f"DAM_{safe(story)}")
elif args:                                               # cả 1 tầng: dầm rồi đến cột, mỗi cái 1 khung
    story = args[0]
    rs = story_beams(story)
    labels = story_columns(story)
    n = len(rs) + len(labels)
    print(f"{story}: {len(rs)} dầm + {len(labels)} cột, mỗi cái 1 khung")
    frames = [beam_frame(r, f"{i + 1}/{n}") for i, r in enumerate(rs)]
    frames += [column_frame(lb, story, f"{len(rs) + i + 1}/{n}") for i, lb in enumerate(labels)]
    save(layout_frames(frames, per_row=4), safe(story))
else:
    print(__doc__)
