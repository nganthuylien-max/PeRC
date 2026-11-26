// PeRC – giao diện. Gọi API của server.py bằng fetch, không dùng thư viện ngoài.
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const api = (url, body) => fetch(url, body === undefined ? {} : {
  method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)}).then(r => r.json());
const fmt = (x, d = 1) => Number(x).toLocaleString("vi-VN", {minimumFractionDigits: d, maximumFractionDigits: d});
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));

function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg; t.className = "on" + (err ? " err" : "");
  clearTimeout(t._h); t._h = setTimeout(() => t.className = "", 3500);
}

// ---------------------------------------------------------------- điều hướng
$$("nav button").forEach(b => b.onclick = () => show(b.dataset.page));
function show(page) {
  $$("nav button").forEach(b => b.classList.toggle("active", b.dataset.page === page));
  $$(".page").forEach(p => p.classList.toggle("active", p.id === "page-" + page));
  ({account: loadAccount, admin: loadAdmin, projects: loadProjects, etabs: loadEtabs, beams: loadBeams, columns: loadColumns, drawings: loadDrawings, quantity: loadQty})[page]();
}

// ---------------------------------------------------------------- trạng thái chung
let SUMMARY = null;
async function loadSummary() {
  SUMMARY = await api("/api/summary");
  const f = SUMMARY.files;
  for (const k of ["project", "beams", "columns", "quantities"]) $("#dot-" + k).classList.toggle("on", !!f[k]);
  const p = SUMMARY.project;
  $("#model-name").textContent = p ? p.model + " · đọc lúc " + f.project : "Chưa có dữ liệu ETABS";
  $("#nav-project").textContent = SUMMARY.active;
  const stories = await api("/api/stories");
  $$(".story-select").forEach(sel => {
    const keep = sel.value, all = sel.id !== "draw-story";
    sel.innerHTML = (all ? '<option value="">Tất cả tầng</option>' : "") +
      stories.map(s => `<option>${s}</option>`).join("");
    if (keep && stories.includes(keep)) sel.value = keep;
  });
}

const stat = (v, label, cls = "") => `<div class="stat ${cls}"><b>${v}</b><span>${label}</span></div>`;

// ---------------------------------------------------------------- 0. Dự án
async function loadProjects() {
  const r = await api("/api/projects");
  const pill = (ok, t) => `<span class="${ok ? "ok" : ""}">${ok ? "✓ " : ""}${t}</span>`;
  $("#project-list").innerHTML = r.items.map(p => `<div class="proj ${p.name === r.active ? "on" : ""}" data-name="${esc(p.name)}">
    <h3><span class="nm">${esc(p.name)}</span>${p.name === r.active ? '<span class="badge">ĐANG MỞ</span>' : ""}</h3>
    <div class="meta">${p.model ? "Model: " + esc(p.model) + "<br>" : ""}Tạo: ${p.created || "–"} · Sửa: ${p.updated || "–"} · ${p.size_mb} MB</div>
    <div class="steps">${pill(p.steps.etabs, "ETABS")}${pill(p.steps.beams, "Dầm")}${pill(p.steps.columns, "Cột")}
      ${pill(p.steps.drawings > 0, p.steps.drawings + " bản vẽ")}${pill(p.steps.quantity, "Khối lượng")}</div>
    <textarea class="note" placeholder="Ghi chú (phương án, người làm, ngày nộp…)">${esc(p.note || "")}</textarea>
    <div class="acts">
      ${p.name === r.active ? "" : '<button class="primary" data-act="open">Mở</button>'}
      <button class="ghost" data-act="rename">Đổi tên</button>
      <button class="ghost" data-act="duplicate">Nhân bản</button>
      <button class="ghost del" data-act="delete">Xoá</button>
    </div></div>`).join("");
}
async function projectAct(action, body, msg) {
  const r = await api("/api/projects/" + action, body);
  if (!r.ok) return toast(r.error, true);
  if (msg) toast(msg(r));
  await loadSummary();
  loadProjects();
}
$("#btn-new").onclick = () => {
  const name = $("#new-name").value.trim();
  if (!name) return toast("Nhập tên dự án.", true);
  $("#new-name").value = "";
  projectAct("new", {name}, r => `Đã tạo và mở dự án "${r.name}". Sang bước 1 để đọc ETABS.`);
};
$("#project-list").addEventListener("click", e => {
  const b = e.target.closest("[data-act]"); if (!b) return;
  const card = b.closest(".proj"), name = card.dataset.name;
  const act = b.dataset.act;
  if (act === "open") projectAct("open", {name}, () => `Đã mở dự án "${name}"`);
  if (act === "duplicate") projectAct("duplicate", {name}, r => `Đã nhân bản thành "${r.name}"`);
  if (act === "delete") {
    if (b.dataset.sure) projectAct("delete", {name}, () => `Đã xoá dự án "${name}"`);
    else { b.dataset.sure = 1; b.textContent = "Bấm lần nữa để xoá hẳn"; setTimeout(() => { delete b.dataset.sure; b.textContent = "Xoá"; }, 4000); }
  }
  if (act === "rename") {
    const h = $("h3", card), old = name;
    h.innerHTML = `<input class="rn" value="${esc(old)}"><button class="primary" data-act="rename-ok">Lưu</button>`;
    $("input", h).focus();
  }
  if (act === "rename-ok") projectAct("rename", {name, new: $("input.rn", card).value}, r => `Đã đổi tên thành "${r.name}"`);
});
$("#project-list").addEventListener("change", e => {
  if (!e.target.classList.contains("note")) return;
  api("/api/projects/note", {name: e.target.closest(".proj").dataset.name, note: e.target.value}).then(() => toast("Đã lưu ghi chú"));
});

