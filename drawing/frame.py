"""Khung bản vẽ (khổ giấy A3–A0, không có khung tên), và xếp nhiều khung trong 1 file DXF.
Mỗi dầm / mỗi cột nằm trong 1 khung riêng, các khung đặt cách xa nhau -> dễ in và dễ tìm."""
import datetime

from .model import Drawing

PAPERS = [("A3", 420, 297), ("A2", 594, 420), ("A1", 841, 594), ("A0", 1189, 841)]
M_LEFT, M_OTHER = 25, 10          # lề khung: trái 25 mm (đóng tập), các cạnh còn lại 10 mm
TB_H = 0                          # không vẽ khung tên (theo yêu cầu)


WARNINGS = []                      # khổ giấy người dùng chọn không đủ chỗ -> ghi lại để báo trong nhật ký


def framed(D, title, project_name="", scale_txt=None, sheet_no=None, paper=None):
    """Đặt bản vẽ D vào khung giấy (chỉ khung viền, không khung tên). paper = "A3" | "A2" | "A1" | "A0" | None (tự chọn khổ
    nhỏ nhất vừa nội dung). Khổ đã chọn không đủ chỗ ở tỉ lệ này thì tự nâng khổ và ghi cảnh báo."""
    S = D.S
    x0, y0, x1, y1 = D.bbox()
    cw, ch = (x1 - x0) / S, (y1 - y0) / S                      # kích thước nội dung trên giấy (mm)
    need_w, need_h = cw + M_LEFT + M_OTHER + 16, ch + 2 * M_OTHER + TB_H + 16
    fit = next(((n, w, h) for n, w, h in PAPERS if need_w <= w and need_h <= h), None)
    if fit is None:                                            # quá lớn: khổ A0 kéo dài
        fit = ("A0+", max(1189, need_w), max(841, need_h))
    chosen = next(((n, w, h) for n, w, h in PAPERS if n == paper), None)
    if chosen and need_w <= chosen[1] and need_h <= chosen[2]:
        fit = chosen
    elif chosen:
        WARNINGS.append(f"{title}: không vừa khổ {paper} ở tỉ lệ {scale_txt or f'1:{S:.0f}'} -> dùng khổ {fit[0]}")
    name, W, H = fit
    F = Drawing(S)
    F.rect(0, 0, W * S, H * S, "TEXT")                          # mép giấy
    bx0, by0, bx1, by1 = M_LEFT * S, M_OTHER * S, (W - M_OTHER) * S, (H - M_OTHER) * S
    F.rect(bx0, by0, bx1 - bx0, by1 - by0)                      # khung bản vẽ (nét đậm)
    # nội dung: căn giữa trong khung
    ax0, ax1 = bx0 + 8 * S, bx1 - 8 * S
    ay0, ay1 = by0 + 8 * S, by1 - 8 * S
    F.merge(D, (ax0 + ax1) / 2 - (x0 + x1) / 2, (ay0 + ay1) / 2 - (y0 + y1) / 2)
    return F


def layout_frames(frames, per_row=3, gap_mm=60):
    """Xếp các khung thành lưới, cách nhau gap_mm (theo tỉ lệ của khung lớn nhất)."""
    if not frames:
        return Drawing(25)
    S = max(f.S for f in frames)
    out = Drawing(S)
    x = y = row_h = 0.0
    gap = gap_mm * S
    for i, f in enumerate(frames):
        x0, y0, x1, y1 = f.bbox()
        if i and i % per_row == 0:
            x, y, row_h = 0.0, y - row_h - gap, 0.0
        out.merge(f, x - x0, y - y1)
        x += (x1 - x0) + gap
        row_h = max(row_h, y1 - y0)
    return out
