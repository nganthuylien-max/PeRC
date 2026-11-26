"""PeRC – máy chủ cục bộ (Flask) cho giao diện.

Kiến trúc:
    Giao diện (HTML/JS trong cửa sổ pywebview)  --HTTP-->  Flask (file này)
        - Đọc kết quả: đọc các file JSON (project, design_beams, design_columns, quantities)
        - Chạy tác vụ dài (đọc ETABS, thiết kế, xuất bản vẽ, bóc khối lượng): chạy script tương ứng
          trong một tiến trình con, đọc từng dòng in ra để hiện nhật ký và tiến độ trên giao diện.
          Mỗi tác vụ là 1 tiến trình riêng nên COM của ETABS không xung đột với luồng của Flask.
        - Bản vẽ 1 cấu kiện: dựng ngay trong Flask và trả về SVG để xem trước.
"""
import json
import os
import subprocess
import sys
import threading
import time

from flask import Flask, Response, abort, jsonify, request, send_from_directory

from app import projects as P
from app.auth import SESSION, TASK_COST

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # thư mục D:\RCDesign
sys.path.insert(0, ROOT)

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "static"), static_url_path="")

FILES = {
    "project": "project.json",
    "beams": "design_beams.json",
    "columns": "design_columns.json",
    "quantities": "quantities.json",
    "excel": "PeRC_KhoiLuong.xlsx",
}

# Tác vụ -> (script, mô tả). Thứ tự = quy trình làm việc.
TASKS = {
    "combos": ("list_combos.py", "Đọc danh sách tổ hợp từ ETABS"),
    "etabs": ("export_json.py", "Đọc model và nội lực từ ETABS"),
    "beams": ("design_beams.py", "Thiết kế dầm"),
    "columns": ("design_columns.py", "Thiết kế cột"),
    "drawings": ("draw_sections.py", "Xuất bản vẽ DXF theo tầng"),
    "quantity": ("quantity_takeoff.py", "Bóc tách khối lượng"),
}
NEEDS = {"beams": ["project"], "columns": ["project"], "drawings": ["project", "beams", "columns"],
         "quantity": ["project", "beams", "columns"]}


def pdir():
    """Thư mục của dự án đang mở – mọi kết quả đọc/ghi ở đây."""
    return P.folder(P.active())


def path(key):
    return os.path.join(pdir(), FILES[key])


# ------------------------------------------------------------------ đọc JSON có bộ nhớ đệm theo thời gian sửa file
_cache = {}


def load(key):
    p = path(key)
    if not os.path.exists(p):
        return None
    stamp = (p, os.path.getmtime(p))                 # đổi dự án hoặc file được ghi lại -> đọc lại
    hit = _cache.get(key)
    if hit and hit[0] == stamp:
        return hit[1]
    data = json.load(open(p, encoding="utf-8"))
    _cache[key] = (stamp, data)
    return data


def file_info(key):
    p = path(key)
    if not os.path.exists(p):
        return None
    return time.strftime("%d/%m %H:%M", time.localtime(os.path.getmtime(p)))


# ------------------------------------------------------------------ chạy tác vụ dài trong tiến trình con
class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.task = None
        self.state = "idle"            # idle | running | done | error
        self.log = []
        self.started = 0.0
        self.ended = 0.0
        self.proc = None
        self.project = None

    def start(self, task, args):
        with self.lock:
            if self.state == "running":
                return False
            script, _ = TASKS[task]
            self.project = P.active()
            self.task, self.state, self.log = task, "running", []
            self.started, self.ended = time.time(), 0.0
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
            self.proc = subprocess.Popen(
                [sys.executable, "-u", os.path.join(ROOT, script), *args], cwd=P.folder(self.project), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._pump, daemon=True).start()
        return True

    def _pump(self):
        for line in self.proc.stdout:
            line = line.rstrip()
            if line:
                self.log.append(line)
        code = self.proc.wait()
        if code == 0 and self.task == "etabs":            # ghi tên model ETABS vào thông tin dự án
            try:
                pj = json.load(open(os.path.join(P.folder(self.project), "project.json"), encoding="utf-8"))
                P.write_meta(self.project, model=pj.get("model_file", ""))
            except Exception:
                pass
        elif code == 0:
            P.write_meta(self.project)                    # cập nhật thời gian sửa
        self.state = "done" if code == 0 else "error"
        self.ended = time.time()

    def snapshot(self, since=0):
        end = self.ended or time.time()
        return {"task": self.task, "label": TASKS[self.task][1] if self.task else "",
                "state": self.state, "elapsed": round(end - self.started, 1) if self.started else 0,
                "log": self.log[since:], "n": len(self.log)}


JOB = Job()


