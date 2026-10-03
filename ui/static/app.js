// app.js —— 整合包工作台前端逻辑（原生 JS，零依赖）
// 2B 骨架（导航/工作区/错误映射）+ 2C（环境状态/快捷目录/文件浏览/目录创建）

"use strict";

const $ = (sel) => document.querySelector(sel);

// ---------- 错误映射（UI 错误处理第 10 条） ----------
function errorToUser(raw) {
  const text = String(raw ?? "未知错误");
  if (/EPERM|EACCES|access denied|权限/i.test(text)) {
    return "无法完成文件操作。文件可能正在被其他程序或安全软件占用。";
  }
  if (/EBUSY|locked|being used/i.test(text)) {
    return "文件正在被其他程序使用，请关闭占用程序后重试。";
  }
  if (/ENOENT|no such file|不存在|not found/i.test(text)) {
    return "找不到指定的文件或目录，请检查路径。";
  }
  if (/FS_STALE|changed since it was read/i.test(text)) {
    return "文件内容已被其他程序修改，请刷新后重试。";
  }
  if (/UnicodeDecode|encoding|FS_NOT_TEXT|乱码/i.test(text)) {
    return "文件编码无法识别（可能是非 UTF-8 文件），请勿直接改写该文件。";
  }
  if (/数据契约错误|Missing required/i.test(text)) {
    return "输入文件缺少必要字段，请检查所选文件。";
  }
  if (/timeout|超时/i.test(text)) {
    return "操作超时，请重试。";
  }
  return "操作未完成，请重试。";
}

function toast(message, kind = "info", ms = 4000) {
  const el = $("#toast");
  el.textContent = message;
  el.dataset.kind = kind;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, ms);
}

// ---------- 极简 Markdown 渲染（零依赖；先整体转义再套格式，防 XSS） ----------
function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function mdInline(s) {
  return s
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}
function renderMarkdown(text) {
  const lines = escapeHtml(text).split("\n");
  const out = [];
  let inCode = false;
  let inTable = false;
  for (const line of lines) {
    if (line.startsWith("```")) {
      if (inCode) { out.push("</pre>"); inCode = false; }
      else { out.push("<pre>"); inCode = true; }
      continue;
    }
    if (inCode) { out.push(line); continue; }
    if (/^\|.*\|$/.test(line.trim())) {
      if (/^\|[\s:|-]+\|$/.test(line.trim())) continue; // 分隔行
      const cells = line.trim().slice(1, -1).split("|").map((c) => c.trim());
      if (!inTable) { out.push("<table>"); inTable = true; }
      out.push(`<tr>${cells.map((c) => `<td>${mdInline(c)}</td>`).join("")}</tr>`);
      continue;
    }
    if (inTable) { out.push("</table>"); inTable = false; }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) { out.push(`<h${h[1].length + 1}>${mdInline(h[2])}</h${h[1].length + 1}>`); continue; }
    if (/^[-*]\s+/.test(line)) { out.push(`<li>${mdInline(line.replace(/^[-*]\s+/, ""))}</li>`); continue; }
    if (/^\d+\.\s+/.test(line)) { out.push(`<li>${mdInline(line.replace(/^\d+\.\s+/, ""))}</li>`); continue; }
    if (line.trim() !== "") out.push(`<p>${mdInline(line)}</p>`);
  }
  if (inTable) out.push("</table>");
  if (inCode) out.push("</pre>");
  return out.join("\n");
}

async function api(path, options = {}) {
  const r = await fetch(path, options);
  let j = null;
  try { j = await r.json(); } catch { /* 非 JSON */ }
  if (!r.ok) {
    const detail = (j && (j.hint || j.detail || j.error)) || `HTTP ${r.status}`;
    const err = new Error(detail);
    err.status = r.status;
    err.payload = j;
    throw err;
  }
  return j;
}

// ---------- 导航 ----------
const QUICK_DIRS = [
  { rel: "", name: "工作区", note: "项目根目录" },
  { rel: "integration-pack/reports", name: "reports", note: "招标日报与输出结果" },
  { rel: "integration-pack/templates", name: "templates", note: "Excel 模板" },
  { rel: "integration-pack/data", name: "data", note: "载流量/工艺参数/图例库" },
  { rel: "integration-pack/config", name: "config", note: "招标关键词与来源清单" },
  { rel: "integration-pack/docs", name: "docs", note: "契约与审计文档" },
  { rel: "integration-pack/skills", name: "skills", note: "技能说明" },
  { rel: "integration-pack/plugins", name: "plugins", note: "插件审查报告" },
  { rel: "integration-pack/scripts", name: "scripts", note: "工具脚本" },
];

function initNav() {
  const items = document.querySelectorAll(".nav-item");
  items.forEach((item) => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      items.forEach((x) => x.classList.remove("active"));
      item.classList.add("active");
      document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
      const page = document.getElementById("page-" + item.dataset.page);
      if (page) page.classList.add("active");
      history.replaceState(null, "", "#" + item.dataset.page);
      // 首次进入文件页时触发目录加载（修复"加载中"卡住）
      if (item.dataset.page === "files" && !window._filesLoaded) {
        window._filesLoaded = true;
        loadFiles("");
      }
    });
  });
  const initial = (location.hash || "#workbench").slice(1);
  const target = document.querySelector(`.nav-item[data-page="${initial}"]`) || $(".nav-item");
  target.click();
}

