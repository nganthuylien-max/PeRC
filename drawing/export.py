"""Xuất Drawing ra SVG (xem trong app / trình duyệt) và DXF AutoCAD 2018 (thư viện ezdxf)."""
import math
from html import escape

from .model import LAYERS


# ============================================================================ SVG
def dim_text_pos(e, S):
    """Vị trí chữ của đường kích thước (giữa đoạn, trên đường; hoặc bên kia nếu flip)."""
    (x1, y1), (x2, y2), (bx, by) = e["p1"], e["p2"], e["base"]
    if not e["vertical"]:
        return ((x1 + x2) / 2, by - 3.0 * S) if e.get("flip") else ((x1 + x2) / 2, by + 0.6 * S)
    return (bx + 3.0 * S, (y1 + y2) / 2) if e.get("flip") else (bx - 0.6 * S, (y1 + y2) / 2)


def _expand_dim(e, S):
    """Đường kích thước -> các nét + chữ (SVG không có đối tượng 'dimension')."""
    (x1, y1), (x2, y2), (bx, by) = e["p1"], e["p2"], e["base"]
    out = []
    if not e["vertical"]:
        sgn = 1 if by > y1 else -1
        for x, y in ((x1, y1), (x2, y2)):
            out.append(("line", (x, y + sgn * 1.0 * S), (x, by + sgn * 1.5 * S)))   # đường gióng
            out.append(("line", (x - S, by - S), (x + S, by + S)))                  # gạch chéo
        out.append(("line", (min(x1, x2) - 1.5 * S, by), (max(x1, x2) + 1.5 * S, by)))
        out.append(("text", dim_text_pos(e, S), f"{abs(x2 - x1) * e.get('lfac', 1):.0f}", 0))
    else:
        sgn = 1 if bx > x1 else -1
        for x, y in ((x1, y1), (x2, y2)):
            out.append(("line", (x + sgn * 1.0 * S, y), (bx + sgn * 1.5 * S, y)))
            out.append(("line", (bx - S, y - S), (bx + S, y + S)))
        out.append(("line", (bx, min(y1, y2) - 1.5 * S), (bx, max(y1, y2) + 1.5 * S)))
        out.append(("text", dim_text_pos(e, S), f"{abs(y2 - y1) * e.get('lfac', 1):.0f}", 90))
    return out


def to_svg(D, margin=8.0):
    x0, y0, x1, y1 = D.bbox()
    m = margin * D.S
    x0, y0, x1, y1 = x0 - m, y0 - m, x1 + m, y1 + m
    W, H, lw = x1 - x0, y1 - y0, 0.18 * D.S
    P = lambda x, y: (x - x0, y1 - y)                  # SVG có trục y hướng xuống -> lật lại

    def svg_text(x, y, s, h, col, ha, va, rot):
        sx, sy = P(x, y)
        shift = {"bottom": 0, "middle": h / 2, "top": h}[va]
        anchor = {"left": "start", "center": "middle", "right": "end"}[ha]
        if rot:
            a = math.radians(rot)
            bx, by = sx + shift * math.sin(a), sy + shift * math.cos(a)
            tr = f' transform="rotate({-rot} {bx:.1f} {by:.1f})"'
        else:
            bx, by, tr = sx, sy + shift, ""
        return (f'<text x="{bx:.1f}" y="{by:.1f}" font-size="{h / 0.72:.1f}" fill="{col}" '
                f'text-anchor="{anchor}"{tr}>{escape(s)}</text>')

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" '
           f'font-family="Arial, sans-serif"><rect width="{W:.0f}" height="{H:.0f}" fill="#fff"/>']
    for e in D.ents:
        col = LAYERS[e["layer"]][1]
        w = lw * (1.6 if e["layer"] == "BETONG" else 1.0)
        if e["t"] == "line":
            (a, b), (c, d) = P(*e["p"][0]), P(*e["p"][1])
            out.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d:.1f}" stroke="{col}" stroke-width="{w:.1f}"/>')
        elif e["t"] == "pline":
            pts, n = e["p"], len(e["p"])
            sx, sy = P(*pts[0])
            path = [f"M{sx:.1f},{sy:.1f}"]
            for i in range(n if e["closed"] else n - 1):
                p, q, bu = pts[i], pts[(i + 1) % n], e["b"][i]
                qx, qy = P(*q)
                if abs(bu) < 1e-9:
                    path.append(f"L{qx:.1f},{qy:.1f}")
                else:                                   # cung tròn từ bulge
                    th = 4 * math.atan(abs(bu))
                    r = math.dist(p, q) / (2 * math.sin(th / 2))
                    path.append(f"A{r:.1f},{r:.1f} 0 0 {0 if bu > 0 else 1} {qx:.1f},{qy:.1f}")
            if e["closed"]:
                path.append("Z")
            out.append(f'<path d="{" ".join(path)}" fill="none" stroke="{col}" stroke-width="{w * 1.3:.1f}"/>')
        elif e["t"] == "circle":
            cx, cy = P(*e["c"])
            fill = col if e["fill"] else "none"
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{e["r"]:.1f}" fill="{fill}" stroke="{col}" stroke-width="{lw:.1f}"/>')
        elif e["t"] == "text":
            out.append(svg_text(*e["p"], e["s"], e["h"], col, e["ha"], e["va"], e["rot"]))
        elif e["t"] == "dim":
            for kind, a, b, *rest in _expand_dim(e, e.get("S", D.S)):
                if kind == "line":
                    (p, q), (r_, s_) = P(*a), P(*b)
                    out.append(f'<line x1="{p:.1f}" y1="{q:.1f}" x2="{r_:.1f}" y2="{s_:.1f}" stroke="{col}" stroke-width="{lw:.1f}"/>')
                else:
                    out.append(svg_text(*a, b, 2.2 * e.get("S", D.S), col, "center", "bottom", rest[0]))
    out.append("</svg>")
    return "\n".join(out)


