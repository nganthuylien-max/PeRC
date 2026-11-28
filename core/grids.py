"""Tên trục (lưới trục ETABS) cho dầm và cột: dùng để ghi bong bóng trục và tên nhịp trên bản vẽ.
Nếu project.json chưa có lưới trục (đọc từ bản cũ), tự suy ra từ tọa độ cột: phương X đánh 1, 2, 3...,
phương Y đánh A, B, C... (giống quy ước thường dùng)."""
import string

TOL = 60       # mm: điểm cách đường trục không quá 60 mm thì coi là nằm trên trục


def _cluster(values, tol=TOL):
    out = []
    for v in sorted(values):
        if not out or v - out[-1][-1] > tol:
            out.append([v])
        else:
            out[-1].append(v)
    return [sum(c) / len(c) for c in out]


def _letters(i):
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = string.ascii_uppercase[r] + s
    return s


class Grids:
    def __init__(self, project):
        g = project.get("grids") or []
        self.lines = {"X": [(x["coord"], x["id"]) for x in g if x["axis"] == "X"],
                      "Y": [(x["coord"], x["id"]) for x in g if x["axis"] == "Y"]}
        self.auto = not (self.lines["X"] and self.lines["Y"])
        if self.auto:                                   # suy trục từ vị trí cột
            pts = [c["j"] for c in project.get("columns", []) if c.get("j")]
            xs = _cluster([p[0] for p in pts])
            ys = _cluster([p[1] for p in pts])
            self.lines = {"X": [(x, str(i + 1)) for i, x in enumerate(xs)],
                          "Y": [(y, _letters(i)) for i, y in enumerate(ys)]}

    def name(self, axis, coord):
        best = min(self.lines[axis], key=lambda t: abs(t[0] - coord), default=None)
        return best[1] if best and abs(best[0] - coord) <= TOL else None

    def beam(self, beam):
        """(trục đầu trái, trục đầu phải, trục dầm nằm trên) – None nếu không trùng trục nào."""
        (x1, y1), (x2, y2) = beam["i"][:2], beam["j"][:2]
        if abs(x2 - x1) >= abs(y2 - y1):               # dầm theo phương X: 2 đầu ở trục X, dầm nằm trên trục Y
            return self.name("X", x1), self.name("X", x2), self.name("Y", (y1 + y2) / 2)
        return self.name("Y", y1), self.name("Y", y2), self.name("X", (x1 + x2) / 2)

    def column(self, col):
        """Tên giao điểm trục của cột, ví dụ 'B-3' (None nếu không nằm trên lưới)."""
        x, y = col["j"][:2]
        a, b = self.name("Y", y), self.name("X", x)
        return f"{a}-{b}" if a and b else (a or b)


def beam_context(project, grids, res):
    """(axes, level) cho bản vẽ dầm: tên trục 2 gối + trục dầm, và (tên tầng, cao độ mặt dầm m)."""
    from drawing.model import story_vn
    bm = next((b for b in project["beams"] if b["id"] == res["id"]), None)
    axes = grids.beam(bm) if bm and bm.get("i") and bm.get("j") else None
    z = next((s["elevation"] for s in project.get("stories", []) if s["name"] == res["story"]), None)
    level = (story_vn(res["story"]), z / 1000) if z is not None else None
    return axes, level