// ---------- 环境状态 ----------
function statusChip(label, kind) {
  const span = document.createElement("span");
  span.className = "status-chip";
  span.dataset.status = kind;
  const dot = document.createElement("span");
  dot.className = "dot";
  span.appendChild(dot);
  span.appendChild(document.createTextNode(label));
  return span;
}

async function loadEnv() {
  const box = $("#env-status");
  box.innerHTML = "";
  box.appendChild(statusChip("环境检查中……", "loading"));
  try {
    const j = await api("/api/env");
    box.innerHTML = "";
    const { python, pydeps, cad, skills, tender_reports } = j;
    box.appendChild(statusChip(python.ok ? `Python ${python.version}` : "Python 未检测到",
      python.ok ? "ok" : "error"));
    box.appendChild(statusChip(pydeps.ok ? "依赖库正常" : "依赖库缺失（运行“整体自检”可重建）",
      pydeps.ok ? "ok" : "warn"));
    const cadLabel = cad.dwg_to_dxf === "autocad" ? "CAD：AutoCAD 可用"
      : cad.dwg_to_dxf === "oda" ? "CAD：ODA 转换可用"
      : cad.dwg_to_dxf === "none" ? "CAD：未检测到（可看环境检查说明）" : "CAD：状态未知";
    box.appendChild(statusChip(cadLabel, cad.has_autocad || cad.has_oda ? "ok" : "warn"));
    box.appendChild(statusChip(`技能 ${skills} 个 · 招标日报 ${tender_reports} 份`, "ok"));
  } catch (e) {
    box.innerHTML = "";
    box.appendChild(statusChip("环境信息读取失败", "error"));
    console.error("[ui] env failed:", e);
  }
}

// ---------- 快捷目录 ----------
function dirItem(rel, name, note) {
  const div = document.createElement("div");
  div.className = "dir-item";
  const info = document.createElement("div");
  const nm = document.createElement("div");
  nm.className = "dir-name";
  nm.textContent = name;
  const nt = document.createElement("div");
  nt.className = "dir-note";
  nt.textContent = note;
  info.appendChild(nm);
  info.appendChild(nt);
  const actions = document.createElement("div");
  actions.className = "dir-actions";
  const browse = document.createElement("button");
  browse.className = "btn btn-sm";
  browse.textContent = "浏览";
  browse.addEventListener("click", () => openFilesPage(rel));
  const open = document.createElement("button");
  open.className = "btn btn-sm";
  open.textContent = "资源管理器";
  open.addEventListener("click", async () => {
    try {
      await api("/api/explorer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: rel }),
      });
    } catch (e) {
      toast(errorToUser(e.message), "error");
    }
  });
  actions.appendChild(browse);
  actions.appendChild(open);
  div.appendChild(info);
  div.appendChild(actions);
  return div;
}

function loadQuickDirs() {
  const box = $("#quick-dirs");
  box.innerHTML = "";
  QUICK_DIRS.forEach((d) => box.appendChild(dirItem(d.rel, d.name, d.note)));
}

// ---------- 文件浏览 ----------
const FILES_STATE = { rel: "", path: [] };

function openFilesPage(rel) {
  document.querySelector('.nav-item[data-page="files"]').click();
  loadFiles(rel || "");
}

async function loadFiles(rel) {
  const box = $("#file-browser");
  box.innerHTML = '<span class="hint">加载中……</span>';
  FILES_STATE.rel = rel || "";
  try {
    const j = await api("/api/dirs?path=" + encodeURIComponent(rel || ""));
    renderFiles(j);
  } catch (e) {
    box.innerHTML = "";
    if (e.status === 404) {
      box.appendChild(missingDirBox(rel));
      return;
    }
    box.appendChild(errorBox(errorToUser(e.message)));
  }
}

function missingDirBox(rel) {
  const div = document.createElement("div");
  div.className = "error-box";
  div.textContent = "该目录不存在。";
  const btn = document.createElement("button");
  btn.className = "btn btn-sm";
  btn.style.marginLeft = "8px";
  btn.textContent = "创建目录";
  btn.addEventListener("click", async () => {
    try {
      await api("/api/mkdir", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: rel }),
      });
      toast("目录已创建", "success");
      loadFiles(rel);
    } catch (err) {
      toast(errorToUser(err.message), "error");
    }
  });
  div.appendChild(btn);
  return div;
}

function errorBox(msg) {
  const div = document.createElement("div");
  div.className = "error-box";
  div.textContent = msg;
  return div;
}

