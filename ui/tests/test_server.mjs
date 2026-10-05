// ui/tests/test_server.mjs —— server.py HTTP 行为测试（纯脚本式，零 spawn，零依赖）
// 编排说明：受限沙箱下 Node 无法 spawn（node:test runner 自身也会 spawn，故不用框架）；
// 同时内置 fetch（undici keep-alive 池）在沙箱退出清理时会触发 libuv 断言，
// 因此 HTTP 客户端使用 node:http + agent:false（每请求独立连接，退出无活动句柄）。
//
// 2.1.0 起的密闭性要求（原用例在这三处不密闭，换个机器/换个配置就变红）：
//   1) 整合包内资源一律用 @pack/ 前缀寻址。相对路径按契约优先落在「文件区」，
//      会随用户配置漂移（原用例写 integration-pack/xxx，只在未配置文件区时成立）。
//   2) 工具输出固定写到 <PACK_ROOT>/reports/ui（server.py 的 out_dir），而 /api/run 回报的
//      output 字段随文件区配置在「相对/绝对」之间变化，故断言改为「该目录新增了文件」。
//   3) 静态前端已随 2.1.0 内嵌进 DSH 而移除，相关用例改为断言 404 契约而非 200。
// 另外：本文件不修改用户的文件区配置；workspace 用例在改前保存、改后原样恢复。
import http from "node:http";
import fsp from "node:fs/promises";
import path from "node:path";

const PORT = process.env.UI_TEST_PORT;
if (!PORT) {
  console.error("UI_TEST_PORT 未设置：请通过 ui/tests/run_integration.ps1 运行");
  process.exit(2);
}

function request(reqPath, method = "GET", bodyObj = null) {
  const body = bodyObj === null ? null : JSON.stringify(bodyObj);
  return new Promise((resolve, reject) => {
    const options = {
      host: "127.0.0.1",
      port: Number(PORT),
      path: reqPath,
      method,
      agent: false,
      headers: { Connection: "close" },
    };
    if (body !== null) {
      options.headers["Content-Type"] = "application/json";
      options.headers["Content-Length"] = Buffer.byteLength(body);
    }
    const req = http.request(options, (res) => {
      let data = "";
      res.on("data", (c) => { data += c; });
      res.on("end", () => resolve({ status: res.statusCode, text: data }));
    });
    req.on("error", reject);
    if (body !== null) req.write(body);
    req.end();
  });
}

const packPath = (rel) => "@pack/" + rel.split(path.sep).join("/");
const q = (rel) => "path=" + encodeURIComponent(rel);

let passed = 0, failed = 0, skipped = 0;
async function check(name, fn) {
  try {
    await fn();
    passed += 1;
    console.log(`  PASS  ${name}`);
  } catch (e) {
    if (e && e.skip === true) {
      skipped += 1;
      console.log(`  SKIP  ${name}  ${e.message}`);
      return;
    }
    failed += 1;
    console.log(`  FAIL  ${name}  ${e.message}`);
  }
}
function skip(reason) {
  const e = new Error(reason);
  e.skip = true;
  return e;
}

// 未配置文件区时可达的默认根（server.py: WORKSPACE_ROOT = PACK_ROOT 的父目录）
let PACK_ROOT = "";
let OUT_DIR = "";
let CFG_PATH = "";
let cfgExisted = false;
let cfgBackup = null;
let initialOut = new Set();

async function outSnapshot() {
  return new Set(await fsp.readdir(OUT_DIR));
}
async function addedSince(snap) {
  const now = await fsp.readdir(OUT_DIR);
  return now.filter((f) => !snap.has(f));
}
async function restoreWorkspaceConfig() {
  if (!CFG_PATH) return;
  if (cfgExisted) await fsp.writeFile(CFG_PATH, cfgBackup, "utf8");
  else await fsp.rm(CFG_PATH, { force: true });
}

