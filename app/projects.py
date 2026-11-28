"""Lưu trữ dự án: mỗi dự án là 1 thư mục trong projects/, chứa toàn bộ kết quả.

    projects/
        active.txt                <- tên dự án đang mở
        Nha nhieu tang/
            meta.json             <- tên, model ETABS, ngày tạo, ghi chú
            project.json          <- dữ liệu đọc từ ETABS
            design_beams.json     <- kết quả thiết kế dầm
            design_columns.json   <- kết quả thiết kế cột
            quantities.json       <- khối lượng
            PeRC_KhoiLuong.xlsx
            drawings/*.dxf, *.svg

Các script tính toán đọc/ghi file theo đường dẫn tương đối, nên chỉ cần chạy chúng với
thư mục làm việc = thư mục dự án là kết quả tự lưu vào đúng dự án. Mở lại dự án = đọc lại các file này,
không phải chạy lại ETABS hay thiết kế.
"""
import json
import os
import re
import shutil
import time

import sys

if getattr(sys, "frozen", False):        # bản PeRC.exe: dự án lưu cạnh file exe
    ROOT = os.path.dirname(sys.executable)
else:                                    # chạy từ mã nguồn: thư mục D:\RCDesign
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "projects")
USERS = os.path.join(BASE, "users")      # mỗi tài khoản 1 thư mục: projects/users/<email>/
_user = ""                               # email đang đăng nhập (server.py gán mỗi lần có yêu cầu)


def set_user(email):
    """Chọn kho dự án của tài khoản đang đăng nhập. Người khác không thấy dự án của nhau."""
    global _user
    _user = _safe((email or "").lower())


def home():
    """Thư mục chứa các dự án của tài khoản hiện tại."""
    h = os.path.join(USERS, _user or "_khach")
    if not os.path.isdir(h):
        os.makedirs(h)
        _claim_legacy(h)
    return h


def _active_file():
    return os.path.join(home(), "active.txt")


def _claim_legacy(h):
    """Dự án tạo trước khi tách theo tài khoản (nằm thẳng trong projects/) thuộc về
    tài khoản đăng nhập đầu tiên sau khi cập nhật -> chuyển vào thư mục của tài khoản đó."""
    if not os.path.isdir(BASE):
        return
    for n in os.listdir(BASE):
        src = os.path.join(BASE, n)
        if n == "users" or not os.path.isdir(src):
            continue
        shutil.move(src, os.path.join(h, n))
    old = os.path.join(BASE, "active.txt")
    if os.path.exists(old):
        shutil.move(old, os.path.join(h, "active.txt"))
    if os.listdir(h):                                      # đã nhận dự án cũ -> không chép kết quả cũ cho ai nữa
        open(os.path.join(BASE, ".root_migrated"), "w").close()
RESULT_FILES = ("project.json", "design_beams.json", "design_columns.json", "quantities.json",
                "PeRC_KhoiLuong.xlsx")


def _safe(name):
    """Tên thư mục hợp lệ trên Windows."""
    name = re.sub(r'[<>:"/\\|?*]', " ", name or "").strip().rstrip(".")
    return re.sub(r"\s+", " ", name)[:60]


def folder(name):
    return os.path.join(home(), name)


def _now():
    return time.strftime("%Y-%m-%d %H:%M")


def read_meta(name):
    p = os.path.join(folder(name), "meta.json")
    meta = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    meta.setdefault("name", name)
    return meta


