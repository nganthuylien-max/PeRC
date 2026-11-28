"""Chọn và xếp thép dọc trong tiết diện dầm."""
import math
from .materials import bar_area

DIAMS = [14, 16, 18, 20, 22, 25, 28]
ZONES = ("L", "M", "R")
CONT_RATIO = {"top": 0.25, "bot": 0.5}    # thép suốt tối thiểu / As lớn nhất của thớ (thớ dưới: >= 50% thép nhịp vào gối, TCVN 5574:2018 10.3.3.5)


def layer_capacity(b, cover, ds, d, face):
    """Số thanh tối đa xếp được trong 1 lớp."""
    clear = max(d, 25 if face == "bot" else 30)
    avail = b - 2 * (cover + ds)
    return max(2, int((avail + clear) // (d + clear)))


def second_layer_x(xs, n2, b):
    """Vị trí thanh lớp 2: đối xứng qua trục dầm, thẳng hàng với thanh lớp 1 (để đổ bê tông lọt),
    xếp từng cặp từ 2 góc vào trong; lẻ 1 thanh thì đặt giữa."""
    out, i, j = [], 0, len(xs) - 1
    while len(out) + 2 <= n2 and i < j:
        out += [xs[i], xs[j]]
        i, j = i + 1, j - 1
    if len(out) < n2:
        out.append(b / 2)
    return sorted(out)


def place_face(b, cover, ds, cont, add, face):
    """Tọa độ từng thanh của 1 thớ. x đo từ mép trái, y đo từ mép thớ.
    cont = (n, d) thép suốt; add = (n, d) thép gia cường hoặc None."""
    n_c, d_c = cont
    n_a, d_a = add if add and add[0] > 0 else (0, 0)
    dmax = max(d_c, d_a)
    cap = layer_capacity(b, cover, ds, dmax, face)
    n1_add = max(0, min(n_a, cap - n_c))       # gia cường xếp được ở lớp 1
    n2 = n_a - n1_add                          # phần còn lại xuống lớp 2
    n1 = n_c + n1_add

    x0 = cover + ds + dmax / 2
    xs = [x0 + i * (b - 2 * x0) / (n1 - 1) for i in range(n1)]
    cont_idx = {round(i * (n1 - 1) / (n_c - 1)) for i in range(n_c)}   # thép suốt rải đều, có 2 góc

    bars = []
    for i, x in enumerate(xs):
        d = d_c if i in cont_idx else d_a
        bars.append({"x": x, "y": cover + ds + d / 2, "d": d,
                     "group": "cont" if i in cont_idx else "add", "layer": 1})
    if n2 > 0:
        y2 = cover + ds + dmax + max(25, dmax) + d_a / 2
        for x in second_layer_x(xs, n2, b):
            bars.append({"x": x, "y": y2, "d": d_a, "group": "add", "layer": 2})

    As = sum(bar_area(t["d"]) for t in bars)
    a = sum(bar_area(t["d"]) * t["y"] for t in bars) / As        # trọng tâm thép
    clear = (xs[1] - xs[0]) - dmax if n1 > 1 else b
    return {"bars": bars, "As": As, "a": a, "layers": 2 if n2 else 1,
            "clear": clear, "fits": n2 <= cap}


def choose_face(b, cover, ds, L, reqs, face):
    """Chọn (thép suốt, thép gia cường theo vùng) có khối lượng nhỏ nhất. reqs = {vùng: As yêu cầu}."""
    req_max = max(reqs.values())
    best = None
    for ic, d_c in enumerate(DIAMS):
        for n_c in (2, 3):
            if n_c > layer_capacity(b, cover, ds, d_c, face):
                continue
            A_c = n_c * bar_area(d_c)
            if A_c < CONT_RATIO[face] * req_max:
                continue
            options = [None] + [d for d in DIAMS if abs(DIAMS.index(d) - ic) <= 1]
            for d_a in options:
                adds, cost, ok = {}, A_c * L, True
                for z in ZONES:
                    need = reqs[z] - A_c
                    if need <= 0:
                        adds[z] = (0, d_c)
                        continue
                    if d_a is None:
                        ok = False
                        break
                    n = math.ceil(need / bar_area(d_a))
                    if n_c + n > 2 * layer_capacity(b, cover, ds, max(d_c, d_a), face):
                        ok = False                        # quá 2 lớp -> loại
                        break
                    adds[z] = (n, d_a)
                    length = 0.6 * L if z == "M" else 0.25 * L + 30 * d_a   # chiều dài thanh gia cường
                    cost += n * bar_area(d_a) * length
                if not ok:
                    continue
                n_bars = n_c + sum(v[0] for v in adds.values())
                cost *= 1 + 0.04 * n_bars + (0.05 if d_c >= 28 else 0)     # phạt nhiều thanh, thanh quá to
                if best is None or cost < best["cost"]:
                    best = {"cont": (n_c, d_c), "add": adds, "cost": cost}
    if best is None:
        raise ValueError("Tiết diện quá nhỏ – không xếp đủ thép trong 2 lớp")
    return best