// ---------------------------------------------------------------- 1. ETABS
async function loadEtabs() {
  loadCombos();
  const p = SUMMARY && SUMMARY.project;
  $("#project-stats").innerHTML = p ? [
    stat(p.stories, "tầng"), stat(p.beams.toLocaleString("vi-VN"), "dầm"), stat(p.columns, "cột"),
    stat(p.slabs.toLocaleString("vi-VN"), "ô sàn"), stat(p.walls, "vách"), stat(p.combos, "tổ hợp tải trọng"),
  ].join("") : '<div class="card muted">Chưa đọc dữ liệu từ ETABS.</div>';
  $("#etabs-list").textContent = "Đang kiểm tra…";
  const r = await api("/api/etabs");
  if (!r.ok) { $("#etabs-list").textContent = "Không kiểm tra được: " + r.error; return; }
  $("#etabs-list").innerHTML = r.items.length
    ? r.items.map(e => `<div>${e.visible ? "🟢" : "⚪"} PID ${e.pid} – ${esc(e.visible ? e.title : "chạy ngầm, không có cửa sổ")}</div>`).join("")
    : '<span class="muted">Chưa mở ETABS.</span>';
}
$("#btn-etabs-refresh").onclick = loadEtabs;

let COMBOS = null;
async function loadCombos() {
  COMBOS = await api("/api/combos");
  const sel = new Set(COMBOS.selected);
  $("#combo-list").innerHTML = COMBOS.available.length ? COMBOS.available.map(c => `<label class="${c.default ? "" : "off"}">
      <input type="checkbox" value="${esc(c.name)}" ${sel.has(c.name) ? "checked" : ""}>${esc(c.name)}
      <small>${esc(c.type)}${c.auto ? " · tự sinh" : ""}</small></label>`).join("")
    : '<span class="muted">Chưa đọc danh sách tổ hợp. Mở ETABS rồi bấm "Đọc danh sách tổ hợp".</span>';
  countCombos();
}
function countCombos() {
  const n = $$("#combo-list input:checked").length;
  $("#cb-count").textContent = COMBOS && COMBOS.available.length
    ? `Đã chọn ${n}/${COMBOS.available.length} tổ hợp` + (COMBOS.saved ? "" : " (mặc định, chưa lưu)") : "";
}
async function saveCombos() {
  const selected = $$("#combo-list input:checked").map(x => x.value);
  await api("/api/combos", {selected});
  COMBOS.saved = true;
  countCombos();
}
$("#combo-list").addEventListener("change", saveCombos);
$("#cb-all").onclick = () => { $$("#combo-list input").forEach(x => x.checked = true); saveCombos(); };
$("#cb-none").onclick = () => { $$("#combo-list input").forEach(x => x.checked = false); saveCombos(); };
$("#cb-default").onclick = () => {
  const def = new Set(COMBOS.available.filter(c => c.default).map(c => c.name));
  $$("#combo-list input").forEach(x => x.checked = def.has(x.value)); saveCombos();
};