function renderFiles(j) {
  const box = $("#file-browser");
  box.innerHTML = "";
  // 面包屑
  const crumbs = document.createElement("div");
  crumbs.className = "crumbs";
  const segs = (j.rel || "").split("/").filter(Boolean);
  const rootBtn = document.createElement("a");
  rootBtn.href = "#";
  rootBtn.textContent = "工作区";
  rootBtn.addEventListener("click", (e) => { e.preventDefault(); loadFiles(""); });
  crumbs.appendChild(rootBtn);
  let acc = "";
  segs.forEach((s) => {
    acc = acc ? acc + "/" + s : s;
    crumbs.appendChild(document.createTextNode(" / "));
    const a = document.createElement("a");
    a.href = "#";
    a.textContent = s;
    a.addEventListener("click", (e) => { e.preventDefault(); loadFiles(acc); });
    crumbs.appendChild(a);
  });
  box.appendChild(crumbs);

  // 上级
  if (j.rel) {
    const up = document.createElement("div");
    up.className = "dir-item";
    up.style.marginTop = "10px";
    const upBtn = document.createElement("button");
    upBtn.className = "btn btn-sm";
    upBtn.textContent = "↑ 上级目录";
    upBtn.addEventListener("click", () => {
      const parts = (j.rel || "").split("/").filter(Boolean);
      parts.pop();
      loadFiles(parts.join("/"));
    });
    up.appendChild(upBtn);
    box.appendChild(up);
  }

  // 条目
  const list = document.createElement("div");
  list.className = "file-list";
  (j.entries || []).forEach((entry) => {
    const row = document.createElement("div");
    row.className = "file-row";
    const icon = document.createElement("span");
    icon.className = "file-icon";
    icon.textContent = entry.type === "dir" ? "▸" : "·";
    const name = document.createElement("span");
    name.className = "file-name";
    name.textContent = entry.name;
    name.title = entry.rel;
    row.appendChild(icon);
    row.appendChild(name);
    if (entry.type === "file" && entry.size !== null) {
      const size = document.createElement("span");
      size.className = "file-size";
      size.textContent = entry.size > 1024 ? (entry.size / 1024).toFixed(1) + " KB" : entry.size + " B";
      row.appendChild(size);
    }
    const open = document.createElement("button");
    open.className = "btn btn-sm";
    open.textContent = "资源管理器";
    open.addEventListener("click", async () => {
      try {
        await api("/api/explorer", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: entry.rel }),
        });
      } catch (e) { toast(errorToUser(e.message), "error"); }
    });
    row.appendChild(open);
    row.addEventListener("click", (e) => {
      if (e.target === open) return;
      if (entry.type === "dir") loadFiles(entry.rel);
      else if (PICK_TARGET) {
        // 文件选择模式：回填路径并回到工具页
        const input = document.getElementById(PICK_TARGET);
        if (input) input.value = entry.rel;
        PICK_TARGET = null;
        document.querySelector('.nav-item[data-page="tools"]').click();
      } else {
        previewFile(entry.rel);
      }
    });
    list.appendChild(row);
  });
  box.appendChild(list);
  if (!(j.entries || []).length) {
    const empty = document.createElement("div");
    empty.className = "hint";
    empty.style.marginTop = "12px";
    empty.textContent = "（空目录）";
    box.appendChild(empty);
  }
  // 预览区
  const preview = document.createElement("div");
  preview.id = "file-preview";
  box.appendChild(preview);
}

async function previewFile(rel) {
  const area = $("#file-preview");
  if (!area) return;
  area.innerHTML = '<span class="hint">加载中……</span>';
  try {
    const j = await api("/api/file?path=" + encodeURIComponent(rel));
    renderPreviewInto(area, j);
  } catch (e) {
    area.innerHTML = "";
    area.appendChild(errorBox(errorToUser(e.message)));
  }
}

/** 统一的预览渲染：md 走 Markdown 渲染，table/text 走文本块，不可预览给原因。 */
function renderPreviewInto(area, j) {
  area.innerHTML = "";
  if (j.previewable) {
    if (j.kind === "md") {
      const box = document.createElement("div");
      box.className = "md-body";
      box.innerHTML = renderMarkdown(j.content);
      area.appendChild(box);
    } else {
      const box = document.createElement("div");
      box.className = "result-box";
      box.textContent = j.content;
      area.appendChild(box);
    }
  } else {
    const box = document.createElement("div");
    box.className = "error-box";
    box.textContent = j.reason || "无法预览该文件。";
    area.appendChild(box);
  }
}

// ---------- 工具运行（配置驱动，Phase 4 全量接入） ----------
let PICK_TARGET = null;   // 文件选择模式：点击文件后回填的输入框 id
let RUNNING = false;

const TOOL_FORMS = [
  {
    id: "normalize", title: "招标清单规整", runTool: "normalize",
    desc: "把招标清单（xlsx / csv）规整为标准设备表：序号、设备名称、规格型号、材质、单位、数量。",
    fields: [
      { id: "input", label: "输入文件", kind: "file",
        placeholder: "integration-pack/reports/smoke/招标清单.xlsx" },
    ],
  },
  {
    id: "compare", title: "供应商报价比对", runTool: "compare",
    desc: "多份供应商报价横向比对（同参数归组，标注异常高低价）。需 2~8 个报价文件。",
    fields: [
      { id: "inputs", label: "报价文件（2~8 个，逗号分隔）", kind: "files",
        placeholder: "报价A.xlsx, 报价B.xlsx" },
    ],
  },
  {
    id: "cost", title: "成本测算", runTool: "cost",
    desc: "对含单价的清单做含税测算（运费/安装/管理/利润参数化）。同设备多行默认拒绝（防重复计价）。",
    fields: [
      { id: "input", label: "输入文件（含单价列）", kind: "file",
        placeholder: "integration-pack/reports/smoke/报价A.xlsx" },
      { id: "tax", label: "税率 %", kind: "number", default: 13 },
      { id: "freight", label: "运费（元）", kind: "number", default: 0 },
      { id: "install", label: "安装费 %", kind: "number", default: 0 },
      { id: "admin", label: "管理费 %", kind: "number", default: 5 },
      { id: "profit", label: "利润 %", kind: "number", default: 8 },
      { id: "allow_duplicates", label: "允许同设备多行", kind: "flag", default: false },
    ],
  },
  {
    id: "diff", title: "清单差异核对", runTool: "diff",
    desc: "投标清单与报价清单一致性核对：漏项、多出、数量差异。",
    fields: [
      { id: "tender", label: "投标清单", kind: "file",
        placeholder: "integration-pack/reports/smoke/招标清单.xlsx" },
      { id: "quote", label: "报价清单", kind: "file",
        placeholder: "integration-pack/reports/smoke/报价A.xlsx" },
    ],
  },
  {
    id: "dxf_parse", title: "图纸清单提取", runTool: "dxf_parse",
    desc: "从 DXF 图纸提取设备位号与仪表位号，输出带置信度的清单初稿（⚠ 项需人工复核）。",
    fields: [
      { id: "dxf", label: "DXF 图纸", kind: "file",
        placeholder: "integration-pack/reports/smoke/测试PID.dxf" },
    ],
  },
  {
    id: "cad_env", title: "CAD 环境检查", runTool: "cad_env", noInput: true,
    desc: "检测本机 AutoCAD / ODA File Converter 与 DWG 转换能力。",
  },
  {
    id: "smoke_test", title: "整体自检", runTool: "smoke_test", noInput: true,
    desc: "运行整合包冒烟测试（cad_env / dxf_parse / quote_tools 全链路），确认环境与工具链正常。",
  },
  {
    id: "bootstrap", title: "重建依赖库", runTool: "bootstrap", noInput: true,
    desc: "从镜像重建 Python 依赖库（首次部署或依赖损坏时使用，约 1~2 分钟）。",
  },
];

