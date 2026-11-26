"""Xuất bảng khối lượng ra Excel (3 sheet).

    "Tong hop"  : tổng theo cấu kiện (Cột, Dầm, Sàn, Vách) – công thức SUMIFS lấy từ sheet "Theo tang"
    "Theo tang" : mỗi dòng = 1 tầng x 1 cấu kiện, bê tông m³, ván khuôn m², thép 3 nhóm đường kính (kg)
    "Dien giai" : diễn giải cách tính của từng dòng (từ notes của quantity/takeoff.py)
"""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ELEMENTS = ("Cột", "Dầm", "Sàn", "Vách")
GROUPS = ("d≤10", "d≤18", "d>18")
FONT = "Times New Roman"
THIN = Side(style="thin", color="999999")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD = PatternFill("solid", fgColor="D9E1F2")
TOTAL = PatternFill("solid", fgColor="F2F2F2")


def _cell(ws, r, c, v, bold=False, fmt=None, fill=None, wrap=False, align=None, italic=False):
    x = ws.cell(r, c, v)
    x.font = Font(name=FONT, bold=bold, italic=italic)
    x.border = BOX
    x.alignment = Alignment(wrap_text=wrap, vertical="center", horizontal=align)
    if fmt:
        x.number_format = fmt
    if fill:
        x.fill = fill
    return x


def _title(ws, text, sub):
    ws["A1"] = text
    ws["A1"].font = Font(name=FONT, bold=True, size=13)
    ws["A2"] = sub
    ws["A2"].font = Font(name=FONT, italic=True)