// ---------------------------------------------------------------- bảng dầm, cột
function utilCell(u, ok) {
  if (u === null || u === undefined) return '<span class="tag">Không xếp đủ thép</span>';
  const w = Math.min(u, 1) * 100;
  return `<div class="util ${ok ? "" : "ng"}"><div class="bar"><i style="width:${w}%"></i></div><b>${fmt(u, 2)}</b></div>`;
}
function bindTable(table, rows, onPick) {
  const tb = $("tbody", table);
  tb.onclick = e => {
    const tr = e.target.closest("tr"); if (!tr) return;
    $$("tr.sel", tb).forEach(x => x.classList.remove("sel")); tr.classList.add("sel");
    onPick(rows[tr.dataset.i]);
  };
}
const debounce = (fn, ms = 250) => { let h; return () => { clearTimeout(h); h = setTimeout(fn, ms); }; };

async function loadBeams() {
  const b = SUMMARY && SUMMARY.beams;
  $("#beam-stats").innerHTML = b ? [stat(b.total.toLocaleString("vi-VN"), "dầm đã thiết kế"),
    stat(b.ok.toLocaleString("vi-VN"), "đạt", "ok"), stat(b.total - b.ok - b.ng_fit, "vượt khả năng chịu lực", "ng"),
    stat(b.ng_fit, "không xếp đủ thép", "ng")].join("") : "";
  const q = new URLSearchParams({story: $("#beam-story").value, q: $("#beam-q").value, ng: $("#beam-ng").checked ? 1 : 0});
  const rows = await api("/api/beams?" + q);
  $("#beam-count").textContent = rows.length + " dầm";
  $("#beam-table tbody").innerHTML = rows.map((r, i) => `<tr data-i="${i}">
    <td>${r.story}</td><td><b>${esc(r.label)}</b></td><td>${esc(r.section)}</td><td>${fmt(r.L, 2)}</td>
    <td class="bars">${r.top ? r.top.map(t => `<span>${t}</span>`).join("") : "–"}</td>
    <td class="bars">${r.bot ? r.bot.map(t => `<span>${t}</span>`).join("") : "–"}</td>
    <td>${r.stirrup || "–"}</td><td>${utilCell(r.util, r.ok)}</td></tr>`).join("");
  bindTable($("#beam-table"), rows, r => preview("#beam-preview", "beam", r, [
    ["Tiết diện", r.section], ["Nhịp L", fmt(r.L, 2) + " m"],
    ["Thép trên", r.top ? r.top.join(" · ") : "–"], ["Thép dưới", r.bot ? r.bot.join(" · ") : "–"],
    ["Cốt đai", r.stirrup || "–"], ["Hệ số sử dụng", r.util == null ? "–" : fmt(r.util, 2)]]));
}
["#beam-story", "#beam-ng"].forEach(s => $(s).onchange = loadBeams);
$("#beam-q").oninput = debounce(loadBeams);

async function loadColumns() {
  const c = SUMMARY && SUMMARY.columns;
  $("#col-stats").innerHTML = c ? [stat(c.total, "cột đã thiết kế"), stat(c.ok, "đạt", "ok"),
    stat(c.total - c.ok, "không đạt", "ng")].join("") : "";
  const q = new URLSearchParams({story: $("#col-story").value, q: $("#col-q").value, ng: $("#col-ng").checked ? 1 : 0});
  const rows = await api("/api/columns?" + q);
  $("#col-count").textContent = rows.length + " cột";
  $("#col-table tbody").innerHTML = rows.map((r, i) => `<tr data-i="${i}">
    <td>${r.story}</td><td><b>${esc(r.label)}</b></td><td>${esc(r.section)}</td><td>${r.bars}</td><td>${r.tie}</td>
    <td>${fmt(r.mu, 2)}</td><td>${esc(r.combo)} <span class="muted">N=${r.N.toLocaleString("vi-VN")} kN</span></td>
    <td>${utilCell(r.util, r.ok)}</td></tr>`).join("");
  bindTable($("#col-table"), rows, r => preview("#col-preview", "column", r, [
    ["Tiết diện", r.section], ["Thép dọc", r.bars + ` (μ = ${fmt(r.mu, 2)}%)`], ["Cốt đai", r.tie],
    ["Tổ hợp bất lợi", `${r.combo}, N = ${r.N.toLocaleString("vi-VN")} kN`], ["Hệ số sử dụng", fmt(r.util, 2)]]));
}
["#col-story", "#col-ng"].forEach(s => $(s).onchange = loadColumns);
$("#col-q").oninput = debounce(loadColumns);