const DIALOG_FEATURES = [
  { name: "PLC 程序开发辅助", desc: "电机启停/液位联锁/PID 等控制逻辑；信捷、汇川、台达、西门子、三菱代码与地址映射",
    example: "给 1# 提升泵写电机启停程序（本地/远程/自动三模式），信捷 XC 系列" },
  { name: "水处理工艺计算", desc: "曝气需氧量、加药量、污泥产量、水力计算，输出含公式与取值依据的计算书",
    example: "算曝气需氧量：水量 1 万吨/天，进出水 BOD 250/20 mg/L，氨氮 30/5 mg/L" },
  { name: "电气设计计算", desc: "电缆载流量与压降、短路简算、断路器/热继整定",
    example: "校核 YJV 4×25 电缆带 90kW 电机、120 米，压降是否合格" },
  { name: "规范标准查询", desc: "GB/HG/CJ 条文定位、现行版本核验、官方来源链接",
    example: "查 GB 50014-2021 关于泵站集水池有效容积的条文" },
  { name: "招标与价格查询", desc: "公开源检索、多源交叉验证、带来源链接的询价汇总（每日 08:30 自动监控招标）",
    example: "查一下 DN200 电磁流量计的参考价格" },
  { name: "报价清单深度处理", desc: "复杂清单的人工审核、异常项分析与调整建议（对话式）",
    example: "帮我看这份报价表里有没有异常低价项" },
  { name: "故障诊断", desc: "工具错误的五步法诊断：观察→假设→验证→行动→复核",
    example: "这个文件一直打不开，帮我诊断一下" },
];

function initTools() {
  document.querySelectorAll("[data-goto]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelector(`.nav-item[data-page="${btn.dataset.goto}"]`).click();
      if (btn.dataset.tool) {
        setTimeout(() => {
          const card = document.getElementById("tool-" + btn.dataset.tool);
          if (card) card.scrollIntoView({ block: "start" });
        }, 50);
      }
    });
  });
  const box = $("#tool-list");
  box.innerHTML = "";
  TOOL_FORMS.forEach(renderToolForm);
  renderDialogFeatures();
}

function renderDialogFeatures() {
  const page = document.getElementById("page-tools");
  const h = document.createElement("h2");
  h.className = "section-title";
  h.style.marginTop = "28px";
  h.textContent = "对话功能（在 DSH 对话中使用）";
  page.appendChild(h);
  const hint = document.createElement("p");
  hint.className = "hint";
  hint.textContent = "以下功能由 DSH 对话技能提供：在对话框直接提问即可，无需在本页面操作。点“复制示例”后回到对话粘贴。";
  page.appendChild(hint);
  const list = document.createElement("div");
  list.className = "file-list";
  DIALOG_FEATURES.forEach((f) => {
    const row = document.createElement("div");
    row.className = "file-row";
    row.style.cursor = "default";
    const main = document.createElement("div");
    main.style.flex = "1";
    main.style.minWidth = "0";
    const nm = document.createElement("div");
    nm.className = "dialog-name";
    nm.textContent = f.name;
    const ds = document.createElement("div");
    ds.className = "hint";
    ds.textContent = f.desc;
    const ex = document.createElement("div");
    ex.className = "dialog-example";
    ex.textContent = "示例：" + f.example;
    main.appendChild(nm);
    main.appendChild(ds);
    main.appendChild(ex);
    row.appendChild(main);
    if (f.example) {
      const copy = document.createElement("button");
      copy.className = "btn btn-sm";
      copy.textContent = "复制示例";
      copy.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(f.example);
          toast("已复制，回对话粘贴即可", "success");
        } catch {
          toast("复制失败，请手动选中复制", "warn");
        }
      });
      row.appendChild(copy);
    }
    list.appendChild(row);
  });
  page.appendChild(list);
}

