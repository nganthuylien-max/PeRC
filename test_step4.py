"""Thử vẽ 1 mặt cắt dầm 300×600 đơn giản -> test.svg + test.dxf"""
from drawing.model import Drawing, rounded_rect, hook135
from drawing.export import to_svg, to_dxf

S = 10                                   # tỉ lệ 1:10
D = Drawing(S)
b, h, cover, ds = 300, 600, 25, 8

D.rect(0, 0, b, h)                                           # bê tông
c = cover + ds / 2
rounded_rect(D, c, c, b - c, h - c, 2 * ds)                  # cốt đai (đường tim)
hook135(D, c + 5, h - c, 0.707, -0.707, 60)                  # 2 móc 135°
hook135(D, c, h - c - 5, 0.707, -0.707, 60)

y_bot = cover + ds + 10                                      # 3Ø20 thớ dưới
xs = [cover + ds + 10, b / 2, b - cover - ds - 10]
for x in xs:
    D.circle(x, y_bot, 10, "THEP", filled=True)
for x in (xs[0], xs[-1]):                                    # 2Ø16 thớ trên
    D.circle(x, h - cover - ds - 8, 8, "THEP", filled=True)

D.dim_chain_h([0] + xs + [b], 0, -7 * S)                     # dim chuỗi + dim tổng
D.dim((0, 0), (b, 0), (0, -13 * S))
D.dim_chain_v([0, y_bot, h - cover - ds - 8, h], 0, -7 * S)
D.dim((0, 0), (0, h), (-13 * S, 0), vertical=True)

D.tag(b + 11 * S, -5 * S, 1, "3Ø20", [(x, y_bot, 10) for x in xs])
D.tag(b + 11 * S, h + 5 * S, 2, "2Ø16", [(x, h - cover - ds - 8, 8) for x in (xs[0], xs[-1])])
D.tag(b + 11 * S, h * 0.55, 3, "Ø8a150", [(b - c, h * 0.55 - 20, 4)])
D.title(b / 2, -24 * S, "1 - 1", "Mặt cắt thử – TL 1:10")

open("test.svg", "w", encoding="utf-8").write(to_svg(D))
print("Đã ghi test.svg")
to_dxf(D, "test.dxf")
print("Đã ghi test.dxf")