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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS = os.path.join(ROOT, "projects")
ACTIVE = os.path.join(PROJECTS, "active.txt")
RESULT_FILES = ("project.json", "design_beams.json", "design_columns.json", "quantities.json",
                "PeRC_KhoiLuong.xlsx")


def _safe(name):
    """Tên thư mục hợp lệ trên Windows."""
    name = re.sub(r'[<>:"/\\|?*]', " ", name or "").strip().rstrip(".")
    return re.sub(r"\s+", " ", name)[:60]


def folder(name):
    return os.path.join(PROJECTS, name)


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
    open(ACTIVE, "w", encoding="utf-8").write(name)


def active():
    """Tên dự án đang mở. Lần đầu chạy: chuyển kết quả cũ ở thư mục gốc vào 1 dự án."""
    os.makedirs(PROJECTS, exist_ok=True)
    if os.path.exists(ACTIVE):
        name = open(ACTIVE, encoding="utf-8").read().strip()
        if name and os.path.isdir(folder(name)):
            return name
    existing = list_names()
    if existing:
        set_active(existing[0])
        return existing[0]
    return migrate_root()


def migrate_root():
    """Chép các kết quả đã chạy trước đây (ở D:\\RCDesign) sang dự án đầu tiên. Chép chứ không xoá bản gốc."""
    name, model = "Du an 1", ""
    src = os.path.join(ROOT, "project.json")
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
    if not os.path.isdir(PROJECTS):
        return []
    return sorted((n for n in os.listdir(PROJECTS) if os.path.isdir(folder(n))),
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
    if active() == name and len(list_names()) == 1:
        raise ValueError("Không xoá được dự án duy nhất. Tạo dự án khác trước.")
    shutil.rmtree(folder(name))
    if not os.path.exists(ACTIVE) or open(ACTIVE, encoding="utf-8").read().strip() == name:
        set_active(list_names()[0])