function renderToolForm(form) {
  const box = $("#tool-list");
  const card = document.createElement("div");
  card.className = "card tool-card";
  card.id = "tool-" + form.id;
  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = form.title;
  const desc = document.createElement("div");
  desc.className = "card-desc";
  desc.textContent = form.desc;
  card.appendChild(title);
  card.appendChild(desc);

  (form.fields || []).filter((f) => f.kind !== "flag").forEach((f) => {
    const label = document.createElement("label");
    label.className = "field-label";
    label.textContent = f.label;
    label.setAttribute("for", `f-${form.id}-${f.id}`);
    card.appendChild(label);
    const row = document.createElement("div");
    row.className = "field-row";
    const el = document.createElement("input");
    el.className = "input";
    el.id = `f-${form.id}-${f.id}`;
    el.dataset.field = f.id;
    el.dataset.kind = f.kind;
    if (f.kind === "number") {
      el.type = "number";
      el.value = f.default ?? "";
      el.style.maxWidth = "120px";
    } else {
      el.type = "text";
      el.placeholder = f.placeholder || "";
    }
    row.appendChild(el);
    if (f.kind === "file") {
      const pick = document.createElement("button");
      pick.className = "btn btn-sm";
      pick.type = "button";
      pick.textContent = "选择文件";
      pick.addEventListener("click", () => {
        PICK_TARGET = el.id;
        document.querySelector('.nav-item[data-page="files"]').click();
        toast("点击文件即可填入路径；点击目录进入浏览。", "info");
      });
      row.appendChild(pick);
    }
    card.appendChild(row);
  });

  const flagField = (form.fields || []).find((f) => f.kind === "flag");
  if (flagField) {
    const flagRow = document.createElement("div");
    flagRow.className = "field-row";
    flagRow.style.marginTop = "8px";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = `f-${form.id}-allow_duplicates`;
    cb.dataset.field = "allow_duplicates";
    cb.dataset.kind = "flag";
    const lb = document.createElement("label");
    lb.htmlFor = cb.id;
    lb.textContent = flagField.label;
    lb.style.fontSize = "13px";
    flagRow.appendChild(cb);
    flagRow.appendChild(lb);
    card.appendChild(flagRow);
  }

  const actions = document.createElement("div");
  actions.className = "card-actions";
  actions.style.marginTop = "10px";
  const run = document.createElement("button");
  run.className = "btn btn-primary";
  run.type = "button";
  run.textContent = "运行";
  run.addEventListener("click", () => runTool(form, card));
  const cancel = document.createElement("button");
  cancel.className = "btn";
  cancel.type = "button";
  cancel.textContent = "取消";
  cancel.disabled = true;
  cancel.addEventListener("click", cancelRun);
  actions.appendChild(run);
  actions.appendChild(cancel);
  card.appendChild(actions);

  const result = document.createElement("div");
  result.className = "tool-result";
  result.style.marginTop = "10px";
  card.appendChild(result);
  box.appendChild(card);
  form._card = card;
}

function collectParams(form) {
  const params = {};
  for (const f of form.fields || []) {
    if (f.kind === "flag") continue;
    const el = document.getElementById(`f-${form.id}-${f.id}`);
    if (!el) continue;
    if (f.kind === "number") {
      const v = el.value.trim();
      if (v !== "") params[f.id] = Number(v);
    } else if (f.kind === "files") {
      const parts = el.value.split(/[,，\n]/).map((s) => s.trim()).filter(Boolean);
      if (parts.length) params[f.id] = parts;
    } else if (f.kind === "file") {
      const v = el.value.trim();
      if (v) params[f.id] = v;
    }
  }
  const cb = document.getElementById(`f-${form.id}-allow_duplicates`);
  if (cb && cb.checked) params.allow_duplicates = true;
  return params;
}

function setFormRunning(form, running) {
  RUNNING = running;
  const card = form._card;
  card.querySelectorAll("button").forEach((b) => {
    if (b.textContent === "运行") b.disabled = running;
    if (b.textContent === "取消") b.disabled = !running;
  });
}

async function runTool(form, card) {
  const params = collectParams(form);
  if (!form.noInput && Object.keys(params).length === 0) {
    toast("请先填写输入文件。", "warn");
    return;
  }
  setFormRunning(form, true);
  const result = card.querySelector(".tool-result");
  result.innerHTML = '<span class="hint">处理中……</span>';
  try {
    const j = await api("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tool: form.runTool, params }),
    });
    renderToolResult(j, result);
  } catch (e) {
    result.innerHTML = "";
    result.appendChild(errorBox(errorToUser(e.message)));
  } finally {
    setFormRunning(form, false);
  }
}