function openModal(src) {
  $("#modal-img").innerHTML = `<img src="${src}">`; $("#modal").classList.add("on");
}
function preview(box, kind, r, facts) {
  const el = $(box);
  const can = kind === "column" || r.top;
  // cột: bản vẽ đầy đủ của tầng (mặt cắt dọc + 3 mặt cắt ngang); dầm: mặt cắt dọc + 3 mặt cắt ngang
  const src = kind === "column" ? `/api/svg/column_elev/${encodeURIComponent(r.label)}?story=${r.story}`
                                : `/api/svg/beam/${r.id}`;
  el.innerHTML = `<h3>${kind === "beam" ? "Dầm" : "Cột"} ${esc(r.label)} – ${r.story}</h3>
    <dl>${facts.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
    ${(r.warnings || []).map(w => `<div class="warn">⚠ ${esc(w)}</div>`).join("")}
    ${can ? `<img src="${src}" alt="Bản vẽ" title="Bấm để phóng to">
             <div class="muted" style="font-size:12px">Bấm vào bản vẽ để phóng to</div>`
          : '<div class="muted">Không có bản vẽ vì không xếp đủ thép trong 2 lớp.</div>'}`;
  const img = $("img", el);
  if (img) img.onclick = () => openModal(img.src);
}
$("#modal-close").onclick = () => $("#modal").classList.remove("on");
$("#modal").onclick = e => { if (e.target.id === "modal") $("#modal").classList.remove("on"); };

// ---------------------------------------------------------------- 4. Bản vẽ
async function loadDrawings() {
  const labels = await api("/api/column_labels");
  const sel = $("#draw-col"), keep = sel.value;
  sel.innerHTML = labels.map(l => `<option>${l}</option>`).join("");
  if (keep && labels.includes(keep)) sel.value = keep;
  await loadColStories();
  const list = await api("/api/drawings");
  $("#draw-list").innerHTML = list.length ? list.map(d => `<div class="file"><b>${esc(d.name)}.dxf</b>
    <span class="muted grow">${d.time}</span>
    <button class="ghost" data-open="drawings/${esc(d.name)}.dxf">Mở bằng AutoCAD</button></div>`).join("")
    : '<span class="muted">Chưa xuất bản vẽ nào.</span>';
  $("#dot-drawings").classList.toggle("on", list.length > 0);
}
$("#btn-draw").onclick = () => runTask("drawings", {story: $("#draw-story").value});
async function loadColStories() {
  const col = $("#draw-col").value; if (!col) return;
  const st = await api("/api/column_stories/" + encodeURIComponent(col));
  const s = $("#draw-col-story"), keep = s.value;
  s.innerHTML = '<option value="">Tất cả tầng (mỗi tầng 1 file)</option>' + st.map(x => `<option>${x}</option>`).join("");
  s.value = keep && st.includes(keep) ? keep : (st[st.length - 1] || "");
}
$("#draw-col").onchange = loadColStories;
$("#btn-col-draw").onclick = () => runTask("drawings", {column: $("#draw-col").value, story: $("#draw-col-story").value});
$("#btn-col-view").onclick = () => {
  const st = $("#draw-col-story").value;
  if (!st) return toast("Chọn 1 tầng để xem. \"Tất cả tầng\" chỉ dùng khi xuất DXF.", true);
  openModal(`/api/svg/column_elev/${encodeURIComponent($("#draw-col").value)}?story=${st}`);
};
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-open]"); if (!b) return;
  const r = await api("/api/open", {name: b.dataset.open});
  if (!r.ok) toast(r.error, true);
});

