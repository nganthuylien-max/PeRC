"""Thiết kế 1 dầm: uốn 3 vùng × 2 thớ + cắt + cấu tạo."""
from .beam_flexure import required_As, capacity, MU_MIN
from .beam_shear import choose_stirrups, shear_check
from .beam_layout import choose_face, place_face, ZONES

ZONE_NAME = {"L": "Gối trái", "M": "Giữa nhịp", "R": "Gối phải"}


def design_beam(beam, sec, conc, steel, steel_w, cover=25):
    b, h, L, env = sec["b"], sec["h"], beam["L"], beam["env"]
    ds = 8
    a = {"top": cover + ds + 10, "bot": cover + ds + 10}          # giả định ban đầu
    factor = {(z, f): 1.0 for z in ZONES for f in ("top", "bot")}

    for _ in range(6):                                            # lặp tới khi đạt
        # 1. As yêu cầu từng vùng, từng thớ
        reqs = {"top": {}, "bot": {}}
        for z in ZONES:
            rt = required_As(env[z]["Mtop"], b, h, a["top"], a["bot"], conc, steel)
            rb = required_As(env[z]["Mbot"], b, h, a["bot"], a["top"], conc, steel)
            Amin = MU_MIN * b * (h - a["bot"])
            reqs["top"][z] = max(rt["As"], rb["As_c"], Amin if env[z]["Mtop"] > 0 else 0) * factor[(z, "top")]
            reqs["bot"][z] = max(rb["As"], rt["As_c"], Amin if env[z]["Mbot"] > 0 else 0) * factor[(z, "bot")]

        # 2. Chọn thép
        top = choose_face(b, cover, ds, L, reqs["top"], "top")
        bot = choose_face(b, cover, ds, L, reqs["bot"], "bot")
        faces = {z: {"top": place_face(b, cover, ds, top["cont"], top["add"][z], "top"),
                     "bot": place_face(b, cover, ds, bot["cont"], bot["add"][z], "bot")} for z in ZONES}

        # 3. Cốt đai, với h0 nhỏ nhất thực tế
        h0 = min(h - faces[z][f]["a"] for z in ZONES for f in ("top", "bot"))
        d_main = max(t["d"] for z in ZONES for f in ("top", "bot") for t in faces[z][f]["bars"])
        stir = choose_stirrups(max(env["L"]["V"], env["R"]["V"]), env["M"]["V"],
                               b, h, h0, conc, steel_w, d_main)

        # 4. Kiểm tra lại với thép thật
        checks, again = {}, False
        for z in ZONES:
            checks[z] = {}
            for f, other, key in (("top", "bot", "Mtop"), ("bot", "top", "Mbot")):
                ft, fc = faces[z][f], faces[z][other]
                k = capacity(b, h, ft["As"], ft["a"], fc["As"], fc["a"], conc, steel)
                M = env[z][key]
                util = M / k["Mu"] if k["Mu"] > 0 else 0
                checks[z][f] = {"M": M, "combo": env[z][key + "_combo"], "As": ft["As"],
                                "a": ft["a"], "Mu": k["Mu"], "util": util, "mu": k["mu"],
                                "x": k["x"], "layers": ft["layers"], "fits": ft["fits"]}
                if util > 1:
                    factor[(z, f)] *= util * 1.02          # thiếu -> tăng As yêu cầu, chọn lại
                    again = True
            s = stir["s_mid"] if z == "M" else stir["s_end"]
            checks[z]["shear"] = shear_check(env[z]["V"], b, h0, conc, steel_w, stir["d"], stir["legs"], s)
            checks[z]["shear"]["s"] = s
        ds = stir["d"]
        a = {f: max(faces[z][f]["a"] for z in ZONES) for f in ("top", "bot")}
        if not again:
            break

    # 5. Tổng hợp
    warnings = []
    for z in ZONES:
        for f in ("top", "bot"):
            c = checks[z][f]
            if c["M"] > 0 and c["mu"] < MU_MIN:
                warnings.append(f"{ZONE_NAME[z]} {f}: μ < 0.1%")
            if c["mu"] > 0.03:
                warnings.append(f"{ZONE_NAME[z]} {f}: μ = {c['mu']*100:.1f}% > 3%")
            if not c["fits"]:
                warnings.append(f"{ZONE_NAME[z]} {f}: vượt 2 lớp thép")
    util = max(max(checks[z]["top"]["util"], checks[z]["bot"]["util"], checks[z]["shear"]["util"])
               for z in ZONES)
    if util > 1.0:
        warnings.append(f"Hệ số sử dụng {util:.2f} > 1: tiết diện {b:.0f}×{h:.0f} không đủ – "
                        "tăng tiết diện dầm")
    ok = util <= 1.0 and stir["ok"] and not any("vượt" in w for w in warnings)
    layout = {"top": {"cont": list(top["cont"]), "add": {z: list(v) for z, v in top["add"].items()}},
              "bot": {"cont": list(bot["cont"]), "add": {z: list(v) for z, v in bot["add"].items()}},
              "stirrup": stir}
    return {"layout": layout, "checks": checks, "util": util, "ok": ok, "warnings": warnings}


def bars_text(layout, face, z):
    """'2Ø20 + 3Ø22' cho 1 thớ, 1 vùng."""
    n, d = layout[face]["cont"]
    na, da = layout[face]["add"][z]
    return f"{n}Ø{d}" + (f" + {na}Ø{da}" if na else "")
