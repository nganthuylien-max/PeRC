"""Khởi động PeRC: chạy máy chủ Flask cục bộ rồi mở cửa sổ ứng dụng (pywebview).
   python run_app.py
Không có pywebview thì mở bằng trình duyệt mặc định."""
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