async function cancelRun() {
  try {
    const j = await api("/api/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!j.ok) toast(j.error || "当前没有正在运行的任务", "warn");
  } catch (e) {
    toast(errorToUser(e.message), "error");
  }
}

function renderToolResult(j, area) {
  area.innerHTML = "";
  if (j.status === "ok") {
    const box = document.createElement("div");
    box.className = "result-box";
    box.style.borderColor = "#bbf7d0";
    let text = "✓ 已完成\n" + (j.stdout || "").trim();
    if (j.output) text += `\n\n输出文件：${j.output}`;
    box.textContent = text;
    area.appendChild(box);
    if (j.output) {
      const openBtn = document.createElement("button");
      openBtn.className = "btn btn-sm";
      openBtn.style.marginTop = "8px";
      openBtn.textContent = "打开输出所在目录";
      openBtn.addEventListener("click", async () => {
        try {
          await api("/api/explorer", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: j.output }),
          });
        } catch (e) { toast(errorToUser(e.message), "error"); }
      });
      area.appendChild(openBtn);
    }
  } else if (j.status === "failed" || j.status === "rejected") {
    const msg = j.error || j.stderr || "操作未完成。";
    area.appendChild(errorBox(errorToUser(msg)));
    const det = document.createElement("details");
    det.className = "details";
    const sum = document.createElement("summary");
    sum.textContent = "查看详细信息";
    det.appendChild(sum);
    const pre = document.createElement("pre");
    pre.className = "result-box";
    pre.textContent = (j.stderr || "") + (j.stdout || "");
    det.appendChild(pre);
    area.appendChild(det);
  } else if (j.status === "cancelled") {
    area.appendChild(errorBox("已取消。"));
  } else if (j.status === "timeout") {
    area.appendChild(errorBox("操作超时，已终止。"));
  }
}

// ---------- 资源页 ----------
const RESOURCE_GROUPS = [
  {
    title: "模板",
    items: [
      { name: "投标报价表模板.xlsx", rel: "integration-pack/templates/投标报价表模板.xlsx", note: "分项报价 + 汇总" },
      { name: "IO点表模板.xlsx", rel: "integration-pack/templates/IO点表模板.xlsx", note: "DI/DO/AI/AO 点表" },
      { name: "设备清单模板.xlsx", rel: "integration-pack/templates/设备清单模板.xlsx", note: "招标/投标设备清单" },
      { name: "电缆清册模板.xlsx", rel: "integration-pack/templates/电缆清册模板.xlsx", note: "电缆敷设清册" },
      { name: "调试记录模板.xlsx", rel: "integration-pack/templates/调试记录模板.xlsx", note: "设备/回路调试记录" },
    ],
  },
  {
    title: "参考数据",
    items: [
      { name: "电缆载流量表", rel: "integration-pack/data/cable_ampacity.csv", note: "YJV 铜芯 空气/埋地" },
      { name: "水处理工艺参数", rel: "integration-pack/data/water_params.csv", note: "药剂/水力/生化/膜参数" },
      { name: "CAD 图例库", rel: "integration-pack/data/cad_legend.csv", note: "块名 → 设备/仪表类型" },
      { name: "常用规范清单", rel: "integration-pack/data/standards_list.md", note: "给排水/电气规范目录" },
    ],
  },
  {
    title: "文档",
    items: [
      { name: "操作手册（README）", rel: "integration-pack/README.md", note: "安装、使用、故障排查" },
      { name: "工具数据契约", rel: "integration-pack/docs/数据契约.md", note: "工具串联规则与数据流图" },
      { name: "插件清单", rel: "integration-pack/plugins/插件清单.md", note: "随包插件与备选清单" },
    ],
  },
];

function initResources() {
  const box = $("#resource-list");
  box.innerHTML = "";
  RESOURCE_GROUPS.forEach((group) => {
    const title = document.createElement("h2");
    title.className = "section-title";
    title.textContent = group.title;
    box.appendChild(title);
    const list = document.createElement("div");
    list.className = "file-list";
    group.items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "file-row";
      const icon = document.createElement("span");
      icon.className = "file-icon";
      icon.textContent = "·";
      const name = document.createElement("span");
      name.className = "file-name";
      name.textContent = item.name;
      name.title = item.rel;
      const note = document.createElement("span");
      note.className = "file-size";
      note.textContent = item.note || "";
      row.appendChild(icon);
      row.appendChild(name);
      row.appendChild(note);
      const preview = document.createElement("button");
      preview.className = "btn btn-sm";
      preview.textContent = "预览";
      preview.addEventListener("click", () => previewInResource(item));
      const open = document.createElement("button");
      open.className = "btn btn-sm";
      open.textContent = "资源管理器";
      open.addEventListener("click", async () => {
        try {
          await api("/api/explorer", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: item.rel }),
          });
        } catch (e) { toast(errorToUser(e.message), "error"); }
      });
      row.appendChild(preview);
      row.appendChild(open);
      list.appendChild(row);
    });
    box.appendChild(list);
  });
  const previewArea = document.createElement("div");
  previewArea.id = "resource-preview";
  previewArea.style.marginTop = "14px";
  box.appendChild(previewArea);
}

async function previewInResource(item) {
  const area = $("#resource-preview");
  area.innerHTML = '<span class="hint">加载中……</span>';
  try {
    const j = await api("/api/file?path=" + encodeURIComponent(item.rel));
    renderPreviewInto(area, j);
  } catch (e) {
    area.innerHTML = "";
    area.appendChild(errorBox(errorToUser(e.message)));
  }
}

// ---------- 设置页 ----------
function settingRow(labelText, actionBtn) {
  const row = document.createElement("div");
  row.className = "file-row";
  row.style.cursor = "default";
  const name = document.createElement("span");
  name.className = "file-name";
  name.textContent = labelText;
  row.appendChild(name);
  if (actionBtn) row.appendChild(actionBtn);
  return row;
}

function explorerBtn(rel, text) {
  const b = document.createElement("button");
  b.className = "btn btn-sm";
  b.textContent = text;
  b.addEventListener("click", async () => {
    try {
      await api("/api/explorer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: rel }),
      });
    } catch (e) { toast(errorToUser(e.message), "error"); }
  });
  return b;
}