# ------------------------------------------------------------------ trang chính
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ------------------------------------------------------------------ trạng thái chung
@app.get("/api/summary")
def summary():
    p = load("project")
    out = {"files": {k: file_info(k) for k in FILES}, "project": None, "beams": None, "columns": None,
           "active": P.active()}
    if p:
        out["project"] = {
            "model": os.path.basename(p.get("model_file", "")),
            "stories": len(p["stories"]), "beams": len(p["beams"]), "columns": len(p["columns"]),
            "slabs": len(p["slabs"]), "walls": len(p["walls"]), "combos": len(p.get("combos", [])),
        }
    b, c = load("beams"), load("columns")
    if b:
        out["beams"] = {"total": len(b), "ok": sum(1 for r in b if r["ok"]),
                        "ng_fit": sum(1 for r in b if not r["layout"])}
    if c:
        out["columns"] = {"total": len(c), "ok": sum(1 for r in c if r["ok"])}
    return jsonify(out)


@app.get("/api/stories")
def stories():
    p = load("project")
    return jsonify([s["name"] for s in reversed(p["stories"])] if p else [])


@app.get("/api/etabs")
def etabs_instances():
    """Danh sách ETABS đang mở (chỉ chạy được trên Windows)."""
    try:
        from etabs_link.connect import list_etabs
        items = [{"pid": pid, "title": title, "visible": "ETABS" in title} for pid, title in list_etabs()]
        return jsonify({"ok": True, "items": items})
    except Exception as e:                       # máy không phải Windows / chưa cài comtypes
        return jsonify({"ok": False, "error": str(e), "items": []})


# ------------------------------------------------------------------ bảng kết quả dầm, cột
def _filter(rows, story, only_ng, q):
    q = (q or "").strip().lower()
    for r in rows:
        if story and r["story"] != story:
            continue
        if only_ng and r["ok"]:
            continue
        if q and q not in r["label"].lower() and q not in r["section"].lower():
            continue
        yield r


@app.get("/api/beams")
def beams():
    from core.beam_design import bars_text
    data = load("beams") or []
    a = request.args
    out = []
    for r in _filter(data, a.get("story"), a.get("ng") == "1", a.get("q")):
        lay = r["layout"]
        row = {"id": r["id"], "label": r["label"], "story": r["story"], "section": r["section"],
               "L": round(r["L"] / 1000, 2), "util": r["util"], "ok": r["ok"], "warnings": r.get("warnings", [])}
        if lay:
            row["top"] = [bars_text(lay, "top", z) for z in "LMR"]
            row["bot"] = [bars_text(lay, "bot", z) for z in "LMR"]
            s = lay["stirrup"]
            row["stirrup"] = f"Ø{s['d']}a{s['s_end']}/{s['s_mid']} ({s['legs']} nhánh)"
        out.append(row)
    return jsonify(out[:2000])


@app.get("/api/columns")
def columns():
    data = load("columns") or []
    a = request.args
    out = []
    for r in _filter(data, a.get("story"), a.get("ng") == "1", a.get("q")):
        lay = r["layout"]
        n = 2 * (lay["nb"] + lay["nh"]) - 4
        w = r.get("worst") or {}
        out.append({"id": r["id"], "label": r["label"], "story": r["story"], "section": r["section"],
                    "bars": f"{n}Ø{lay['d']}", "tie": f"Ø{lay['tie']['d']}a{lay['tie']['s_end']}/{lay['tie']['s_mid']}",
                    "mu": round(r["mu"] * 100, 2), "util": r["util"], "ok": r["ok"],
                    "combo": w.get("combo", ""), "N": round(w.get("N", 0)),
                    "warnings": r.get("warnings", [])})
    return jsonify(out[:2000])


# ------------------------------------------------------------------ bản vẽ 1 cấu kiện (SVG xem trước)
_supports = {}


def supports():
    p = load("project")
    key = _cache["project"][0]                        # (đường dẫn, thời gian sửa) của project.json
    if _supports.get("key") != key:
        from core.beam_detailing import find_supports
        _supports.update(key=key, data=find_supports(p))
    return _supports["data"]


@app.get("/api/svg/beam/<bid>")
def beam_svg(bid):
    from core.beam_detailing import detail_beam
    from drawing.export import to_svg
    from drawing.sections import beam_sheet
    r = next((x for x in load("beams") or [] if x["id"] == bid), None)
    if not r or not r["layout"]:
        abort(404)
    sec = load("project")["frame_sections"][r["section"]]
    det = detail_beam(r, sec, supports()[r["id"]])
    return Response(to_svg(beam_sheet(r, sec, 10, det=det)), mimetype="image/svg+xml")


@app.get("/api/svg/column/<cid>")
def column_svg(cid):
    from drawing.export import to_svg
    from drawing.sections import column_sheet
    r = next((x for x in load("columns") or [] if x["id"] == cid), None)
    if not r:
        abort(404)
    sec = load("project")["frame_sections"][r["section"]]
    return Response(to_svg(column_sheet(r, sec, 10)), mimetype="image/svg+xml")


