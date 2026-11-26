"""Đăng nhập Google qua Supabase (luồng PKCE cho ứng dụng desktop), giữ đăng nhập, hạn mức theo ngày.

Luồng đăng nhập:
  1. App tạo code_verifier (ngẫu nhiên) và code_challenge = SHA256(code_verifier).
  2. Mở trình duyệt: Supabase /authorize?provider=google&code_challenge=...&redirect_to=http://127.0.0.1:53682/auth/callback
  3. Người dùng đăng nhập Google -> Supabase chuyển về địa chỉ trên kèm ?code=...
     (một máy chủ nhỏ chạy tạm ở cổng 53682 nhận mã này).
  4. App đổi code + code_verifier lấy access_token (1 giờ) và refresh_token (dài hạn).
  5. refresh_token lưu trong Windows Credential Manager (thư viện keyring) -> lần sau tự đăng nhập.
Offline: nếu không vào được mạng nhưng lần xác minh gần nhất < 3 ngày thì vẫn cho dùng.
Mọi việc trừ điểm, khoá tài khoản... chạy trong hàm SQL trên Supabase (schema.sql), app chỉ gọi.
"""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

# ----------------------------------------------------------------- cấu hình (khoá publishable được phép để công khai)
SUPABASE_URL = os.environ.get("PERC_SUPABASE_URL", "https://bjuiycgwcmosvlzhabgh.supabase.co")
SUPABASE_KEY = os.environ.get("PERC_SUPABASE_KEY", "sb_publishable_XZamTP9910-oBeVcnxm7gg_uh9_GRpM")
CALLBACK_PORT = 53682
REDIRECT = f"http://127.0.0.1:{CALLBACK_PORT}/auth/callback"
OFFLINE_DAYS = 3
SERVICE = "PeRC"                      # tên mục trong Windows Credential Manager

# điểm của từng tác vụ (hạn mức mặc định 500 điểm/ngày)
TASK_COST = {"combos": 5, "etabs": 50, "beams": 20, "columns": 30, "drawings": 10, "quantity": 10}

STATE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PeRC")
STATE_FILE = os.path.join(STATE_DIR, "account.json")      # thông tin hiển thị + thời điểm xác minh (không chứa token)


# ----------------------------------------------------------------- lưu refresh token
def _keyring():
    try:
        import keyring
        return keyring
    except ImportError:
        return None


def save_refresh(token):
    kr = _keyring()
    if kr:
        if token:
            kr.set_password(SERVICE, "refresh_token", token)
        else:
            try:
                kr.delete_password(SERVICE, "refresh_token")
            except Exception:
                pass
    else:                                                  # dự phòng: file trong %APPDATA% (kém an toàn hơn)
        _write_state({**_read_state(), "rt": token})


def load_refresh():
    kr = _keyring()
    if kr:
        return kr.get_password(SERVICE, "refresh_token")
    return _read_state().get("rt")


def _read_state():
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        return {}


def _write_state(d):
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(d, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False)


# ----------------------------------------------------------------- gọi Supabase
class NetError(Exception):
    """Không kết nối được máy chủ (mất mạng)."""


def _http(method, path, body=None, token=None):
    url = SUPABASE_URL.rstrip("/") + path
    headers = {"apikey": SUPABASE_KEY, "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt else None
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode())
        except Exception:
            msg = {"message": str(e)}
        raise RuntimeError(msg.get("msg") or msg.get("message") or msg.get("error_description") or str(msg))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise NetError(str(e))


