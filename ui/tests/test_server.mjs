// ui/tests/test_server.mjs —— server.py HTTP 行为测试（纯脚本式，零 spawn，零依赖）
// 编排说明：受限沙箱下 Node 无法 spawn（node:test runner 自身也会 spawn，故不用框架）；
// 同时内置 fetch（undici keep-alive 池）在沙箱退出清理时会触发 libuv 断言，
// 因此 HTTP 客户端使用 node:http + agent:false（每请求独立连接，退出无活动句柄）。
import http from "node:http";

const PORT = process.env.UI_TEST_PORT;
if (!PORT) {
  console.error("UI_TEST_PORT 未设置：请通过 ui/tests/run_integration.ps1 运行");
  process.exit(2);
}

function request(path, method = "GET", bodyObj = null) {
  const body = bodyObj === null ? null : JSON.stringify(bodyObj);
  return new Promise((resolve, reject) => {
    const options = {
      host: "127.0.0.1",
      port: Number(PORT),
      path,
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

let passed = 0, failed = 0;
async function check(name, fn) {
  try {
    await fn();
    passed += 1;
    console.log(`  PASS  ${name}`);
  } catch (e) {
    failed += 1;
    console.log(`  FAIL  ${name}  ${e.message}`);
  }
}

async function main() {
  await check("2A-1 /api/health 返回 200 与关键字段", async () => {
    const r = await request("/api/health");
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (j.status !== "ok") throw new Error("status field");
    if (!j.workspace.includes("DeepSeek Harness")) throw new Error(`workspace=${j.workspace}`);
    if (!j.pack_root.endsWith("integration-pack")) throw new Error(`pack_root=${j.pack_root}`);
  });

  await check("2A-2 根路径 / 返回首页 200（静态已就绪）", async () => {
    const r = await request("/");
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    if (!r.text.includes("水处理 · 电气自动化工作台")) throw new Error("首页内容缺失");
  });

  await check("2A-3 未知 /api 路由返回 404 JSON", async () => {
    const r = await request("/api/nope");
    if (r.status !== 404) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (j.error !== "not found") throw new Error("error field");
  });

  await check("2A-5 中文路径下服务正常响应", async () => {
    const r = await request("/api/health");
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (!j.workspace.includes("DeepSeek Harness")) throw new Error("workspace missing");
  });

  await check("2B-1 /index.html 返回 200 text/html", async () => {
    const r = await request("/index.html");
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    if (!r.text.includes("水处理 · 电气自动化工作台")) throw new Error("首页内容缺失");
  });

  await check("2B-2 /style.css 返回 200", async () => {
    const r = await request("/style.css");
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    if (!r.text.includes("--accent")) throw new Error("design tokens 缺失");
  });

  await check("2B-3 /app.js 返回 200", async () => {
    const r = await request("/app.js");
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    if (!r.text.includes("errorToUser")) throw new Error("错误映射函数缺失");
  });

  await check("2B-4 静态目录逃逸被拒绝", async () => {
    const r = await request("/../server.py");
    if (r.status !== 403 && r.status !== 404) throw new Error(`status=${r.status}（应为 403/404）`);
  });

  // ---- 2C 目录 / 文件 / 资源管理器 / 创建目录 ----
  await check("2C-1 /api/dirs 列出工作区根", async () => {
    const r = await request("/api/dirs?path=");
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (!j.exists || j.entries.length === 0) throw new Error("空列表");
    if (!j.entries.some((e) => e.name === "integration-pack")) throw new Error("缺少 integration-pack");
  });

  await check("2C-2 /api/dirs 列出 integration-pack（中文路径编码）", async () => {
    const r = await request("/api/dirs?path=" + encodeURIComponent("integration-pack"));
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    const names = j.entries.map((e) => e.name);
    for (const n of ["config", "data", "docs", "scripts", "templates", "skills"]) {
      if (!names.includes(n)) throw new Error(`缺少目录 ${n}`);
    }
  });

  await check("2C-3 /api/dirs 目录逃逸（../）被拒绝", async () => {
    const r = await request("/api/dirs?path=" + encodeURIComponent("integration-pack/../../.."));
    if (r.status !== 403) throw new Error(`status=${r.status}（应为 403）`);
  });

  await check("2C-4 /api/dirs 绝对盘符被拒绝", async () => {
    const r = await request("/api/dirs?path=" + encodeURIComponent("C:/Windows"));
    if (r.status !== 403) throw new Error(`status=${r.status}（应为 403）`);
  });

  await check("2C-5 /api/dirs 不存在目录返回 404 与提示", async () => {
    const r = await request("/api/dirs?path=" + encodeURIComponent("integration-pack/不存在的目录xyz"));
    if (r.status !== 404) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (!j.hint) throw new Error("缺少提示");
  });

  await check("2C-6 /api/file 预览文本文件（UTF-8 中文保真）", async () => {
    const r = await request("/api/file?path=" + encodeURIComponent("integration-pack/README.md"));
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (!j.previewable) throw new Error("应可预览");
    if (!j.content.includes("一键部署") && !j.content.includes("水处理与电气自动化")) {
      throw new Error("中文内容缺失");
    }
  });

  await check("2C-7 /api/file xlsx 现在可预览（table 类型，Phase 3 升级）", async () => {
    const r = await request("/api/file?path=" + encodeURIComponent("integration-pack/templates/投标报价表模板.xlsx"));
    if (r.status !== 200) throw new Error(`status=${r.status}`);
    const j = JSON.parse(r.text);
    if (!j.previewable || j.kind !== "table") throw new Error("xlsx 应支持表格预览");
  });

  await check("2C-8 /api/file 文件逃逸被拒绝", async () => {
    const r = await request("/api/file?path=" + encodeURIComponent("../../Windows/win.ini"));
    if (r.status !== 403) throw new Error(`status=${r.status}（应为 403）`);
  });

  await check("2C-9 /api/explorer 白名单外路径拒绝", async () => {
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
    if (j.skills < 7) throw new Error(`skills=${j.skills}（应 ≥7）`);
  });

  // ---- 2D/2E 工具运行链路（normalize） ----
  const UI_REPORT = "D:/DeepSeek Harness/integration-pack/reports/ui";
  const mkdir = await import("node:fs").then((f) => f.promises.mkdir(UI_REPORT, { recursive: true }));
  const FSW = await import("node:fs").then((f) => f.promises);

  const inputCsv = "integration-pack/reports/ui/2d-test-input.csv";
  const emptyCsv = "integration-pack/reports/ui/2d-test-empty.csv";
  const badExt = "integration-pack/reports/ui/2d-test-bad.txt";
  const bigCsv = "integration-pack/reports/ui/2d-test-big.csv";
  await FSW.writeFile(UI_REPORT + "/2d-test-input.csv",
    "设备名称,规格型号,单位,数量\n潜水排污泵,Q=100m3/h,台,2\n电磁流量计,DN200,台,1\n", "utf8");
  await FSW.writeFile(UI_REPORT + "/2d-test-empty.csv", "设备名称\n", "utf8");
  await FSW.writeFile(UI_REPORT + "/2d-test-bad.txt", "not a table", "utf8");
  const bigLines = new Array(60000).fill("设备A,规格X,台,1").join("\n");
  await FSW.writeFile(UI_REPORT + "/2d-test-big.csv", "设备名称,规格型号,单位,数量\n" + bigLines + "\n", "utf8");

  await check("2D-1 normalize 正常链路（中文表头）→ 状态 ok + 输出文件", async () => {
    const r = await request("/api/run", "POST", { tool: "normalize", params: { input: inputCsv } });
    if (r.status !== 200) throw new Error(`http=${r.status}`);
    const j = JSON.parse(r.text);
    if (j.status !== "ok") throw new Error(`status=${j.status} stderr=${(j.stderr || "").slice(0, 200)}`);
    if (!j.output) throw new Error("缺少输出路径");
    const f = await FSW.stat("D:/DeepSeek Harness/" + j.output);
    if (!f.size) throw new Error("输出文件为空");
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
    const r = await request("/api/run", "POST", { tool: "normalize", params: { input: "integration-pack/reports/ui/不存在.csv" } });
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
    const rel = "integration-pack/reports/ui/2d 测试 输入.csv";
    await FSW.writeFile("D:/DeepSeek Harness/" + rel, "设备名称,数量\n泵 A,1\n", "utf8");
    const r = await request("/api/run", "POST", { tool: "normalize", params: { input: rel } });
    const j = JSON.parse(r.text);
    if (j.status !== "ok") throw new Error(`status=${j.status} ${(j.stderr || "").slice(0, 120)}`);
  });

  // ---- Phase 4：其余工具逐个接入验证 ----
  const qA = "integration-pack/reports/ui/4a-报价A.csv";
  const qB = "integration-pack/reports/ui/4a-报价B.csv";
  await FSW.writeFile("D:/DeepSeek Harness/" + qA, "设备名称,规格型号,单价\n潜污泵,Q=100,18500\n流量计,DN200,3200\n", "utf8");
  await FSW.writeFile("D:/DeepSeek Harness/" + qB, "设备名称,规格型号,单价\n潜污泵,Q=100,19800\n流量计,DN200,3000\n", "utf8");

  await check("4A compare 多文件比对 → ok + 输出", async () => {
    const r = await request("/api/run", "POST", { tool: "compare", params: { inputs: [qA, qB] } });
    const j = JSON.parse(r.text);
    if (j.status !== "ok") throw new Error(`status=${j.status} ${(j.stderr || "").slice(0, 150)}`);
    if (!j.output) throw new Error("缺少输出");
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
    const r = await request("/api/run", "POST", {
      tool: "dxf_parse",
      params: { dxf: "integration-pack/reports/smoke/测试PID.dxf" },
    });
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
    const r = await request("/api/file?path=" + encodeURIComponent("integration-pack/templates/投标报价表模板.xlsx"));
    const j = JSON.parse(r.text);
    if (!j.previewable || j.kind !== "table") throw new Error(JSON.stringify(j).slice(0, 140));
    if (!/Sheet/.test(j.content)) throw new Error("缺表格内容");
  });

  await check("4I docx 预览 → 段落文本", async () => {
    const r = await request("/api/file?path=" + encodeURIComponent("integration-pack/reports/ui/4i-test.docx"));
    const j = JSON.parse(r.text);
    if (!j.previewable) throw new Error(j.reason || "不可预览");
    if (!/预览测试/.test(j.content)) throw new Error("内容缺失");
  });

  await check("4J .doc 旧格式 → 明确提示不支持", async () => {
    await FSW.writeFile("D:/DeepSeek Harness/integration-pack/reports/ui/4j-old.doc", "fake doc", "utf8");
    const r = await request("/api/file?path=" + encodeURIComponent("integration-pack/reports/ui/4j-old.doc"));
    const j = JSON.parse(r.text);
    if (j.previewable) throw new Error("不应可预览");
    if (!/旧版 \.doc/.test(j.reason)) throw new Error(j.reason);
    await FSW.rm("D:/DeepSeek Harness/integration-pack/reports/ui/4j-old.doc", { force: true });
  });

  await check("4K md 预览带 kind=md 标记", async () => {
    const r = await request("/api/file?path=" + encodeURIComponent("integration-pack/docs/数据契约.md"));
    const j = JSON.parse(r.text);
    if (j.kind !== "md" || !j.previewable) throw new Error(JSON.stringify(j).slice(0, 140));
  });

  await check("4L workspace 默认返回工作区根", async () => {
    const r = await request("/api/workspace");
    const j = JSON.parse(r.text);
    if (!j.workspace) throw new Error("缺 workspace");
  });

  await check("4M workspace 更改生效 + 恢复", async () => {
    const r1 = await request("/api/workspace", "POST", { path: "D:/DeepSeek Harness/integration-pack/reports" });
    if (!JSON.parse(r1.text).ok) throw new Error("保存失败");
    const r2 = await request("/api/workspace");
    if (JSON.parse(r2.text).workspace !== "D:\\DeepSeek Harness\\integration-pack\\reports") {
      throw new Error("更改未生效");
    }
    const r3 = await request("/api/dirs?path=");
    if (!JSON.parse(r3.text).exists) throw new Error("新工作区未加入白名单");
    const r4 = await request("/api/workspace", "POST", { path: "D:/DeepSeek Harness" });
    if (!JSON.parse(r4.text).ok) throw new Error("恢复默认失败");
  });

  await check("4N workspace 不存在目录 → 400", async () => {
    const r = await request("/api/workspace", "POST", { path: "D:/不存在目录xyz123" });
    if (r.status !== 400) throw new Error(`status=${r.status}`);
  });

  await check("4O workspace 非字符串 → 400", async () => {
    const r = await request("/api/workspace", "POST", { path: 123 });
    if (r.status !== 400) throw new Error(`status=${r.status}`);
  });

  // 清理 Phase 4 测试产物
  for (const f of ["4a-报价A.csv", "4a-报价B.csv"]) {
    await FSW.rm("D:/DeepSeek Harness/integration-pack/reports/ui/" + f, { force: true });
  }

  // 清理 2D 测试产物
  for (const f of ["2d-test-input.csv", "2d-test-empty.csv", "2d-test-bad.txt", "2d-test-big.csv", "2d 测试 输入.csv"]) {
    await FSW.rm(UI_REPORT + "/" + f, { force: true });
  }
  const uiFiles = await FSW.readdir(UI_REPORT);
  for (const f of uiFiles) {
    if (f.startsWith("normalize_")) await FSW.rm(UI_REPORT + "/" + f, { force: true });
  }

  console.log(`\n结果：${passed} 通过 / ${failed} 失败`);
  process.exit(failed > 0 ? 1 : 0);
}

main();