@app.get("/api/column_labels")
def column_labels():
    labels = {r["label"] for r in load("columns") or []}
    return jsonify(sorted(labels, key=lambda s: (len(s), s)))


@app.get("/api/svg/column_elev/<label>")
def column_elev_svg(label):
    """Mặt cắt dọc cột của 1 tầng (?story=Story5; mặc định tầng dưới cùng)."""
    from drawing.column_elevation import column_stories, column_story_sheets
    from drawing.export import to_svg
    st = request.args.get("story") or (column_stories(load("project"), load("columns") or [], label) or [None])[0]
    try:
        D = column_story_sheets(load("project"), load("columns") or [], label, st, st)
    except ValueError:
        abort(404)
    return Response(to_svg(D), mimetype="image/svg+xml")


@app.get("/api/column_stories/<label>")
def column_stories_api(label):
    from drawing.column_elevation import column_stories
    return jsonify(list(reversed(column_stories(load("project"), load("columns") or [], label))))


@app.get("/api/drawings")
def drawings():
    d = os.path.join(pdir(), "drawings")
    if not os.path.isdir(d):
        return jsonify([])
    names = sorted(f[:-4] for f in os.listdir(d) if f.endswith(".dxf"))
    return jsonify([{"name": n, "time": time.strftime("%d/%m %H:%M",
                                                      time.localtime(os.path.getmtime(os.path.join(d, n + ".dxf"))))}
                    for n in names])


# ------------------------------------------------------------------ khối lượng
@app.get("/api/quantities")
def quantities():
    rows = load("quantities")
    if not rows:
        return jsonify(None)
    els = ("Cột", "Dầm", "Sàn", "Vách")
    tot = {e: {"concrete": 0.0, "formwork": 0.0, "d≤10": 0.0, "d≤18": 0.0, "d>18": 0.0} for e in els}
    per_story = {}
    for r in rows:
        t = tot[r["element"]]
        t["concrete"] += r["concrete"]
        t["formwork"] += r["formwork"]
        for g, kg in r["steel"].items():
            t[g] += kg
        s = per_story.setdefault(r["story"], {"concrete": 0.0, "steel": 0.0})
        s["concrete"] += r["concrete"]
        s["steel"] += sum(r["steel"].values())
    p = load("project")
    order = [s["name"] for s in reversed(p["stories"])] if p else list(per_story)
    return jsonify({"totals": tot, "stories": [{"story": s, **per_story[s]} for s in order if s in per_story]})


# ------------------------------------------------------------------ tác vụ
@app.post("/api/run/<task>")
def run(task):
    if task not in TASKS:
        abort(404)
    missing = [FILES[k] for k in NEEDS.get(task, []) if not os.path.exists(path(k))]
    if missing:
        return jsonify({"ok": False, "error": "Chưa có " + ", ".join(missing) + ". Làm bước trước đó trước."})
    args = []
    body = request.get_json(silent=True) or {}
    if task == "drawings" and body.get("column"):        # mặt cắt dọc cột: 1 tầng hoặc mỗi tầng 1 file
        args = ["cot", body["column"]] + ([body["story"]] if body.get("story") else [])
    elif task == "drawings":
        story = body.get("story")
        if not story:
            return jsonify({"ok": False, "error": "Chọn tầng cần xuất bản vẽ."})
        args = [story]
    if JOB.state == "running":
        return jsonify({"ok": False, "error": "Đang chạy một tác vụ khác, đợi xong đã."})
    note = ""
    if SESSION.public()["configured"]:                   # có cấu hình Supabase -> bắt buộc đăng nhập + trừ điểm
        if not SESSION.public()["logged_in"]:
            return jsonify({"ok": False, "error": "Chưa đăng nhập."})
        allowed, note = SESSION.consume(task)
        if not allowed:
            return jsonify({"ok": False, "error": note})
    if not JOB.start(task, args):
        return jsonify({"ok": False, "error": "Đang chạy một tác vụ khác, đợi xong đã."})
    return jsonify({"ok": True, "note": note, "cost": TASK_COST.get(task, 0)})


@app.get("/api/job")
def job():
    return jsonify(JOB.snapshot(int(request.args.get("since", 0))))


@app.post("/api/open")
def open_file():
    """Mở file kết quả bằng phần mềm mặc định của Windows (Excel, AutoCAD...)."""
    name = (request.get_json(silent=True) or {}).get("name", "")
    ok_name = name == FILES["excel"] or (name.startswith("drawings/") and name.endswith(".dxf")
                                          and ".." not in name and "\\" not in name)
    if not ok_name:                              # chỉ cho mở file kết quả của PeRC
        abort(400)
    full = os.path.join(pdir(), name)
    if not os.path.exists(full):
        return jsonify({"ok": False, "error": "Chưa có file " + name})
    if hasattr(os, "startfile"):
        os.startfile(full)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Chỉ mở được file trên Windows."})