// ---------------------------------------------------------------- 5. Khối lượng
async function loadTienLuong() {
  const sel = $("#tl-story");
  if (!sel.options.length) {
    const st = await api("/api/stories");
    sel.innerHTML = '<option value="">Toàn công trình</option>' + st.map(s => `<option>${s}</option>`).join("");
  }
  const r = await api("/api/tienluong?story=" + encodeURIComponent(sel.value));
  const T = $("#tl-table");
  if (!r) { T.innerHTML = '<tr><td class="muted">Chưa bóc khối lượng.</td></tr>'; return; }
  const dec = u => u === "tấn" ? 3 : 2;
  T.innerHTML = `<thead><tr><th>Ký hiệu</th><th>STT</th><th>Tên công việc / Diễn giải khối lượng</th>
      <th>Đơn vị</th><th>Khối lượng</th></tr></thead><tbody>` +
    r.items.filter(it => it.qty > 1e-9 || !sel.value).map(it => `<tr class="item"><td class="c">PeRC</td><td class="c">${it.stt}</td>
      <td>${esc(it.name)}</td><td class="c">${it.unit}</td><td class="n">${fmt(it.qty, dec(it.unit))}</td></tr>` +
      it.lines.map(([t, v]) => `<tr class="dg"><td></td><td></td><td class="t">${esc(t)}</td><td class="c">${it.unit}</td>
        <td class="n">${fmt(v, dec(it.unit) + 1)}</td></tr>`).join("")).join("") + "</tbody>";
  if (r.old) toast("Kết quả khối lượng cũ chưa có diễn giải theo tầng – bấm \"Bóc khối lượng\" để tính lại.", true);
}
$("#tl-story").onchange = loadTienLuong;
$("#tl-hide").onchange = e => $("#tl-table").classList.toggle("hide", e.target.checked);

async function loadQty() {
  loadTienLuong();
  const q = await api("/api/quantities");
  if (!q) { $("#qty-table").innerHTML = '<tr><td class="muted">Chưa bóc khối lượng.</td></tr>'; $("#qty-chart").innerHTML = ""; return; }
  const els = ["Cột", "Dầm", "Sàn", "Vách"], G = {concrete: 0, formwork: 0, "d≤10": 0, "d≤18": 0, "d>18": 0};
  const line = (name, t, cls = "") => {
    const s = t["d≤10"] + t["d≤18"] + t["d>18"];
    return `<tr class="${cls}"><td>${name}</td><td>${fmt(t.concrete)}</td><td>${fmt(t.formwork)}</td>
      <td>${fmt(t["d≤10"] / 1000, 2)}</td><td>${fmt(t["d≤18"] / 1000, 2)}</td><td>${fmt(t["d>18"] / 1000, 2)}</td>
      <td><b>${fmt(s / 1000, 2)}</b></td><td>${fmt(t.concrete ? s / t.concrete : 0, 0)}</td></tr>`;
  };
  let body = "";
  for (const e of els) { const t = q.totals[e]; for (const k in G) G[k] += t[k]; body += line(e, t); }
  $("#qty-table").innerHTML = `<thead><tr><th>Cấu kiện</th><th>Bê tông (m³)</th><th>Ván khuôn (m²)</th>
    <th>Thép d≤10 (T)</th><th>d≤18 (T)</th><th>d>18 (T)</th><th>Tổng thép (T)</th><th>kg/m³</th></tr></thead>
    <tbody>${body}${line("TỔNG", G, "total")}</tbody>`;
  const mc = Math.max(...q.stories.map(s => s.concrete)), ms = Math.max(...q.stories.map(s => s.steel));
  $("#qty-chart").innerHTML = `<div class="legend"><span></span><span>Bê tông (m³)</span><span>Cốt thép (tấn)</span></div>` +
    q.stories.map(s => `<div class="r"><span>${s.story}</span>
      <div><div class="b" style="width:${s.concrete / mc * 80}%"><em>${fmt(s.concrete, 0)}</em></div></div>
      <div><div class="b s" style="width:${s.steel / ms * 80}%"><em>${fmt(s.steel / 1000, 1)}</em></div></div></div>`).join("");
}
$("#btn-excel").onclick = async () => {
  const r = await api("/api/open", {name: "PeRC_KhoiLuong.xlsx"});
  if (!r.ok) toast(r.error, true);
};