# ============================================================================ DXF
ALIGN = {("left", "bottom"): "LEFT", ("center", "bottom"): "CENTER", ("right", "bottom"): "RIGHT",
         ("left", "middle"): "MIDDLE_LEFT", ("center", "middle"): "MIDDLE_CENTER",
         ("right", "middle"): "MIDDLE_RIGHT", ("left", "top"): "TOP_LEFT",
         ("center", "top"): "TOP_CENTER", ("right", "top"): "TOP_RIGHT"}


def to_dxf(D, path):
    """Ghi file DXF AutoCAD 2018: layer có màu, đường kích thước THẬT (DIMENSION), chữ tiếng Việt."""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment

    doc = ezdxf.new("R2018")
    doc.units = ezdxf.units.MM
    doc.styles.get("Standard").dxf.font = "arial.ttf"         # font có dấu tiếng Việt
    for name, (aci, _) in LAYERS.items():
        doc.layers.add(name, color=aci)
    styles = {(e.get("S", D.S), e.get("lfac", 1.0)) for e in D.ents if e["t"] == "dim"} | {(D.S, 1.0)}
    for sc, lf in sorted(styles):
        doc.dimstyles.new(f"PERC_{sc:g}_{lf:g}", dxfattribs={
            "dimscale": sc,       # các kích thước dưới đây là mm GIẤY, nhân với tỉ lệ
            "dimlfac": lf,        # hệ số đo: hình phóng to k lần thì ghi số thật = đo × 1/k
            "dimtxt": 2.2, "dimtsz": 1.0, "dimasz": 1.0,           # chữ 2.2, đầu mút kiểu gạch chéo
            "dimexe": 1.5, "dimexo": 1.0, "dimgap": 0.6,
            "dimtad": 1, "dimdec": 0, "dimtih": 0, "dimtoh": 0,     # chữ nằm trên đường kích thước
            "dimtmove": 2,                                          # cho phép đặt chữ tự do
            "dimclrd": 4, "dimclre": 4, "dimclrt": 4})
    msp = doc.modelspace()

    for e in D.ents:
        at = {"layer": e["layer"]}
        if e["t"] == "line":
            msp.add_line(e["p"][0], e["p"][1], dxfattribs=at)
        elif e["t"] == "pline":
            pts = [(x, y, b) for (x, y), b in zip(e["p"], e["b"])]
            msp.add_lwpolyline(pts, format="xyb", close=e["closed"], dxfattribs=at)
        elif e["t"] == "circle":
            msp.add_circle(e["c"], e["r"], dxfattribs=at)
            if e["fill"]:                                       # tô đặc thanh thép bằng HATCH
                hatch = msp.add_hatch(color=256, dxfattribs=at)
                hatch.paths.add_edge_path().add_arc(e["c"], e["r"], 0, 360)
        elif e["t"] == "text":
            t = msp.add_text(e["s"], height=e["h"], rotation=e["rot"], dxfattribs=at)
            t.set_placement(e["p"], align=TextEntityAlignment[ALIGN[(e["ha"], e["va"])]])
        elif e["t"] == "dim":
            kw = {}
            sc = e.get("S", D.S)
            if e.get("flip"):                                   # đoạn ngắn: chữ sang phía bên kia
                tx, ty = dim_text_pos(e, sc)
                kw["location"] = (tx - 1.1 * sc, ty) if e["vertical"] else (tx, ty + 1.1 * sc)
            dim = msp.add_linear_dim(base=e["base"], p1=e["p1"], p2=e["p2"],
                                     angle=90 if e["vertical"] else 0,
                                     dimstyle=f"PERC_{sc:g}_{e.get('lfac', 1.0):g}", dxfattribs=at, **kw)
            dim.render()
    doc.saveas(path)
