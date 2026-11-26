import csv, io, subprocess
import comtypes.client

# 1. Liệt kê mọi tiến trình ETABS.exe đang chạy (lệnh tasklist của Windows)
out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ETABS.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True).stdout
pids = [int(r[1]) for r in csv.reader(io.StringIO(out)) if r and r[0].lower() == "etabs.exe"]
print("ETABS đang chạy, PID:", pids)
if not pids:
    raise SystemExit("Chưa mở ETABS")

# 2. Tạo Helper như cũ
helper = comtypes.client.CreateObject("ETABSv1.Helper")
import comtypes.gen.ETABSv1 as E
helper = helper.QueryInterface(E.cHelper)

# 3. Bám vào từng ETABS theo PID để xem mỗi cái đang mở file gì
for pid in pids:
    etabs = helper.GetObjectProcess("CSI.ETABS.API.ETABSObject", pid)
    model = etabs.SapModel
    print(f"PID {pid}: {model.GetModelFilename(True)} | đã có kết quả: {model.GetModelIsLocked()}")