def write_meta(project, **changes):
    meta = read_meta(project)
    meta.update(changes)
    meta["updated"] = _now()
    json.dump(meta, open(os.path.join(folder(project), "meta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return meta


def create(name, note=""):
    name = _safe(name)
    if not name:
        raise ValueError("Tên dự án không hợp lệ.")
    if os.path.exists(folder(name)):
        raise ValueError(f"Đã có dự án '{name}'.")
    os.makedirs(os.path.join(folder(name), "drawings"))
    write_meta(name, name=name, created=_now(), note=note)
    set_active(name)
    return name


def set_active(name):
    if not os.path.isdir(folder(name)):
        raise ValueError(f"Không có dự án '{name}'.")
    open(_active_file(), "w", encoding="utf-8").write(name)


def active():
    """Tên dự án đang mở. Lần đầu chạy: chuyển kết quả cũ ở thư mục gốc vào 1 dự án."""
    act = _active_file()
    if os.path.exists(act):
        name = open(act, encoding="utf-8").read().strip()
        if name and os.path.isdir(folder(name)):
            return name
    existing = list_names()
    if existing:
        set_active(existing[0])
        return existing[0]
    if not os.path.exists(os.path.join(BASE, ".root_migrated")) and os.path.exists(os.path.join(ROOT, "project.json")):
        return migrate_root()                              # máy cũ: kết quả chạy trước đây -> dự án đầu tiên
    return None                                            # tài khoản mới: chưa có dự án nào


def migrate_root():
    """Chép các kết quả đã chạy trước đây (ở D:\\RCDesign) sang dự án đầu tiên. Chép chứ không xoá bản gốc."""
    name, model = "Du an 1", ""
    src = os.path.join(ROOT, "project.json")
    open(os.path.join(BASE, ".root_migrated"), "w").close()   # chỉ chép 1 lần, cho tài khoản đầu tiên
    if os.path.exists(src):
        try:
            model = json.load(open(src, encoding="utf-8")).get("model_file", "")
            name = _safe(os.path.splitext(os.path.basename(model.replace("\\", "/")))[0]) or name
        except Exception:
            pass
    os.makedirs(os.path.join(folder(name), "drawings"), exist_ok=True)
    for f in RESULT_FILES:
        if os.path.exists(os.path.join(ROOT, f)):
            shutil.copy2(os.path.join(ROOT, f), folder(name))
    d = os.path.join(ROOT, "drawings")
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.lower().endswith((".dxf", ".svg")):
                shutil.copy2(os.path.join(d, f), os.path.join(folder(name), "drawings"))
    write_meta(name, name=name, model=model, created=_now(), note="Chuyển từ kết quả chạy trước đây")
    set_active(name)
    return name


def list_names():
    h = home()
    return sorted((n for n in os.listdir(h) if os.path.isdir(folder(n))),
                  key=lambda n: -os.path.getmtime(folder(n)))


def summary(name):
    """Thông tin hiển thị ở danh sách dự án (đọc nhanh, không mở các file JSON lớn)."""
    f = folder(name)
    has = {k: os.path.exists(os.path.join(f, k)) for k in RESULT_FILES}
    d = os.path.join(f, "drawings")
    n_dxf = len([x for x in os.listdir(d) if x.lower().endswith(".dxf")]) if os.path.isdir(d) else 0
    size = sum(os.path.getsize(os.path.join(dp, x)) for dp, _, fs in os.walk(f) for x in fs)
    meta = read_meta(name)
    return {"name": name, "model": meta.get("model", ""), "created": meta.get("created", ""),
            "updated": meta.get("updated", ""), "note": meta.get("note", ""),
            "steps": {"etabs": has["project.json"], "beams": has["design_beams.json"],
                      "columns": has["design_columns.json"], "quantity": has["quantities.json"],
                      "drawings": n_dxf},
            "size_mb": round(size / 1e6, 1)}


def rename(old, new):
    new = _safe(new)
    if not new:
        raise ValueError("Tên dự án không hợp lệ.")
    if os.path.exists(folder(new)):
        raise ValueError(f"Đã có dự án '{new}'.")
    was_active = active() == old
    os.rename(folder(old), folder(new))
    write_meta(new, name=new)
    if was_active:
        set_active(new)
    return new


def duplicate(name):
    """Nhân bản dự án (ví dụ để thử phương án khác mà giữ nguyên kết quả cũ)."""
    i = 2
    while os.path.exists(folder(f"{name} ({i})")):
        i += 1
    new = f"{name} ({i})"
    shutil.copytree(folder(name), folder(new))
    write_meta(new, name=new, created=_now(), note=f"Nhân bản từ {name}")
    return new


def delete(name):
    shutil.rmtree(folder(name))
    act = _active_file()
    if os.path.exists(act) and open(act, encoding="utf-8").read().strip() == name:
        rest = list_names()
        if rest:
            set_active(rest[0])
        else:
            os.remove(act)                                 # xoá hết -> không còn dự án nào đang mở