# ------------------------------------------------------------------ lưu trữ dự án
@app.get("/api/projects")
def projects_list():
    return jsonify({"active": P.active(), "items": [P.summary(n) for n in P.list_names()]})


@app.post("/api/projects/<action>")
def projects_action(action):
    if JOB.state == "running":
        return jsonify({"ok": False, "error": "Đang chạy tác vụ, đợi xong rồi mới đổi dự án."})
    b = request.get_json(silent=True) or {}
    try:
        if action == "new":
            name = P.create(b.get("name", ""), b.get("note", ""))
        elif action == "open":
            P.set_active(b["name"])
            name = b["name"]
        elif action == "rename":
            name = P.rename(b["name"], b.get("new", ""))
        elif action == "duplicate":
            name = P.duplicate(b["name"])
        elif action == "note":
            P.write_meta(b["name"], note=b.get("note", ""))
            name = b["name"]
        elif action == "delete":
            P.delete(b["name"])
            name = P.active()
        else:
            abort(404)
    except (ValueError, KeyError, OSError) as e:
        return jsonify({"ok": False, "error": str(e)})
    _cache.clear()
    return jsonify({"ok": True, "name": name})


# ------------------------------------------------------------------ chọn tổ hợp tải trọng
@app.get("/api/combos")
def combos_get():
    """Danh sách tổ hợp đã đọc từ ETABS + lựa chọn hiện tại (chưa chọn -> mặc định)."""
    pa = os.path.join(pdir(), "combos_available.json")
    ps = os.path.join(pdir(), "combos_selected.json")
    if not os.path.exists(pa):
        return jsonify({"available": [], "selected": [], "saved": False})
    av = json.load(open(pa, encoding="utf-8"))
    if os.path.exists(ps):
        sel, saved = json.load(open(ps, encoding="utf-8")), True
    else:
        sel, saved = [c["name"] for c in av["combos"] if c["default"]], False
    return jsonify({"available": av["combos"], "model": av.get("model", ""), "selected": sel, "saved": saved})


@app.post("/api/combos")
def combos_set():
    sel = (request.get_json(silent=True) or {}).get("selected", [])
    json.dump(sel, open(os.path.join(pdir(), "combos_selected.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return jsonify({"ok": True, "n": len(sel)})


@app.get("/api/tienluong")
def tienluong():
    """Bảng tiên lượng kiểu Eta: ?story=Story5 (không có = toàn công trình)."""
    from quantity.report import work_items
    rows = load("quantities")
    if not rows:
        return jsonify(None)
    p = load("project")
    order = {s["name"]: i for i, s in enumerate(p["stories"])} if p else {}
    st = request.args.get("story") or None
    if rows and "details" not in rows[0] and st:
        return jsonify({"items": work_items(rows, None, order), "old": True})
    return jsonify({"items": work_items(rows, st, order), "old": False})


# ------------------------------------------------------------------ tài khoản (đăng nhập Google qua Supabase)
@app.get("/api/auth/status")
def auth_status():
    if request.args.get("refresh") == "1" or SESSION.status is None:
        if SESSION.public()["configured"] and not SESSION.pending:
            SESSION.refresh_status()
    return jsonify(SESSION.public())


@app.post("/api/auth/login")
def auth_login():
    if not SESSION.public()["configured"]:
        return jsonify({"ok": False, "error": "Chưa cấu hình Supabase (app/auth.py)."})
    SESSION.start_login()
    return jsonify({"ok": True})


@app.post("/api/auth/logout")
def auth_logout():
    SESSION.logout()
    return jsonify({"ok": True})


@app.post("/api/auth/delete")
def auth_delete():
    """Xoá tài khoản + toàn bộ dữ liệu sử dụng trên máy chủ (dữ liệu dự án trên máy vẫn giữ)."""
    try:
        r = SESSION.rpc("delete_my_data")
    except Exception as e:                                  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})
    SESSION.logout()
    return jsonify({"ok": bool(r and r.get("ok"))})


def _admin(fn, params=None):
    try:
        return jsonify({"ok": True, "data": SESSION.rpc(fn, params)})
    except Exception as e:                                  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.get("/api/admin/users")
def admin_users():
    return _admin("admin_list_users")


@app.post("/api/admin/set")
def admin_set():
    b = request.get_json(silent=True) or {}
    return _admin("admin_set_user", {"uid": b["id"], "quota": int(b["quota"]), "is_banned": bool(b["banned"])})


@app.post("/api/admin/delete")
def admin_delete():
    b = request.get_json(silent=True) or {}
    return _admin("admin_delete_user", {"uid": b["id"]})
