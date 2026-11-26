"""Thiết kế mọi dầm trong project.json -> design_beams.json"""
import json
import time

from core.materials import Concrete, Steel
from core.beam_design import design_beam, bars_text

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
for bm in p["beams"]:
    sec = p["frame_sections"][bm["section"]]
    info = {"id": bm["id"], "label": bm["label"], "story": bm["story"],
            "section": bm["section"], "L": bm["L"]}
    try:
        r = design_beam(bm, sec, concrete_of(sec["material"]), steel, steel_w)
    except ValueError as e:
        # không xếp nổi thép trong 2 lớp -> vẫn ghi lại là KHÔNG ĐẠT, kèm gợi ý
        r = {"layout": None, "checks": None, "util": None, "ok": False,
             "warnings": [f"{e}. Gợi ý: tăng tiết diện hoặc khai báo vùng cứng đầu dầm "
                          "(mômen đang lấy tại tim gối)"]}
    results.append({**info, **r})

with open("design_beams.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False)

ok = [r for r in results if r["ok"]]
over = [r for r in results if not r["ok"] and r["util"] is not None]
no_fit = [r for r in results if r["util"] is None]
print(f"Thiết kế {len(results)} dầm trong {time.time() - t0:.1f} s")
print(f"  ĐẠT                          : {len(ok)}")
print(f"  KHÔNG ĐẠT (thiếu khả năng)   : {len(over)}")
print(f"  KHÔNG ĐẠT (không xếp đủ thép): {len(no_fit)}")

print("\nVí dụ 3 dầm đạt có hệ số sử dụng cao nhất:")
for r in sorted(ok, key=lambda r: -r["util"])[:3]:
    L = r["layout"]
    st = L["stirrup"]
    print(f"  {r['story']:8} {r['label']:5} {r['section']:7} hệ số {r['util']:.3f} | "
          f"trên: {bars_text(L, 'top', 'L')} / {bars_text(L, 'top', 'M')} / {bars_text(L, 'top', 'R')} | "
          f"dưới giữa: {bars_text(L, 'bot', 'M')} | đai Ø{st['d']}a{st['s_end']}/{st['s_mid']}")

print("\nDầm không đạt (lặp theo tên):")
from collections import Counter
for name, n in Counter(f"{r['label']} ({r['section']})" for r in over + no_fit).most_common():
    print(f"  {name}: {n} tầng")