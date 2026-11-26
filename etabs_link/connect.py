"""Kết nối tới ETABS đang mở qua COM API (ETABS 18 trở lên)."""
import csv
import io
import subprocess

import comtypes.client

N_MM_C = 9  # mã đơn vị N, mm, độ C trong ETABS


def list_etabs():
    """Liệt kê mọi tiến trình ETABS.exe: [(pid, tiêu đề cửa sổ)].
    ETABS chạy ngầm không có cửa sổ -> tiêu đề là 'N/A'."""
    out = subprocess.run(
        ["tasklist", "/V", "/FI", "IMAGENAME eq ETABS.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, errors="replace").stdout
    found = []
    for row in csv.reader(io.StringIO(out)):
        if row and row[0].lower() == "etabs.exe":
            found.append((int(row[1]), row[-1]))   # cột 2 = PID, cột cuối = tiêu đề
    return found


def connect():
    """Bám vào ETABS đang có cửa sổ. Trả về (pid, SapModel)."""
    found = list_etabs()
    if not found:
        raise RuntimeError("Chưa mở ETABS.")
    visible = [(pid, title) for pid, title in found if "ETABS" in title]
    if not visible:
        raise RuntimeError("ETABS đang chạy ngầm, không có cửa sổ. Hãy mở ETABS bình thường.")
    if len(visible) > 1:
        raise RuntimeError(f"Đang mở {len(visible)} ETABS: {visible}. Hãy đóng bớt, chỉ để 1.")

    pid, title = visible[0]
    helper = comtypes.client.CreateObject("ETABSv1.Helper")
    import comtypes.gen.ETABSv1 as E          # module do comtypes tự sinh
    helper = helper.QueryInterface(E.cHelper)
    etabs = helper.GetObjectProcess("CSI.ETABS.API.ETABSObject", pid)
    if etabs is None:
        raise RuntimeError("Không bám được vào ETABS (thử đóng và mở lại ETABS).")
    return pid, etabs.SapModel