def _sheet_story(wb, rows, story_order):
    ws = wb.create_sheet("Theo tang")
    _title(ws, "KHỐI LƯỢNG THEO TẦNG", "Bê tông m³ · ván khuôn m² · cốt thép kg")
    heads = ["Tầng", "Cấu kiện", "Bê tông (m³)", "Ván khuôn (m²)",
             "Thép d≤10 (kg)", "Thép d≤18 (kg)", "Thép d>18 (kg)", "Tổng thép (kg)"]
    for c, h in enumerate(heads, 1):
        _cell(ws, 4, c, h, bold=True, fill=HEAD, wrap=True, align="center")
    r = 5
    for row in sorted(rows, key=lambda x: (story_order.get(x["story"], 0), ELEMENTS.index(x["element"]))):
        _cell(ws, r, 1, row["story"])
        _cell(ws, r, 2, row["element"])
        _cell(ws, r, 3, round(row["concrete"], 3), fmt="#,##0.000")
        _cell(ws, r, 4, round(row["formwork"], 2), fmt="#,##0.00")
        for i, g in enumerate(GROUPS):
            _cell(ws, r, 5 + i, round(row["steel"].get(g, 0.0), 1), fmt="#,##0.0")
        _cell(ws, r, 8, f"=SUM(E{r}:G{r})", fmt="#,##0.0")
        r += 1
    last = r - 1
    _cell(ws, r, 1, "TỔNG", bold=True, fill=TOTAL)
    _cell(ws, r, 2, "", fill=TOTAL)
    for c in range(3, 9):
        col = get_column_letter(c)
        _cell(ws, r, c, f"=SUM({col}5:{col}{last})", bold=True, fill=TOTAL,
              fmt="#,##0.000" if c == 3 else ("#,##0.00" if c == 4 else "#,##0.0"))
    for col, w in zip("ABCDEFGH", (12, 10, 14, 15, 15, 15, 15, 15)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A5"
    return last


def _sheet_summary(wb, last):
    ws = wb.active
    ws.title = "Tong hop"
    _title(ws, "BẢNG TỔNG HỢP KHỐI LƯỢNG KẾT CẤU", "Tổng hợp từ sheet Theo tang (công thức SUMIFS)")
    heads = ["Cấu kiện", "Bê tông (m³)", "Ván khuôn (m²)", "Thép d≤10 (tấn)",
             "Thép d≤18 (tấn)", "Thép d>18 (tấn)", "Tổng thép (tấn)", "Hàm lượng (kg/m³)"]
    for c, h in enumerate(heads, 1):
        _cell(ws, 4, c, h, bold=True, fill=HEAD, wrap=True, align="center")
    src = "'Theo tang'!"
    rng = lambda col: f"{src}${col}$5:${col}${last}"
    for i, e in enumerate(ELEMENTS):
        r = 5 + i
        _cell(ws, r, 1, e, bold=True)
        crit = f'{rng("B")},$A{r}'
        _cell(ws, r, 2, f"=SUMIFS({rng('C')},{crit})", fmt="#,##0.0")
        _cell(ws, r, 3, f"=SUMIFS({rng('D')},{crit})", fmt="#,##0.0")
        for k, col in enumerate("EFG"):
            _cell(ws, r, 4 + k, f"=SUMIFS({rng(col)},{crit})/1000", fmt="#,##0.00")
        _cell(ws, r, 7, f"=SUM(D{r}:F{r})", fmt="#,##0.00")
        _cell(ws, r, 8, f"=IF(B{r}=0,0,G{r}*1000/B{r})", fmt="#,##0")
    t = 5 + len(ELEMENTS)
    _cell(ws, t, 1, "TỔNG", bold=True, fill=TOTAL)
    for c in range(2, 8):
        col = get_column_letter(c)
        _cell(ws, t, c, f"=SUM({col}5:{col}{t - 1})", bold=True, fill=TOTAL,
              fmt="#,##0.0" if c <= 3 else "#,##0.00")
    _cell(ws, t, 8, f"=IF(B{t}=0,0,G{t}*1000/B{t})", bold=True, fill=TOTAL, fmt="#,##0")
    ws.cell(t + 2, 1, "Ghi chú: dầm tính phần dưới sàn b×(h−t_sàn)×Lc; sàn trừ chỗ giao cột, vách; "
                      "thép dầm, cột theo kết quả thiết kế; thép sàn, vách theo lưới mặc định."
            ).font = Font(name=FONT, italic=True, size=10)
    for col, w in zip("ABCDEFGH", (12, 14, 15, 15, 15, 15, 15, 15)):
        ws.column_dimensions[col].width = w


def _sheet_notes(wb, rows, story_order):
    """Diễn giải theo kiểu Eta: mỗi tầng -> mỗi công tác -> các dòng diễn giải. Có bộ lọc theo tầng."""
    from .report import work_items
    ws = wb.create_sheet("Dien giai")
    _title(ws, "DIỄN GIẢI KHỐI LƯỢNG THEO TẦNG", "Dùng nút lọc ở cột Tầng để xem 1 tầng")
    heads = ["Tầng", "STT", "Tên công việc / diễn giải", "Đơn vị", "Khối lượng"]
    for c, h in enumerate(heads, 1):
        _cell(ws, 4, c, h, bold=True, fill=HEAD, align="center")
    r = 5
    for st in sorted({x["story"] for x in rows}, key=lambda n: -story_order.get(n, 0)):
        for it in work_items(rows, st, story_order):
            if it["qty"] <= 1e-9:
                continue
            fmt = "#,##0.000"
            for c, v in enumerate([st, it["stt"], it["name"], it["unit"], round(it["qty"], 4)], 1):
                _cell(ws, r, c, v, bold=True, fmt=fmt if c == 5 else None, align="center" if c in (2, 4) else None)
            r += 1
            for text, v in it["lines"]:
                for c, val in enumerate([st, "", "   " + text, it["unit"], round(v, 4)], 1):
                    _cell(ws, r, c, val, italic=True, fmt=fmt if c == 5 else None, align="center" if c == 4 else None)
                    ws.cell(r, c).font = Font(name=FONT, italic=True, size=10)
                r += 1
    ws.auto_filter.ref = f"A4:E{r - 1}"
    for col, w in zip("ABCDE", (11, 6, 95, 8, 14)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A5"


def _sheet_tienluong(wb, rows, story_order, last, project_name):
    """Bảng tiên lượng kiểu Eta, chọn tầng ở ô C3 (danh sách thả xuống); khối lượng = SUMIFS từ 'Theo tang'."""
    from openpyxl.worksheet.datavalidation import DataValidation
    from .report import work_items
    ws = wb.create_sheet("Tien luong", 0)
    ws["A1"] = "BẢNG TIÊN LƯỢNG KẾT CẤU BÊ TÔNG CỐT THÉP"
    ws["A1"].font = Font(name=FONT, bold=True, size=14)
    ws["A2"] = f"Công trình: {project_name}"
    ws["A2"].font = Font(name=FONT, italic=True)
    ws["A3"] = "Tầng:"
    ws["A3"].font = Font(name=FONT, bold=True)
    ALL = "Toàn công trình"
    ws["C3"] = ALL
    ws["C3"].font = Font(name=FONT, bold=True, color="0000FF")
    ws["C3"].fill = PatternFill("solid", fgColor="FFFF00")
    ws["C3"].border = BOX
    ws["D3"] = "← bấm vào ô vàng để chọn tầng"
    ws["D3"].font = Font(name=FONT, italic=True, color="808080")
    stories = sorted({x["story"] for x in rows}, key=lambda n: -story_order.get(n, 0))
    for i, st in enumerate([ALL] + stories):                 # danh sách cho ô chọn (cột ẩn H)
        ws.cell(1 + i, 8, st)
    ws.column_dimensions["H"].hidden = True
    dv = DataValidation(type="list", formula1=f"=$H$1:$H${len(stories) + 1}", allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("C3")

    heads = ["Ký hiệu", "STT", "Tên công việc", "Đơn vị", "Khối lượng"]
    for c, h in enumerate(heads, 1):
        _cell(ws, 5, c, h, bold=True, fill=HEAD, align="center")
    src = "'Theo tang'!"
    col = {"concrete": "C", "formwork": "D", "d≤10": "E", "d≤18": "F", "d>18": "G"}
    crit_story = f'IF($C$3="{ALL}","*",$C$3)'
    r = 6
    for it in work_items(rows, None, story_order):
        key = it["group"] if it["work"] == "steel" else it["work"]
        c = col[key]
        f = (f"=SUMIFS({src}${c}$5:${c}${last},{src}$B$5:$B${last},\"{it['element']}\","
             f"{src}$A$5:$A${last},{crit_story})" + ("/1000" if it["work"] == "steel" else ""))
        for cc, v in enumerate(["PeRC", it["stt"], it["name"], it["unit"], f], 1):
            _cell(ws, r, cc, v, fmt="#,##0.000" if cc == 5 else None, align="center" if cc in (2, 4) else None)
        r += 1
    ws.cell(r + 1, 1, "Diễn giải chi tiết từng tầng: sheet \"Dien giai\" (lọc theo tầng). "
                      "Đơn vị: bê tông m³, ván khuôn m², cốt thép tấn.").font = Font(name=FONT, italic=True, size=10)
    for c_, w in zip("ABCDE", (12, 6, 52, 8, 16)):
        ws.column_dimensions[c_].width = w
    ws.freeze_panes = "A6"


def write_quantity_excel(rows, project, path):
    import os
    story_order = {s["name"]: i for i, s in enumerate(project["stories"])}
    wb = Workbook()
    last = _sheet_story(wb, rows, story_order)
    _sheet_summary(wb, last)
    _sheet_notes(wb, rows, story_order)
    name = os.path.basename(project.get("model_file", "").replace("\\", "/"))
    _sheet_tienluong(wb, rows, story_order, last, name)
    wb.active = 0
    wb.save(path)
