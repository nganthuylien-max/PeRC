"""Đọc bảng database của ETABS (giống Display > Show Tables)."""


def to_float(value, default=0.0):
    """Chuỗi số của ETABS -> float. Máy Windows tiếng Việt dùng dấu phẩy: '0,0035'."""
    if value is None:
        return default
    s = str(value).strip().replace(" ", "")
    if not s:
        return default
    if "," in s and "." not in s:
        s = s.replace(",", ".")          # 0,0035 -> 0.0035
    try:
        return float(s)
    except ValueError:
        return default


def read_table(model, key, combos=None):
    """Đọc bảng `key`, trả về list các dict {tên cột: giá trị chuỗi}.
    combos: danh sách tổ hợp cần hiển thị (chỉ dùng cho bảng kết quả)."""
    db = model.DatabaseTables
    if combos is not None:
        db.SetLoadCasesSelectedForDisplay([])
        db.SetLoadCombinationsSelectedForDisplay(combos)

    result = list(db.GetTableForDisplayArray(key, [], "", 0, [], 0, []))
    # comtypes trả về các tham số "out" theo thứ tự:
    # [FieldKeyList, TableVersion, FieldsKeysIncluded, NumberRecords, TableData, ret]
    if result[-1] != 0:
        raise RuntimeError(f"Không đọc được bảng '{key}' (mã lỗi {result[-1]})")
    lists = [x for x in result[:-1] if isinstance(x, (list, tuple))]
    fields, data = list(lists[-2]), list(lists[-1])
    n = len(fields)
    # dữ liệu là 1 mảng phẳng: dòng 1 cột 1, dòng 1 cột 2, ..., dòng 2 cột 1, ...
    return [dict(zip(fields, data[i:i + n])) for i in range(0, len(data), n)]