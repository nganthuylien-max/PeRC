"""Vật liệu theo TCVN 5574:2018. Đơn vị: MPa (N/mm2)."""
import math
import re

# Cấp bê tông: (Rb, Rbt, Eb) – cường độ tính toán, mô đun đàn hồi
CONCRETE = {
    "B15": (8.5, 0.75, 24000), "B20": (11.5, 0.90, 27500),
    "B25": (14.5, 1.05, 30000), "B30": (17.0, 1.15, 32500),
    "B35": (19.5, 1.30, 34500), "B40": (22.0, 1.40, 36000),
    "B45": (25.0, 1.50, 37000), "B50": (27.5, 1.60, 38000),
}

# Thép: (Rs, Rsc, Rsw)
STEEL = {
    "CB240-T": (210, 210, 170),
    "CB300-V": (260, 260, 210),
    "CB400-V": (350, 350, 280),
    "CB500-V": (435, 400, 300),
}

ES = 200000.0    # mô đun đàn hồi thép (MPa)
EPS_B2 = 0.0035  # biến dạng nén cực hạn của bê tông


def bar_area(d):
    """Diện tích 1 thanh thép đường kính d (mm2)."""
    return math.pi * d * d / 4


class Concrete:
    """Cấp bê tông lấy từ tên vật liệu ETABS (B30, "BT B30"...). Tên không có cấp B thì suy từ fc' (MPa)
    mà ETABS lưu: B ≈ fc'/0,78 (fc' mẫu trụ ≈ 0,78 cường độ mẫu lập phương), lấy cấp có sẵn gần nhất."""
    def __init__(self, name, gamma_b1=1.0, fc=None):
        m = re.search(r"B\s*(\d+(?:[.,]5)?)", name.upper())
        if m and f"B{m.group(1)}" in CONCRETE:
            self.grade = f"B{m.group(1)}"
            self.source = "tên vật liệu"
        elif fc:
            target = fc / 0.78
            self.grade = min(CONCRETE, key=lambda g: abs(float(g[1:]) - target))
            self.source = f"fc' = {fc:g} MPa"
        else:
            self.grade = "B25"
            self.source = "mặc định (không đọc được cấp bê tông)"
        Rb, Rbt, Eb = CONCRETE[self.grade]
        self.Rb = Rb * gamma_b1
        self.Rbt = Rbt * gamma_b1
        self.Eb = Eb


class Steel:
    def __init__(self, grade):
        self.grade = grade
        self.Rs, self.Rsc, self.Rsw = STEEL[grade]
        self.Es = ES

    @property
    def xi_R(self):
        """ξR = 0.8 / (1 + εs,el/εb2)"""
        eps_el = self.Rs / self.Es
        return 0.8 / (1 + eps_el / EPS_B2)

    @property
    def alpha_R(self):
        return self.xi_R * (1 - 0.5 * self.xi_R)