// ---------------------------------------------------------------- chạy tác vụ + theo dõi nhật ký
$$("[data-run]").forEach(b => b.onclick = () => runTask(b.dataset.run));
async function runTask(task, body = {}) {
  const r = await api("/api/run/" + task, body);
  if (!r.ok) return toast(r.error, true);
  if (r.note) toast(r.note);
  loadAuth();
  $("#job-log").textContent = ""; logN = 0;
  $("#job").classList.add("open");
  poll();
}
let logN = 0, polling = false;
async function poll() {
  if (polling) return; polling = true;
  while (true) {
    const j = await api("/api/job?since=" + logN);
    logN = j.n;
    const foot = $("#job");
    foot.className = j.state + (foot.classList.contains("open") ? " open" : "");
    $("#job-label").textContent = j.task ? j.label + ({running: "…", done: " – xong", error: " – lỗi"}[j.state] || "") : "Sẵn sàng";
    $("#job-time").textContent = j.task ? fmt(j.elapsed, 0) + " s" : "";
    if (j.log.length) { const L = $("#job-log"); L.textContent += j.log.join("\n") + "\n"; L.scrollTop = L.scrollHeight; }
    $$("[data-run], #btn-draw, #btn-col-draw").forEach(b => b.disabled = j.state === "running");
    if (j.state !== "running") {
      polling = false;
      if (j.task) {
        toast(j.state === "done" ? j.label + " – hoàn thành" : j.label + " – có lỗi, xem nhật ký", j.state !== "done");
        await loadSummary();
        show($("nav button.active").dataset.page);
      }
      return;
    }
    await new Promise(r => setTimeout(r, 700));
  }
}
$("#job-toggle").onclick = () => $("#job").classList.toggle("open");

// ---------------------------------------------------------------- khởi động
// ---------------------------------------------------------------- đăng nhập, tài khoản, quản trị
const TERMS = `<ol>
<li>PeRC là công cụ hỗ trợ thiết kế theo TCVN 5574:2018. Kết quả phải được kỹ sư có chuyên môn kiểm tra trước khi sử dụng;
  tác giả không chịu trách nhiệm về thiệt hại phát sinh từ việc dùng kết quả chưa được kiểm tra.</li>
<li>Khi đăng nhập bằng Google, PeRC chỉ lưu email, tên hiển thị, thời điểm sử dụng và số điểm đã dùng
  (để tính hạn mức). Model ETABS, kết quả thiết kế và bản vẽ chỉ lưu trên máy của bạn, không gửi lên máy chủ.</li>
<li>Mỗi tài khoản có hạn mức điểm theo ngày. Quản trị viên có thể điều chỉnh hạn mức hoặc khoá tài khoản vi phạm.</li>
<li>Bạn có thể xoá tài khoản và toàn bộ dữ liệu sử dụng trên máy chủ bất cứ lúc nào ở trang Tài khoản.</li>
<li>Dịch vụ miễn phí, có thể thay đổi hoặc ngừng mà không báo trước.</li></ol>`;
$("#terms-text").innerHTML = TERMS;
$("#login-terms").innerHTML = TERMS;
$("#show-terms").onclick = e => { e.preventDefault(); $("#login-terms").hidden = !$("#login-terms").hidden; };