async function initSettings() {
  const box = $("#settings-body");
  box.innerHTML = "";
  let workspace = "";
  try {
    const j = await api("/api/workspace");
    workspace = j.workspace;
  } catch { /* 保持空 */ }

  // 工作区（可更改）
  const h1 = document.createElement("h2");
  h1.className = "section-title";
  h1.textContent = "工作区";
  box.appendChild(h1);
  const wsRow = document.createElement("div");
  wsRow.className = "file-row";
  wsRow.style.cursor = "default";
  const wsLabel = document.createElement("span");
  wsLabel.className = "file-name";
  wsLabel.id = "settings-ws-label";
  wsLabel.textContent = `工作区路径：${workspace || "未设置"}`;
  wsLabel.title = workspace || "";
  wsRow.appendChild(wsLabel);
  const changeBtn = document.createElement("button");
  changeBtn.className = "btn btn-sm";
  changeBtn.textContent = "更改";
  changeBtn.title = "通过文件资源管理器选择工作区目录";
  changeBtn.addEventListener("click", changeWorkspace);
  wsRow.appendChild(changeBtn);
  const wsOpenBtn = explorerBtn("", "打开");
  wsOpenBtn.id = "settings-ws-open";
  wsOpenBtn.style.display = workspace ? "" : "none";
  wsRow.appendChild(wsOpenBtn);
  box.appendChild(wsRow);

  // 服务控制（停止服务）
  const svcRow = document.createElement("div");
  svcRow.className = "file-row";
  svcRow.style.cursor = "default";
  const svcLabel = document.createElement("span");
  svcLabel.className = "file-name";
  svcLabel.textContent = "服务控制：停止后双击桌面快捷方式可重新启动";
  svcRow.appendChild(svcLabel);
  const stopBtn = document.createElement("button");
  stopBtn.className = "btn btn-sm";
  stopBtn.textContent = "停止服务";
  stopBtn.addEventListener("click", async () => {
    try {
      const j = await api("/api/shutdown", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      toast(j.message || "工作台已停止", "success");
    } catch {
      toast("服务正在停止……", "info");
    }
  });
  svcRow.appendChild(stopBtn);
  box.appendChild(svcRow);

  // CAD 环境
  const h2 = document.createElement("h2");
  h2.className = "section-title";
  h2.textContent = "CAD 环境";
  box.appendChild(h2);
  box.appendChild(settingRow("AutoCAD / ODA 路径配置（config/cad_env.json）",
    explorerBtn("integration-pack/config", "打开配置目录")));
  box.appendChild(settingRow("检测本机 CAD 环境", (() => {
    const b = document.createElement("button");
    b.className = "btn btn-sm";
    b.textContent = "重新探测";
    b.addEventListener("click", async () => {
      const area = $("#settings-cad-result");
      area.innerHTML = '<span class="hint">探测中……</span>';
      try {
        const j = await api("/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tool: "cad_env", params: {} }),
        });
        const out = document.createElement("div");
        out.className = "result-box";
        out.textContent = (j.stdout || j.stderr || "").trim();
        area.innerHTML = "";
        area.appendChild(out);
      } catch (e) {
        area.innerHTML = "";
        area.appendChild(errorBox(errorToUser(e.message)));
      }
    });
    return b;
  })()));
  const cadResult = document.createElement("div");
  cadResult.id = "settings-cad-result";
  cadResult.style.marginTop = "8px";
  box.appendChild(cadResult);

  // 招标监控
  const h3 = document.createElement("h2");
  h3.className = "section-title";
  h3.textContent = "招标监控";
  box.appendChild(h3);
  box.appendChild(settingRow("每日 08:30 自动检索，报告写入 reports/tender",
    explorerBtn("integration-pack/reports/tender", "打开报告目录")));
  box.appendChild(settingRow("监控关键词配置（config/tender-keywords.txt）",
    explorerBtn("integration-pack/config", "打开配置目录")));

  // 依赖库
  const h4 = document.createElement("h2");
  h4.className = "section-title";
  h4.textContent = "依赖库";
  box.appendChild(h4);
  box.appendChild(settingRow("Python 依赖位于 pydeps（bootstrap 可重建）", (() => {
    const b = document.createElement("button");
    b.className = "btn btn-sm";
    b.textContent = "去重建";
    b.addEventListener("click", () => {
      document.querySelector('.nav-item[data-page="tools"]').click();
      setTimeout(() => {
        const card = document.getElementById("tool-bootstrap");
        if (card) card.scrollIntoView({ block: "start" });
      }, 50);
    });
    return b;
  })()));

  // 关于（含文档入口）
  const h5 = document.createElement("h2");
  h5.className = "section-title";
  h5.textContent = "关于";
  box.appendChild(h5);
  box.appendChild(settingRow("水处理·电气自动化整合包 v1.0（water-treatment-and-electrical-automation）"));
  box.appendChild(settingRow("六轮审计防线：编码保真 / 并发保护 / 诊断纪律 / 数据契约 / 网络安全 / Windows 环境诊断"));
  const h6 = document.createElement("h2");
  h6.className = "section-title";
  h6.textContent = "文档";
  box.appendChild(h6);
  const DOC_LINKS = [
    { name: "操作手册（README）", rel: "integration-pack/README.md" },
    { name: "工具数据契约", rel: "integration-pack/docs/数据契约.md" },
    { name: "插件清单", rel: "integration-pack/plugins/插件清单.md" },
  ];
  DOC_LINKS.forEach((d) => {
    const b = document.createElement("button");
    b.className = "btn btn-sm";
    b.textContent = d.name;
    b.style.margin = "0 8px 8px 0";
    b.addEventListener("click", () => {
      document.querySelector('.nav-item[data-page="resources"]').click();
      previewInResource({ rel: d.rel, name: d.name });
    });
    box.appendChild(b);
  });
}

