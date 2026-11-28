"""Bảng thống kê cốt thép và khung ghi chú chung – trình bày như bản vẽ thi công.
Số liệu lấy từ cùng nguồn với bóc khối lượng (beam_detailing / quantity.takeoff) nên luôn khớp nhau."""
from core.beam_detailing import unit_weight

# cột: (tiêu đề, bề rộng mm giấy)
COLS = [("SỐ\nHIỆU", 12), ("HÌNH DẠNG – KÍCH THƯỚC", 62), ("Ø\n(mm)", 13), ("DÀI 1 THANH\n(mm)", 24),
        ("SỐ\nLƯỢNG", 16), ("TỔNG DÀI\n(m)", 20), ("KHỐI LƯỢNG\n(kg)", 22)]
ROW_H, HEAD_H, TITLE_H = 9.0, 13.0, 11.0


def _text_lines(D, x, y, s, h, ha="center"):
    lines = s.split("\n")
    for i, ln in enumerate(lines):
        D.text(x, y + (len(lines) - 1) / 2 * h * 1.5 * D.S - i * h * 1.5 * D.S, ln, h, "TEXT", ha, "middle")


def _shape(D, cx, cy, w, sh):
    """Vẽ hình dạng thanh trong ô: thanh thẳng có móc 2 đầu, hoặc cốt đai chữ nhật."""
    S = D.S
    if sh[0] == "bar":
        _, hk0, L, hk1, up = sh
        x0, x1 = cx - 0.32 * w, cx + 0.32 * w
        y = cy - 1.2 * S if up else cy + 1.5 * S
        dy = 3.0 * S if up else -3.0 * S
        D.line(x0, y, x1, y, "THEP")
        D.text(cx, y + 0.6 * S if up else y - 0.6 * S, f"{L:.0f}", 2.2, "TEXT", "center", "bottom" if up else "top")
        for xe, hk, ha in ((x0, hk0, "right"), (x1, hk1, "left")):
            if hk:
                D.line(xe, y, xe, y + dy, "THEP")
                D.text(xe + (-1 if ha == "right" else 1) * 1.0 * S, y + dy / 2, f"{hk:.0f}", 2.2, "TEXT", ha, "middle")
    else:                                                   # ("stir", rộng, cao, móc)
        _, bw, bh, hk = sh
        k = min(0.3 * w / max(bw, 1), 6.0 * S / max(bh, 1))
        rw, rh = bw * k, bh * k
        D.rect(cx - rw / 2, cy - rh / 2, rw, rh, "THEP_DAI")
        D.text(cx - rw / 2 - 1.0 * S, cy, f"{bw:.0f}", 2.2, "TEXT", "right", "middle")
        D.text(cx + rw / 2 + 1.0 * S, cy, f"{bh:.0f}", 2.2, "TEXT", "left", "middle")
        D.text(cx, cy - rh / 2 - 0.5 * S, f"móc {hk:.0f}", 2.0, "TEXT", "center", "top")


def steel_table(D, x, y, rows, title="BẢNG THỐNG KÊ CỐT THÉP"):
    """rows = [{"mark", "shape", "d", "length" (mm), "n"}]; góc trên trái tại (x, y). Trả về tổng khối lượng (kg)."""
    S = D.S
    W = sum(w for _, w in COLS) * S
    H = (TITLE_H + HEAD_H + ROW_H * (len(rows) + 1)) * S
    D.rect(x, y - H, W, H, "TEXT")
    D.text(x + W / 2, y - TITLE_H * S / 2, title, 4.0, "TITLE", "center", "middle")
    yh = y - TITLE_H * S
    D.line(x, yh, x + W, yh, "TEXT")
    xs = [x]
    for _, w in COLS:
        xs.append(xs[-1] + w * S)
    yr = yh - HEAD_H * S
    for (name, _), a, b in zip(COLS, xs, xs[1:]):
        _text_lines(D, (a + b) / 2, (yh + yr) / 2, name, 2.2)
    for a in xs[1:-1]:
        D.line(a, yh, a, y - H, "TEXT")
    total = 0.0
    yy = yr
    for r in rows:
        D.line(x, yy, x + W, yy, "TEXT")
        ym = yy - ROW_H * S / 2
        kg = r["n"] * r["length"] / 1000 * unit_weight(r["d"])
        total += kg
        vals = [str(r["mark"]), None, f"{r['d']}", f"{r['length']:.0f}", f"{r['n']}",
                f"{r['n'] * r['length'] / 1000:.2f}", f"{kg:.2f}"]
        for v, a, b in zip(vals, xs, xs[1:]):
            if v is None:
                _shape(D, (a + b) / 2, ym, b - a, r["shape"])
            else:
                D.text((a + b) / 2, ym, v, 2.5, "TEXT", "center", "middle")
        yy -= ROW_H * S
    D.line(x, yy, x + W, yy, "TEXT")
    ym = yy - ROW_H * S / 2
    D.text((xs[0] + xs[5]) / 2, ym, "TỔNG CỘNG", 2.5, "TITLE", "center", "middle")
    D.text((xs[6] + xs[7]) / 2, ym, f"{total:.2f}", 2.5, "TITLE", "center", "middle")
    return total


def notes(D, x, y, lines):
    """Khung GHI CHÚ chung (gạch đầu dòng)."""
    S = D.S
    D.text(x, y, "GHI CHÚ:", 3.0, "TITLE", "left", "top")
    for i, ln in enumerate(lines):
        D.text(x + 2 * S, y - (6 + i * 5) * S, f"•  {ln}", 2.5, "TEXT", "left", "top")


def beam_rows(det, marks, b, h, cover=25):
    """Bảng thép 1 dầm từ kết quả triển khai thép (beam_detailing) – khớp với bóc khối lượng."""
    from .sections import _mark
    agg = {}
    for bar in det["bars"]:
        face, group = bar["face"], bar["key"][1]
        if face == "side":
            m = _mark(marks, "bar", "side", "side", "M")
        else:
            m = _mark(marks, "bar", face, group, bar["key"][2] if len(bar["key"]) > 2 else "L")
        a = agg.setdefault(m["mark"], {"mark": m["mark"], "d": bar["d"], "n": 0, "length": 0.0,
                                       "shape": ("bar", bar["hook0"], bar["x1"] - bar["x0"], bar["hook1"],
                                                 face == "bot")})
        a["n"] += bar["n"]
        a["length"] = max(a["length"], bar["length"])
    st = det["stirrups"]
    if st:
        m = next(m for m in marks if m["kind"] == "stir")
        ds = st[0]["d"]
        agg[m["mark"]] = {"mark": m["mark"], "d": ds, "n": sum(z["count"] for z in st), "length": st[0]["length"],
                          "shape": ("stir", b - 2 * cover, h - 2 * cover, 10 * ds)}
    return [agg[k] for k in sorted(agg)]


def general_notes(conc, cover_beam=25, cover_col=30):
    return [f"Bê tông {conc}",
            "Cốt thép dọc CB400-V, cốt đai CB240-T",
            f"Lớp bê tông bảo vệ: dầm {cover_beam} mm, cột {cover_col} mm",
            "Chiều dài neo cốt thép dọc ≥ 40d (có móc ≥ 10d)",
            "Nối chồng cốt thép cột: max(40d; 500 mm), ngay trên mặt sàn mỗi tầng",
            "Kích thước ghi bằng mm, cao độ ghi bằng m"]
