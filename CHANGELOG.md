# 更新日志

本整合包遵循[语义化版本](https://semver.org/lang/zh-CN/)。

> 作者：moqsting（GitHub）

## 2.0.0（契约重构，进行中，未发布）

### 变更

- **形态切换：dshhome → profile**（manifest v5 `type:"profile"`；机器文件 package.json 放 ZIP 根、`overrides/` 落 profile 根、`home/` 落 `$DSH_HOME`）。
  为什么：dshhome 形态下 DSHL 导入器未执行 profile 依赖重建（实测 `node_modules` 缺失）；profile 形态机器文件与导入流程对齐规范 pack-structure v3 §9.2。
  如何验证：`make-dspack.py` 20 项自检全过；待干净 profile 端到端验收。
- **插件 git 化**：侧边栏按钮插件迁至独立仓库 `moqsting/dsh-engineering-workbench`（原名 `dsh-water-treatment-engineering`），依赖坐标改为 git commit sha（`github:moqsting/dsh-engineering-workbench` → `86b65368…`）。
  为什么：原 `file:open-workbench` 坐标不在 manifest v5 契约内（契约只认 npm 精确版本 / git commit sha）；插件名从 `dsh-water-treatment-engineering` 改为 `dsh-engineering-workbench`。
  如何验证：插件仓库单元测试 5/5 通过；模拟导入 `pnpm install` 拉取 git 依赖成功、`--dump-config` 确认 bundle 被 DSH 加载。
- **纳入 4 个外来插件 + 官方导入器（npm 精确版本，放弃 git+vendored）**：`@michengai/dsh-skills-manager`、`@michengai/dsh-automation`、`dshmarket`、`dsh-bottom-info-bar` 与官方 `@dsh-packforge/dsh-pack-plugin`(0.3.5) 作为 bundles+dependencies，用 npm 精确版本。
  为什么：实测这 5 个包均已发布到 npm registry；官方样例 `desktop-pack` 即用 npm 精确版本依赖（不打 vendored）；npm 发布包是已构建产物，install 不跑 prepare/build，故无需 git 源码 + vendored 预构建（之前 vendorize 预构建方案因此废弃）。
  如何验证：模拟规范导入 `pnpm install` 退出码 0、6 依赖 4.6s 装齐；`--dump-config` 6 个 bundle 全被 DSH 加载、无 skipped；peer 警告均为 DSH 内置包（`autoInstallPeers:false` 正确处理）。
- **纳入招投标工作台链路**：`dsh-tender-workbench`（git `21a6a85e`）+ `dsh-mcp-connector`（npm `0.2.66`）+ `dsh-better-sidebar`（npm `0.24.1`）。
  为什么：新增企查查 MCP 专项招标查询（找招标机会/拟建项目 + Excel/PDF 导出），与「招标与价格查询」技能互补；`dsh-tender-workbench` 0.6.1 未发 npm（npm 仅 0.5.11，面向 0.1.x 不可用），故用 git 坐标。
  如何验证：`pnpm-workspace.yaml` 加 allowBuilds 精确键放行其 prepare 构建；模拟导入 9 插件全装齐、`tender-workbench/lib` 产物生成、挂载顺序 `dsh-mcp-connector` 先于 `dsh-tender-workbench`（自检 24 项 PASS）。
- **机器文件新增 `pnpm-workspace.yaml`**（`nodeLinker: hoisted` + `autoInstallPeers: false`，对齐官方样例 desktop-pack）。
  为什么：peer 依赖（`@deepseek-ai/cordis`、`dsh-client-*` 等）由 DSH 内置 bundle 提供，不 pnpm 重复安装。
  如何验证：`pnpm peers check` 的 missing peer 均指向 DSH 内置包名；install 退出码 0。
- **移除 `setup/deploy-to-instance.py`**：旧 zip 路线的部署脚本（含硬编码本机 DSH 版本目录）。
  为什么：2.0.0 主交付为 profile 形态 `.dspack`（导入器负责依赖重建），该脚本及 `install.ps1` 中的手动 pnpm 步骤已冗余。
  如何验证：`.dspack` 20 项自检通过；`install.ps1` 步骤 6→5、语法 0 错误。
- **插件路径解析重构**：删除 `findDshHome` 目录嗅探与 `workbench-path.json`，改用 `ctx.profileContext`（官方 `resolveRuntime` 契约）拿 profile 根。
  为什么：约束 1（路径由导入器解析，不在代码中硬编码）。
  如何验证：`runtime.js` 单测覆盖 profileContext 优先 + 环境变量兜底。
- **pydeps 指针化**：131 MB 离线依赖不再打进 `.dspack`，改走 manifest `files[]`（path+sha256+size+urls），`server.py` 增加 `pydeps_dir()` 惰性解压。
  为什么：约束 1 + 规范 v5 §8（重内容走 `files[]` 指针闭环）。
  如何验证：`.dspack` 体积 32.5 MB → 116 KB；`pydeps_dir()` 双布局冒烟通过。
- **11 个技能全部重写**：frontmatter（name+description 触发条件）+ 纯文本段落正文，无表格/加粗/多级标题，≤80 行，无硬编码路径。
  为什么：约束 5。
  如何验证：11/11 格式合规扫描通过。

## 2.1.0（工作台 UI 内嵌，进行中，未发布）

### 变更

- **工作台插件 UI 内嵌 DSH（`dsh-engineering-workbench` 1.0.0）**：侧边栏按钮不再 `window.open` 单开浏览器，改为 better-sidebar Tab 内嵌 5 页面（工具/文件/资源/设置/环境）；目录选择用插件自包含的 Node fs 目录浏览器（跨平台，不依赖本机 PowerShell / directoryPicker 后端）；host 加 `/api/workbench/proxy/*` 反向代理。
  为什么：可移植（不依赖本机环境）；对齐 DSH 内部 UI 规范（tender-workbench 同款 better-sidebar Tab）。
  如何验证：`0.2.0-rc.2_test` 单独测插件通过（Tab + 5 页面 + 目录浏览器）；插件仓库已发正式版 v1.0.0。
- **删除 server.py 旧前端 `static/`**：工作台 UI 内嵌 DSH 后，不再需要独立网页前端（`app.js`/`index.html`/`style.css`），保留全部 `/api/*` 后端。
  为什么：UI 单一化（只在 DSH 内），避免两套前端维护。
  如何验证：`server.py` 语法通过、`.dspack` 24 项自检通过、体积 116KB → 99KB。

## 1.2.1

### 变更

- **安装脚本 `setup\install.ps1` 补强**（让新机器部署更接近全自动）：
  - 检测到未安装 Python 3.12 时，可**用 `winget` 一键安装**（此前直接报错退出）；
  - 新增**侧边栏「工作台」按钮插件部署**步骤（此前脚本部署路线拿不到该按钮）；
  - 依赖步骤改为**包内已内置则跳过**（`pydeps\` 随包分发，无需再联网下载）；
  - 脚本改用 **UTF-8 with BOM**，修复 PowerShell 5.1 读取时中文乱码。
- `setup\deploy-to-instance.py` 默认 profile 由 `0.2.0-rc.2_test` 改为 `wet-automation`。
- `README.md` 更新：明确 **Python 3.12 为必装前置**；补齐 `.dspack` 一键导入路线；修正「不支持 DSHL 导入」的过时说明；技能数 9 → 11。

### 说明

- 本版本为**安装体验补强**，功能与 1.2.0 一致。

## 1.2.0

### 新增

- **侧边栏「工作台」按钮插件**（`plugins/open-workbench`）
  - DSH 侧边栏底部新增按钮，点击即可**启动/停止**本地工作台，无需命令行。
  - 按钮内右侧显示状态：`正在启动中` → `正在运行` → `正在关闭`（字号小于「工作台」）；关闭完成后自动关闭对应网页并清除状态字样。
  - **自动定位工作台**：按 `DSH_HOME` 环境变量，或从插件所在位置向上推导 `profiles` + `skills` 同时存在的目录，免配置路径文件。
  - **pythonw 自动探测**（配置 → 环境变量 → `%LOCALAPPDATA%\Programs\Python\*` → `py -3` 推导同目录），并**捕获 spawn 异常**——插件失败不再导致宿主 DSH 崩溃。
- **`.dspack` 自包含整合包**：技能 + 插件 + 完整工具链（工作台/脚本/模板/数据/文档）+ 离线依赖（`pydeps`）统一打进单个 `.dspack`，DSHL「手动安装整合包」一键导入即可用。
- **工作区首次引导**：首次打开工作台弹出「选择工作区目录」对话框，支持**文件资源管理器**选择（`浏览…`）；选择后记录、实时同步到设置页，之后不再弹出。
- **设置页「更改」按钮**：随时通过资源管理器重新选择工作区；仅在已设定工作区时显示「打开」按钮。
- **后端资源清单 API**（`/api/resources`）：按整合包**实际内容**动态生成模板 / 参考数据 / 文档清单。

### 修复

- **工作区设置真实生效**：修复空路径被硬编码为整合包父目录的问题（此前「打开」与文件页始终指向开发目录），并移除硬编码默认工作区。
- **资源 / 文档路径 404**：引入 `@pack/` 前缀统一表示整合包内路径，修复导入后布局（`$DSH_HOME/wta`）下所有模板、参考数据、文档「找不到指定的文件或目录」。
- **目录选择器弹出终端**：为目录选择子进程加 `CREATE_NO_WINDOW`，弹原生选择框时不再出现终端窗口。
- **前端路径硬编码治理**：快捷目录 / 资源页 / 文档入口全部改为后端动态清单，前端零路径假设（开发布局与导入后布局一致）。

### 变更

- 技能增至 **11 个**（新增 `chinese-response` 中文回复规范、`moqsting-metadata` 作者元数据）。
- `pack.json` 补充侧边栏插件、自包含 `.dspack` 等组件说明。

## 1.0.0

### 新增

- 首个版本：11 个对话技能、本地 Web 工作台（8 个工具一键运行）、Python 工具链、19 个固定版本离线依赖、5 个 Excel 模板、参考数据与规范清单、招标监控自动化脚本。
- 一键安装脚本（`setup/一键安装.cmd`、`setup/install.ps1`）与桌面快捷方式。
- 按 DSH-PackForge 规范（manifest v5 / pack-structure v3）生成 `.dspack`。