async function main() {
  console.log(`  INFO  端口 ${PORT}`);

  // ── 探明整合包根（布局无关：开发布局=…/integration-pack，导入布局=…/<profile>/wta）──
  const hres = await request("/api/health");
  if (hres.status !== 200) throw new Error(`/api/health 不可用：status=${hres.status}`);
  const health = JSON.parse(hres.text);
  PACK_ROOT = health.pack_root;
  OUT_DIR = path.join(PACK_ROOT, "reports", "ui");
  CFG_PATH = path.join(PACK_ROOT, "config", "ui-workspace.json");
  await fsp.mkdir(OUT_DIR, { recursive: true });
  initialOut = await outSnapshot();
  try {
    cfgBackup = await fsp.readFile(CFG_PATH, "utf8");
    cfgExisted = true;
  } catch {
    cfgExisted = false;
  }
  console.log(`  INFO  PACK_ROOT = ${PACK_ROOT}`);
  console.log(`  INFO  文件区配置${cfgExisted ? "存在（测试将保存并原样恢复）" : "不存在（测试不创建）"}`);

  // ---- 2A 服务基本信息 ----
  await check("2A-1 /api/health 返回 200 与关键字段", async () => {
    if (hres.status !== 200) throw new Error(`status=${hres.status}`);
    if (health.status !== "ok") throw new Error("status field");
    if (typeof health.workspace !== "string") throw new Error(`workspace 类型=${typeof health.workspace}`);
    if (!path.isAbsolute(health.pack_root)) throw new Error(`pack_root 非绝对路径：${health.pack_root}`);
    const st = await fsp.stat(health.pack_root).catch(() => null);
    if (!st || !st.isDirectory()) throw new Error(`pack_root 不存在：${health.pack_root}`);
  });

  await check("2A-2 根路径 / 不再服务静态页（2.1.0 已内嵌进 DSH）", async () => {
    const r = await request("/");
    if (r.status !== 404) throw new Error(`status=${r.status}（应为 404）`);
    if (!/无静态页面/.test(r.text)) throw new Error(`缺说明文案：${r.text.slice(0, 60)}`);
  });

  await check("2A-3 未知 /api 路由返回 404 JSON", async () => {
    const r = await request("/api/nope");
    if (r.status !== 404) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (j.error !== "not found") throw new Error("error field");
  });

  await check("2A-5 中文路径寻址正常（@pack 中文文件名）", async () => {
    const r = await request("/api/file?" + q(packPath("docs/数据契约.md")));
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (!j.previewable) throw new Error("应可预览");
  });

  // ---- 2B 静态资源已移除的契约 ----
  for (const [id, rel] of [["2B-1", "/index.html"], ["2B-2", "/style.css"], ["2B-3", "/app.js"]]) {
    await check(`${id} ${rel} 返回 404（静态前端已移除）`, async () => {
      const r = await request(rel);
      if (r.status !== 404) throw new Error(`status=${r.status}（应为 404）`);
    });
  }

  await check("2B-4 静态目录逃逸被拒绝", async () => {
    const r = await request("/../server.py");
    if (r.status !== 403 && r.status !== 404) throw new Error(`status=${r.status}（应为 403/404）`);
  });

  // ---- 2C 目录 / 文件 / 环境 ----
  await check("2C-1 /api/dirs 列出当前文件区根", async () => {
    const r = await request("/api/dirs?" + q(""));
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (!j.exists || !Array.isArray(j.entries)) throw new Error(`exists=${j.exists}`);
  });

  await check("2C-2 /api/dirs 列出整合包根（中文路径编码）", async () => {
    const r = await request("/api/dirs?" + q("@pack"));
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    const names = j.entries.map((e) => e.name);
    for (const n of ["config", "data", "docs", "scripts", "templates", "skills"]) {
      if (!names.includes(n)) throw new Error(`缺少目录 ${n}`);
    }
  });

  await check("2C-3 /api/dirs 目录逃逸（../）被拒绝", async () => {
    const r = await request("/api/dirs?" + q("@pack/../../.."));
    if (r.status !== 403) throw new Error(`status=${r.status}（应为 403）`);
  });

  await check("2C-4 /api/dirs 绝对盘符被拒绝", async () => {
    const r = await request("/api/dirs?" + q("C:/Windows"));
    if (r.status !== 403) throw new Error(`status=${r.status}（应为 403）`);
  });

  await check("2C-5 /api/dirs 不存在目录返回 404 与提示", async () => {
    const r = await request("/api/dirs?" + q("@pack/不存在的目录xyz"));
    if (r.status !== 404) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (!j.hint) throw new Error("缺少提示");
  });

  await check("2C-6 /api/file 预览文本文件（UTF-8 中文保真）", async () => {
    const r = await request("/api/file?" + q(packPath("README.md")));
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (!j.previewable) throw new Error("应可预览");
    if (!j.content.includes("一键部署") && !j.content.includes("水处理与电气自动化")) {
      throw new Error("中文内容缺失");
    }
  });

  await check("2C-7 /api/file xlsx 现在可预览（table 类型，Phase 3 升级）", async () => {
    const r = await request("/api/file?" + q(packPath("templates/投标报价表模板.xlsx")));
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (!j.previewable || j.kind !== "table") throw new Error("xlsx 应支持表格预览");
  });

  await check("2C-8 /api/file 文件逃逸被拒绝", async () => {
    const r = await request("/api/file?" + q("../../Windows/win.ini"));
    if (r.status !== 403) throw new Error(`status=${r.status}（应为 403）`);
  });

  await check("2C-9 /api/explorer 已移除 → 404", async () => {
    const r = await request("/api/explorer", "POST", { path: "C:/Windows" });
    if (r.status !== 404 && r.status !== 403) throw new Error(`status=${r.status}`);
  });

  await check("2C-10 /api/env 返回环境状态", async () => {
    const r = await request("/api/env");
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    for (const k of ["python", "pydeps", "cad", "skills"]) {
      if (!(k in j)) throw new Error(`缺少字段 ${k}`);
    }
    if (!j.python.ok) throw new Error(`python 不可用：${JSON.stringify(j.python)}`);
    if (!j.pydeps.ok) throw new Error(`pydeps 不可用：${JSON.stringify(j.pydeps)}`);
    if (j.skills < 7) throw new Error(`skills=${j.skills}（应 ≥7）`);
  });

  // 资源页/文件页的原生预览要求文件系统绝对路径：@pack/... 只是后端寻址标识，
  // 直接塞进 DSH 的资源地址会被当会话相对路径解析。以下两条守住 abs 字段。
  await check("2C-11 /api/resources 每项都给出 abs 绝对路径", async () => {
    const r = await request("/api/resources");
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    const all = (j.quickDirs || []).concat((j.groups || []).reduce((a, g) => a.concat(g.items || []), []));
    if (!all.length) throw new Error("资源清单为空");
    for (const it of all) {
      if (typeof it.abs !== "string" || !path.isAbsolute(it.abs)) {
        throw new Error(`缺少绝对路径 abs：${JSON.stringify(it).slice(0, 120)}`);
      }
    }
  });

  await check("2C-12 /api/dirs 条目都给出 abs 绝对路径", async () => {
    const r = await request("/api/dirs?" + q("@pack/templates"));
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (!j.entries.length) throw new Error("模板目录为空");
    for (const it of j.entries) {
      if (typeof it.abs !== "string" || !path.isAbsolute(it.abs)) {
        throw new Error(`缺少绝对路径 abs：${JSON.stringify(it).slice(0, 120)}`);
      }
    }
  });

  // ---- 2D 工具运行链路（夹具写在输出目录内，用 @pack/ 寻址，不碰用户文件区） ----
  const FIX = (name) => packPath(path.join("reports", "ui", name));
  const disk = (name) => path.join(OUT_DIR, name);

  const inputCsv = FIX("2d-test-input.csv");
  const emptyCsv = FIX("2d-test-empty.csv");
  const badExt = FIX("2d-test-bad.txt");
  const bigCsv = FIX("2d-test-big.csv");
  await fsp.writeFile(disk("2d-test-input.csv"),
    "设备名称,规格型号,单位,数量\n潜水排污泵,Q=100m3/h,台,2\n电磁流量计,DN200,台,1\n", "utf8");
  await fsp.writeFile(disk("2d-test-empty.csv"), "设备名称\n", "utf8");
  await fsp.writeFile(disk("2d-test-bad.txt"), "not a table", "utf8");
  const bigLines = new Array(60000).fill("设备A,规格X,台,1").join("\n");
  await fsp.writeFile(disk("2d-test-big.csv"), "设备名称,规格型号,单位,数量\n" + bigLines + "\n", "utf8");

  await check("2D-1 normalize 正常链路（中文表头）→ 状态 ok + 生成输出", async () => {
    const snap = await outSnapshot();
    const r = await request("/api/run", "POST", { tool: "normalize", params: { input: inputCsv } });
    if (r.status !== 200) throw new Error(`http=${r.status}`);
    const j = JSON.parse(r.text);
    if (j.status !== "ok") throw new Error(`status=${j.status} stderr=${(j.stderr || "").slice(0, 200)}`);
    if (!j.output) throw new Error("缺少输出路径");
    const added = await addedSince(snap);
    if (!added.length) throw new Error("输出目录未新增文件");
  });

  await check("2D-2 缺 input 参数 → 400 rejected", async () => {
    const r = await request("/api/run", "POST", { tool: "normalize", params: {} });
    if (r.status !== 400) throw new Error(`http=${r.status}`);
    const j = JSON.parse(r.text);
    if (j.status !== "rejected" || !j.error.includes("输入文件")) throw new Error(j.error);
  });

  await check("2D-3 input 路径逃逸 → 400 rejected", async () => {
    const r = await request("/api/run", "POST", { tool: "normalize", params: { input: "C:/Windows/win.ini" } });
    if (r.status !== 400) throw new Error(`http=${r.status}`);
    const j = JSON.parse(r.text);
    if (j.status !== "rejected" || !j.error.includes("允许范围")) throw new Error(j.error);
  });

  await check("2D-4 input 不存在 → 400 rejected", async () => {
    const r = await request("/api/run", "POST", { tool: "normalize", params: { input: FIX("不存在.csv") } });
    if (r.status !== 400) throw new Error(`http=${r.status}`);
    const j = JSON.parse(r.text);
    if (j.status !== "rejected" || !j.error.includes("不存在")) throw new Error(j.error);
  });

  await check("2D-5 文件类型错误 → 400 rejected", async () => {
    const r = await request("/api/run", "POST", { tool: "normalize", params: { input: badExt } });
    if (r.status !== 400) throw new Error(`http=${r.status}`);
    const j = JSON.parse(r.text);
    if (j.status !== "rejected" || !j.error.includes("不支持的文件类型")) throw new Error(j.error);
  });

  await check("2D-6 未知工具 → 400 rejected", async () => {
    const r = await request("/api/run", "POST", { tool: "rm-rf", params: { input: inputCsv } });
    if (r.status !== 400) throw new Error(`http=${r.status}`);
  });

  await check("2D-7 工具契约错误透传（空表 → failed + 契约信息）", async () => {
    const r = await request("/api/run", "POST", { tool: "normalize", params: { input: emptyCsv } });
    if (r.status !== 200) throw new Error(`http=${r.status}`);
    const j = JSON.parse(r.text);
    if (j.status !== "failed") throw new Error(`status=${j.status}`);
    if (!/空数据|数据契约/.test(j.stderr || "")) throw new Error(`stderr=${(j.stderr || "").slice(0, 120)}`);
  });

  await check("2D-8 取消运行中的任务 → cancelled", async () => {
    const runPromise = request("/api/run", "POST", { tool: "normalize", params: { input: bigCsv } });
    await new Promise((r) => setTimeout(r, 400));
    const c = await request("/api/cancel", "POST", {});
    if (!JSON.parse(c.text).ok) throw new Error("cancel 未受理");
    const r = await runPromise;
    const j = JSON.parse(r.text);
    if (j.status !== "cancelled") throw new Error(`status=${j.status}`);
  });

  await check("2D-9 无任务时取消 → ok:false", async () => {
    const r = await request("/api/cancel", "POST", {});
    const j = JSON.parse(r.text);
    if (j.ok !== false) throw new Error("应返回 ok:false");
  });

  await check("2D-10 中文+空格路径输入正常", async () => {
    const rel = FIX("2d 测试 输入.csv");
    await fsp.writeFile(disk("2d 测试 输入.csv"), "设备名称,数量\n泵 A,1\n", "utf8");
    const r = await request("/api/run", "POST", { tool: "normalize", params: { input: rel } });
    const j = JSON.parse(r.text);
    if (j.status !== "ok") throw new Error(`status=${j.status} ${(j.stderr || "").slice(0, 120)}`);
  });

  // ---- Phase 4：其余工具逐个接入验证 ----
  const qA = FIX("4a-报价A.csv");
  const qB = FIX("4a-报价B.csv");
  await fsp.writeFile(disk("4a-报价A.csv"), "设备名称,规格型号,单价\n潜污泵,Q=100,18500\n流量计,DN200,3200\n", "utf8");
  await fsp.writeFile(disk("4a-报价B.csv"), "设备名称,规格型号,单价\n潜污泵,Q=100,19800\n流量计,DN200,3000\n", "utf8");

  await check("4A compare 多文件比对 → ok + 生成输出", async () => {
    const snap = await outSnapshot();
    const r = await request("/api/run", "POST", { tool: "compare", params: { inputs: [qA, qB] } });
    const j = JSON.parse(r.text);
    if (j.status !== "ok") throw new Error(`status=${j.status} ${(j.stderr || "").slice(0, 150)}`);
    if (!j.output) throw new Error("缺少输出");
    if (!(await addedSince(snap)).length) throw new Error("输出目录未新增文件");
  });

  await check("4B compare 文件数不足 → rejected", async () => {
    const r = await request("/api/run", "POST", { tool: "compare", params: { inputs: [qA] } });
    const j = JSON.parse(r.text);
    if (j.status !== "rejected" || !/2~8/.test(j.error)) throw new Error(j.error);
  });

  await check("4C cost 参数化测算 → ok", async () => {
    const r = await request("/api/run", "POST", {
      tool: "cost",
      params: { input: qA, tax: 13, freight: 500, install: 0, admin: 5, profit: 8 },
    });
    const j = JSON.parse(r.text);
    if (j.status !== "ok") throw new Error(`status=${j.status} ${(j.stderr || "").slice(0, 150)}`);
    if (!/含税总价/.test(j.stdout)) throw new Error("缺测算结果");
  });

  await check("4D cost 数值参数越界 → rejected", async () => {
    const r = await request("/api/run", "POST", { tool: "cost", params: { input: qA, tax: 99 } });
    const j = JSON.parse(r.text);
    if (j.status !== "rejected" || !/不能大于/.test(j.error)) throw new Error(j.error);
  });

  await check("4E diff 双文件核对 → ok", async () => {
    const r = await request("/api/run", "POST", { tool: "diff", params: { tender: qA, quote: qB } });
    const j = JSON.parse(r.text);
    if (j.status !== "ok") throw new Error(`status=${j.status} ${(j.stderr || "").slice(0, 150)}`);
  });

  await check("4F dxf_parse 图纸提取 → ok", async () => {
    const dxf = packPath(path.join("reports", "smoke", "测试PID.dxf"));
    const st = await fsp.stat(path.join(PACK_ROOT, "reports", "smoke", "测试PID.dxf")).catch(() => null);
    if (!st) throw skip("缺夹具 reports/smoke/测试PID.dxf（由 scripts/smoke_test.py 生成）");
    const r = await request("/api/run", "POST", { tool: "dxf_parse", params: { dxf } });
    const j = JSON.parse(r.text);
    if (j.status !== "ok") throw new Error(`status=${j.status} ${(j.stderr || "").slice(0, 150)}`);
    if (!/提取条目/.test(j.stdout)) throw new Error("缺提取结果");
  });

  await check("4G cad_env 环境探测 → ok（JSON 输出）", async () => {
    const r = await request("/api/run", "POST", { tool: "cad_env", params: {} });
    const j = JSON.parse(r.text);
    if (j.status !== "ok") throw new Error(`status=${j.status} ${(j.stderr || "").slice(0, 150)}`);
    if (!/"dwg_to_dxf"/.test(j.stdout)) throw new Error("缺 JSON 探测结果");
  });

  // ---- 预览扩展与 workspace 配置 ----
  await check("4H xlsx 预览 → previewable + table", async () => {
    const r = await request("/api/file?" + q(packPath("templates/投标报价表模板.xlsx")));
    const j = JSON.parse(r.text);
    if (!j.previewable || j.kind !== "table") throw new Error(JSON.stringify(j).slice(0, 140));
    if (!/Sheet/.test(j.content)) throw new Error("缺表格内容");
  });

  await check("4I docx 预览 → 段落文本", async () => {
    const rel = FIX("4i-test.docx");
    const st = await fsp.stat(disk("4i-test.docx")).catch(() => null);
    if (!st) throw skip("缺夹具 reports/ui/4i-test.docx（由 run_integration.ps1 生成）");
    const r = await request("/api/file?" + q(rel));
    const j = JSON.parse(r.text);
    if (!j.previewable) throw new Error(j.reason || "不可预览");
    if (!/预览测试/.test(j.content)) throw new Error("内容缺失");
  });

  await check("4J .doc 旧格式 → 明确提示不支持", async () => {
    await fsp.writeFile(disk("4j-old.doc"), "fake doc", "utf8");
    const r = await request("/api/file?" + q(FIX("4j-old.doc")));
    const j = JSON.parse(r.text);
    if (j.previewable) throw new Error("不应可预览");
    if (!/旧版 \.doc/.test(j.reason)) throw new Error(j.reason);
  });

  await check("4K md 预览带 kind=md 标记", async () => {
    const r = await request("/api/file?" + q(packPath("docs/数据契约.md")));
    const j = JSON.parse(r.text);
    if (j.kind !== "md" || !j.previewable) throw new Error(JSON.stringify(j).slice(0, 140));
  });

  await check("4L /api/workspace 返回文件区状态（已配置/未配置两种合法形态）", async () => {
    const r = await request("/api/workspace");
    const j = JSON.parse(r.text);
    if (typeof j.workspace !== "string" || typeof j.custom !== "boolean") {
      throw new Error(JSON.stringify(j));
    }
    if (j.custom) {
      const st = await fsp.stat(j.workspace).catch(() => null);
      if (!st || !st.isDirectory()) throw new Error(`custom=true 但目录不存在：${j.workspace}`);
    } else if (j.workspace !== "") {
      throw new Error(`未配置时 workspace 应为空串，实为 ${j.workspace}`);
    }
  });

  await check("4M workspace 更改生效 + 原样恢复", async () => {
    const r1 = await request("/api/workspace", "POST", { path: OUT_DIR });
    if (!JSON.parse(r1.text).ok) throw new Error("保存失败");
    const r2 = await request("/api/workspace");
    const j2 = JSON.parse(r2.text);
    if (j2.workspace.replace(/\//g, "\\").toLowerCase() !== OUT_DIR.replace(/\//g, "\\").toLowerCase()) {
      throw new Error(`更改未生效：${j2.workspace}`);
    }
    const r3 = await request("/api/dirs?path=");
    if (!JSON.parse(r3.text).exists) throw new Error("新文件区未加入白名单");
    // 关键：原样恢复用户的既有配置（此前版本会把用户配置改成 D:/DeepSeek Harness，属于破坏性副作用）
    await restoreWorkspaceConfig();
    const r4 = await request("/api/workspace");
    const j4 = JSON.parse(r4.text);
    if (cfgExisted) {
      const want = JSON.parse(cfgBackup).path;
      if (j4.workspace.replace(/\//g, "\\").toLowerCase() !== want.replace(/\//g, "\\").toLowerCase()) {
        throw new Error(`未恢复原配置：期望 ${want}，实为 ${j4.workspace}`);
      }
    } else if (j4.custom !== false || j4.workspace !== "") {
      throw new Error(`应回到未配置状态，实为 ${JSON.stringify(j4)}`);
    }
  });

  await check("4N workspace 不存在目录 → 400", async () => {
    const r = await request("/api/workspace", "POST", { path: "D:/不存在目录xyz123" });
    if (r.status !== 400) throw new Error(`status=${r.status}`);
  });

  await check("4O workspace 非字符串 → 400", async () => {
    const r = await request("/api/workspace", "POST", { path: 123 });
    if (r.status !== 400) throw new Error(`status=${r.status}`);
  });
}

async function teardown() {
  try {
    await restoreWorkspaceConfig();
  } catch { /* 忽略 */ }
  try {
    const created = await addedSince(initialOut);
    for (const f of created) await fsp.rm(path.join(OUT_DIR, f), { force: true });
    for (const f of ["2d-test-input.csv", "2d-test-empty.csv", "2d-test-bad.txt", "2d-test-big.csv", "2d 测试 输入.csv"]) {
      await fsp.rm(path.join(OUT_DIR, f), { force: true });
    }
  } catch { /* 忽略 */ }
}

try {
  await main();
} catch (e) {
  failed += 1;
  console.log(`  FAIL  （测试框架异常）${e && e.message}`);
} finally {
  await teardown();
}

console.log(`\n结果：${passed} 通过 / ${failed} 失败 / ${skipped} 跳过`);
process.exit(failed > 0 ? 1 : 0);