let AUTH = null;
async function loadAuth(refresh = false) {
  AUTH = await api("/api/auth/status" + (refresh ? "?refresh=1" : ""));
  const needLogin = AUTH.configured && !AUTH.logged_in;
  $("#login").hidden = !needLogin;
  if (needLogin) {
    $("#login-msg").textContent = AUTH.pending ? "Đang chờ bạn đăng nhập trên trình duyệt…"
      : (AUTH.error || "Đăng nhập 1 lần, app tự giữ đăng nhập trên máy này.");
    $("#btn-login").disabled = !!AUTH.pending;
  }
  const s = AUTH.status;
  $("#acct").hidden = !AUTH.logged_in;
  $("#nav-admin").hidden = !(s && s.is_admin);
  if (AUTH.logged_in) {
    const left = Math.max(0, s.quota - s.used);
    $("#acct-mail").textContent = s.email;
    $("#credit-bar").style.width = (s.quota ? left / s.quota * 100 : 0) + "%";
    $("#acct-txt").innerHTML = `Còn <b>${left}</b>/${s.quota} điểm hôm nay` +
      (AUTH.offline ? `<br><span class="off">Offline – còn ${Math.floor(AUTH.offline_hours_left)} giờ</span>` : "");
  }
  if (!AUTH.configured) $("#acct").hidden = true;
  return AUTH;
}
$("#btn-login").onclick = async () => {
  if (!$("#agree").checked) return toast("Hãy đồng ý Điều khoản sử dụng trước.", true);
  const r = await api("/api/auth/login", {});
  if (!r.ok) return toast(r.error, true);
  await loadAuth();
  const t = setInterval(async () => {                    // chờ đăng nhập xong trên trình duyệt
    const a = await loadAuth();
    if (!a.pending) { clearInterval(t); if (a.logged_in) { toast("Đăng nhập thành công"); start(); } }
  }, 1500);
};
function loadAccount() {
  if (!AUTH || !AUTH.logged_in) return;
  const s = AUTH.status;
  $("#acct-stats").innerHTML = [stat(esc(s.email), s.name ? esc(s.name) : "email"),
    stat(`${s.quota - s.used}/${s.quota}`, "điểm còn lại hôm nay", "ok"),
    stat(s.is_admin ? "Quản trị" : "Người dùng", "vai trò")].join("");
  const names = {combos: "Đọc danh sách tổ hợp", etabs: "Đọc dữ liệu ETABS", beams: "Thiết kế dầm",
                 columns: "Thiết kế cột", drawings: "Xuất bản vẽ DXF", quantity: "Bóc khối lượng"};
  $("#cost-table").innerHTML = "<tbody>" + Object.entries(AUTH.costs).map(([k, v]) =>
    `<tr><td>${names[k] || k}</td><td>${v} điểm</td></tr>`).join("") + "</tbody>";
}
$("#btn-logout").onclick = async () => { await api("/api/auth/logout", {}); await loadAuth(); };
$("#btn-delete-me").onclick = async e => {
  const b = e.target;
  if (!b.dataset.sure) { b.dataset.sure = 1; b.textContent = "Bấm lần nữa để xoá vĩnh viễn";
    return setTimeout(() => { delete b.dataset.sure; b.textContent = "Xoá tài khoản và dữ liệu của tôi"; }, 4000); }
  const r = await api("/api/auth/delete", {});
  toast(r.ok ? "Đã xoá tài khoản và dữ liệu trên máy chủ" : (r.error || "Không xoá được"), !r.ok);
  await loadAuth();
};
async function loadAdmin() {
  const r = await api("/api/admin/users");
  if (!r.ok) { $("#admin-table").innerHTML = `<tr><td class="muted">${esc(r.error)}</td></tr>`; return; }
  const d = v => v ? new Date(v).toLocaleString("vi-VN") : "–";
  $("#admin-table").innerHTML = `<thead><tr><th>Email</th><th>Tên</th><th>Đăng ký</th><th>Lần cuối</th>
    <th>Hôm nay</th><th>Tổng điểm</th><th>Hạn mức/ngày</th><th>Khoá</th><th></th></tr></thead><tbody>` +
    r.data.map(u => `<tr data-id="${u.id}"><td><b>${esc(u.email || "")}</b>${u.is_admin ? " ★" : ""}</td>
      <td>${esc(u.full_name || "")}</td><td>${d(u.created_at)}</td><td>${d(u.last_seen)}</td>
      <td>${u.used_today}</td><td>${u.used_total}</td>
      <td><input type="number" min="0" step="50" value="${u.daily_quota}"></td>
      <td><input type="checkbox" ${u.banned ? "checked" : ""} ${u.is_admin ? "disabled" : ""}></td>
      <td><button class="link" data-a="save">Lưu</button> ${u.is_admin ? "" : '· <button class="link" data-a="del">Xoá</button>'}</td>
    </tr>`).join("") + "</tbody>";
}
$("#btn-admin-reload").onclick = loadAdmin;
$("#admin-table").addEventListener("click", async e => {
  const b = e.target.closest("[data-a]"); if (!b) return;
  const tr = b.closest("tr"), id = tr.dataset.id;
  if (b.dataset.a === "save") {
    const [q, ban] = $$("input", tr);
    const r = await api("/api/admin/set", {id, quota: q.value, banned: ban.checked});
    toast(r.ok ? "Đã lưu" : r.error, !r.ok);
  } else if (b.dataset.a === "del") {
    if (!b.dataset.sure) { b.dataset.sure = 1; b.textContent = "Chắc chắn?"; return; }
    const r = await api("/api/admin/delete", {id});
    toast(r.ok ? "Đã xoá người dùng" : r.error, !r.ok);
    loadAdmin();
  }
});

async function start() { await loadSummary(); loadProjects(); poll(); }
(async () => {
  const a = await loadAuth(true);
  if (!a.configured || a.logged_in) start();
  setInterval(() => { if (AUTH && AUTH.logged_in) loadAuth(); }, 60000);   // cập nhật điểm mỗi phút
})();