class Session:
    def __init__(self):
        self.lock = threading.Lock()
        self.access = None
        self.expires = 0
        self.status = None              # kết quả my_status()
        self.offline = False
        self.pending = None             # đang chờ đăng nhập trên trình duyệt
        self.error = None

    # ------------------------------------------------------------- token
    def _set_tokens(self, tok):
        self.access = tok["access_token"]
        self.expires = time.time() + tok.get("expires_in", 3600) - 60
        save_refresh(tok["refresh_token"])

    def _ensure_access(self):
        if self.access and time.time() < self.expires:
            return self.access
        rt = load_refresh()
        if not rt:
            return None
        try:
            tok = _http("POST", "/auth/v1/token?grant_type=refresh_token", {"refresh_token": rt})
        except RuntimeError:                       # refresh token hết hạn / bị thu hồi -> đăng nhập lại
            save_refresh(None)
            return None
        self._set_tokens(tok)
        return self.access

    def rpc(self, name, params=None):
        tok = self._ensure_access()
        if not tok:
            raise RuntimeError("Chưa đăng nhập")
        return _http("POST", f"/rest/v1/rpc/{name}", params or {}, tok)

    # ------------------------------------------------------------- trạng thái
    def refresh_status(self):
        """Hỏi máy chủ trạng thái tài khoản. Mất mạng: dùng bản lưu nếu xác minh < 3 ngày."""
        with self.lock:
            st = _read_state()
            try:
                s = self.rpc("my_status")
                self.status, self.offline = s, False
                _write_state({**st, "status": s, "verified": time.time()})
            except NetError:
                if st.get("status") and time.time() - st.get("verified", 0) < OFFLINE_DAYS * 86400 and load_refresh():
                    self.status, self.offline = st["status"], True
                else:
                    self.status, self.offline = None, False
            except RuntimeError:
                self.status = None
            return self.public()

    def public(self):
        st = _read_state()
        left = None
        if self.offline:
            left = max(0, OFFLINE_DAYS * 86400 - (time.time() - st.get("verified", 0))) / 3600
        return {"logged_in": bool(self.status and self.status.get("ok")), "status": self.status,
                "offline": self.offline, "offline_hours_left": left, "pending": bool(self.pending),
                "error": self.error, "configured": "YOUR-PROJECT" not in SUPABASE_URL, "costs": TASK_COST}

    # ------------------------------------------------------------- đăng nhập
    def start_login(self):
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        self.pending, self.error = verifier, None
        q = urllib.parse.urlencode({"provider": "google", "redirect_to": REDIRECT,
                                    "code_challenge": challenge, "code_challenge_method": "s256"})
        threading.Thread(target=self._wait_callback, daemon=True).start()
        webbrowser.open(f"{SUPABASE_URL.rstrip('/')}/auth/v1/authorize?{q}")

    def _wait_callback(self):
        sess = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                code = (qs.get("code") or [None])[0]
                err = (qs.get("error_description") or qs.get("error") or [None])[0]
                ok = False
                if code:
                    try:
                        tok = _http("POST", "/auth/v1/token?grant_type=pkce",
                                    {"auth_code": code, "code_verifier": sess.pending})
                        sess._set_tokens(tok)
                        ok = True
                    except Exception as e:                     # noqa: BLE001
                        err = str(e)
                sess.error = None if ok else (err or "Đăng nhập không thành công")
                msg = ("<h2>Đăng nhập thành công</h2><p>Quay lại cửa sổ PeRC để tiếp tục.</p>" if ok
                       else f"<h2>Đăng nhập không thành công</h2><p>{sess.error}</p>")
                body = ("<html><head><meta charset='utf-8'><title>PeRC</title></head>"
                        "<body style='font-family:Segoe UI,Arial;text-align:center;margin-top:80px'>"
                        f"{msg}</body></html>").encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
                sess.pending = None
                threading.Thread(target=self.server.shutdown, daemon=True).start()

            def log_message(self, *a):
                pass

        try:
            srv = HTTPServer(("127.0.0.1", CALLBACK_PORT), H)
            srv.timeout = 300
            srv.serve_forever()
        except OSError as e:
            self.error, self.pending = f"Cổng {CALLBACK_PORT} đang bận: {e}", None
        if self.error is None and self.pending is None:
            self.refresh_status()

    def logout(self):
        save_refresh(None)
        self.access, self.status, self.offline = None, None, False
        _write_state({})

    # ------------------------------------------------------------- hạn mức
    def consume(self, task):
        """Trừ điểm trước khi chạy tác vụ. Trả về (được phép, thông báo)."""
        cost = TASK_COST.get(task, 0)
        if self.offline:
            return True, "Đang dùng offline – điểm sẽ không bị trừ"
        try:
            r = self.rpc("consume", {"task": task, "cost": cost})
        except NetError:
            st = _read_state()
            if time.time() - st.get("verified", 0) < OFFLINE_DAYS * 86400:
                self.offline = True
                return True, "Mất mạng – dùng chế độ offline"
            return False, "Không kết nối được máy chủ và đã quá 3 ngày offline. Kết nối mạng để tiếp tục."
        except RuntimeError as e:
            return False, str(e)
        if r.get("ok") and self.status:
            self.status["used"] = r["used"]
        return bool(r.get("ok")), r.get("error", "")


SESSION = Session()
