"""Khởi động PeRC: chạy máy chủ Flask cục bộ rồi mở cửa sổ ứng dụng (pywebview).
   python run_app.py
Không có pywebview thì mở bằng trình duyệt mặc định.

Bản đóng gói PeRC.exe không có python.exe đi kèm, nên các tác vụ dài (đọc ETABS, thiết kế...)
chạy bằng chính PeRC.exe với tham số:  PeRC.exe --run <script.py> [đối số]"""
import os
import sys

if len(sys.argv) > 2 and sys.argv[1] == "--run":          # chế độ chạy 1 script tính toán (tiến trình con)
    import runpy
    sys.path.insert(0, getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))))
    script = sys.argv[2]
    sys.argv = [script, *sys.argv[3:]]
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", line_buffering=True)   # in ra từng dòng ngay
        except Exception:
            pass
    runpy.run_path(script, run_name="__main__")
    sys.exit(0)

import socket
import threading
import time

from app.server import app


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))                 # hệ điều hành cấp một cổng đang trống
    port = s.getsockname()[1]
    s.close()
    return port


port = free_port()
url = f"http://127.0.0.1:{port}/"
threading.Thread(target=lambda: app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False),
                 daemon=True).start()
time.sleep(0.8)

try:
    import webview
    webview.create_window("PeRC – Thiết kế cốt thép TCVN 5574:2018", url, width=1440, height=900, min_size=(1100, 700))
    webview.start()                          # đóng cửa sổ là thoát chương trình
except ImportError:
    import webbrowser
    print("Chưa cài pywebview -> mở bằng trình duyệt:", url, "(Ctrl+C để thoát)")
    webbrowser.open(url)
    while True:
        time.sleep(1)