// ---------- 全局动作 ----------
function initActions() {
  $("#btn-open-workspace").addEventListener("click", async () => {
    try {
      await api("/api/explorer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: "" }),
      });
    } catch (e) {
      toast(errorToUser(e.message), "error");
    }
  });
}

function setWorkspaceDisplay(ws) {
  const el = $("#workspace-display");
  el.textContent = ws ? "工作区：" + ws : "工作区：未设置";
  el.title = ws || "";
}

/** 同步工作区到顶栏与设置页（避免设置页缓存旧值）。 */
function syncWorkspaceUI(ws) {
  setWorkspaceDisplay(ws);
  const lbl = document.getElementById("settings-ws-label");
  if (lbl) {
    lbl.textContent = "工作区路径：" + (ws || "未设置");
    lbl.title = ws || "";
  }
  // “打开”按钮仅在已设定工作区时出现（未设定时隐藏，避免打开无意义目录）
  const openBtn = document.getElementById("settings-ws-open");
  if (openBtn) openBtn.style.display = ws ? "" : "none";
}

/** 设置页“更改”：通过文件资源管理器选择工作区目录并保存。 */
async function changeWorkspace() {
  try {
    const picked = await api("/api/workspace/pick", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!picked.ok || !picked.path) return; // 用户取消选择
    const saved = await api("/api/workspace", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: picked.path }),
    });
    syncWorkspaceUI(saved.workspace);
    toast("工作区已更新", "success");
  } catch (e) {
    toast(errorToUser(e.message || "更改失败"), "error");
  }
}

async function loadWorkspace() {
  try {
    const j = await api("/api/workspace");
    if (!j.custom) {
      showWorkspacePicker();
      setWorkspaceDisplay("");
      return;
    }
    setWorkspaceDisplay(j.workspace);
  } catch (e) {
    $("#workspace-display").textContent = "工作区：无法读取";
    console.error("[ui] workspace failed:", e);
  }
}

/** 首次使用：引导用户选择工作区目录（选择后记录，不再弹出）。 */
function showWorkspacePicker() {
  if (document.getElementById("ws-picker")) return;

  const overlay = document.createElement("div");
  overlay.id = "ws-picker";
  overlay.className = "ws-picker-overlay";

  const card = document.createElement("div");
  card.className = "ws-picker-card";

  const title = document.createElement("h2");
  title.className = "section-title";
  title.textContent = "选择工作区目录";

  const desc = document.createElement("p");
  desc.className = "hint";
  desc.textContent = "请选择一个用于存放你的项目文件（报价表、图纸、报告等）的本地目录。首次设置后，工作台将把该目录作为你的工作区，后续可在「设置」页修改。";

  const fieldRow = document.createElement("div");
  fieldRow.className = "field-row";
  const input = document.createElement("input");
  input.className = "input";
  input.type = "text";
  input.id = "ws-picker-input";
  input.placeholder = "例如 D:\\Projects\\某某项目";
  input.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") saveBtn.click();
  });
  fieldRow.appendChild(input);

  const browseBtn = document.createElement("button");
  browseBtn.className = "btn btn-sm";
  browseBtn.type = "button";
  browseBtn.textContent = "浏览…";
  browseBtn.addEventListener("click", async () => {
    try {
      const j = await api("/api/workspace/pick", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (j.ok && j.path) input.value = j.path;
    } catch (e) {
      toast(errorToUser(e.message || "打开目录选择器失败"), "error");
    }
  });
  fieldRow.appendChild(browseBtn);

  const actions = document.createElement("div");
  actions.className = "card-actions";

  const saveBtn = document.createElement("button");
  saveBtn.className = "btn btn-primary";
  saveBtn.textContent = "保存";
  saveBtn.addEventListener("click", async () => {
    const p = input.value.trim();
    if (!p) { toast("请输入工作区目录路径。", "warn"); return; }
    try {
      const j = await api("/api/workspace", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: p }),
      });
      syncWorkspaceUI(j.workspace);
      overlay.remove();
      toast("工作区已设置", "success");
    } catch (e) {
      toast(errorToUser(e.message || (e.payload && e.payload.hint) || "设置失败"), "error");
    }
  });

  const laterBtn = document.createElement("button");
  laterBtn.className = "btn";
  laterBtn.textContent = "稍后设置";
  laterBtn.addEventListener("click", () => {
    overlay.remove();
    setWorkspaceDisplay("");
  });

  actions.appendChild(saveBtn);
  actions.appendChild(laterBtn);
  card.appendChild(title);
  card.appendChild(desc);
  card.appendChild(fieldRow);
  card.appendChild(actions);
  overlay.appendChild(card);
  document.body.appendChild(overlay);
  input.focus();
}

// ---------- 启动 ----------
document.addEventListener("DOMContentLoaded", () => {
  initNav();
  initActions();
  initTools();
  initResources();
  initSettings();
  loadWorkspace();
  loadEnv();
  loadQuickDirs();
});
