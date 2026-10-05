# 更新日志

本整合包遵循[语义化版本](https://semver.org/lang/zh-CN/)。

> 作者：moqsting（GitHub）

## 2.3.0（新增 5 个插件：计算 / CAD / WPS / Office / 电气）

### 变更

- **纳入 5 个插件**（全部 fork 到 `github:moqsting/<原名>`、做安全修复后以 git 40 位 SHA 坐标集成）：
  | 插件 | 上游 | fork SHA | 处置 |
  |---|---|---|---|
  | dsh-tool-calculator | omdsh-dev | `3a089c12` | 去官方 scope + peer 范围放宽 |
  | dsh-cad | LAU-MARS | `4fb02b02` | 移除 cad_script、写路径围栏、同源守卫 |
  | dsh-plugin-wps-office-next | sueecku | `57034cf5` | PDF 打开拦截、去逃生舱、confirm 闸门、真实探测（条件启用） |
  | dsh-office-toolkit | cnkids | `81454e1f` | add_image 崩溃修复 + 锁依赖 |
  | dsh-electro-lab | curtainsmall | `5a232e3e` | 同源守卫、输出路径越界、去外部求解器、cordis scope |
  为什么：扩展整合包能力（计算 / CAD 识图 / Office 读写 / WPS / 电气计算），均按安全审查结论 fork 修复（约束#3）。
  如何验证：各 fork 跑作者测试（calculator 31/31、cad 151/152、office 139/140 预存 1 失败、WPS 静态验证、electro-lab tsc+tsdown 构建通过）；`.dspack` 自检 30 项全过（含 5 个新插件 bundles/deps/顺序断言）。

## 2.2.2（环境页重写 + CAD 误判修复）

### 变更

- 随包插件升级到 `dsh-engineering-workbench` **1.1.2**（提交 `1c6a2347`）。
- **环境页整页重写为三态自检卡片**：状态用色块标签表达（正常 / 部分可用 / 不可用），每张卡给出关键值（Python 版本、依赖就绪状态、技能数、日报数）；CAD 一项单列整宽卡片，显示实际检测到的程序与目录、能力说明，并在不可用时列出可操作建议；右上角「重新检测」带检测中状态并显示上次检测时间。
  为什么：原页面把后端字段逐行拼成 `标签：✅/⚠️ 值` 的纯文本，既看不出严重程度，也没有下一步指引；CAD 能力缺失时尤其无从下手。
  配合改动：`/api/env` 的 `cad` 段补充 `autocad_version` / `autocad_dir` / `core_console` / `oda_dir` / `hints` 字段，供页面展示实际检测结果与建议。

### 修复

- **未安装 CAD 时，环境页 CAD 一项仍显示为正常（打勾）**。
  为什么：可用判据写成 `cad.dwg_to_dxf !== "unknown"`，而该字段的值是字符串（`none` / `autocad` / `autocad-acad` / `oda`）——`"none"`（完全没装）也是非空字符串、恒为真值，于是恒判定为正常。
  修复：改为显式三态判定——`autocad` / `oda` 为正常，`autocad-acad` 为部分可用（仅有 acad.exe、缺核心控制台），`none` 为不可用，`unknown` 为未检测。`server.py` 侧同步把判据所需的原始字段完整透传，不再简化。
  如何验证：测试套件新增断言，锁死 `dwg_to_dxf` 的取值域、`has_autocad`/`has_oda`/`core_console` 的布尔类型，并校验"声明可转换"必须与"实际检测到程序"一致；**46/46 通过**。本机实测 `dwg_to_dxf="none"` 现判为「不可用」并列出三条建议。

## 2.2.1（资源页修复）

### 变更

- 随包插件升级到 `dsh-engineering-workbench` **1.1.1**（提交 `65655d33`），修复资源页。

### 修复

- **资源页无法打开文件预览、显示方式与文件页不一致**：该页原为纯文本清单（每行渲染成 `@pack/… — 名称 备注`），行不可点击、无图标与悬停反馈，文件点不开，也看不出目录层级。
  为什么：该页当初按"信息清单"实现，只做展示，没有接入点击与预览链路。
  修复一（后端）：`/api/resources` 与 `/api/dirs` 返回的每一项新增 `abs` 字段（文件系统绝对路径）。`@pack/…` 只是后端寻址标识，直接当作 DSH 资源地址会被按会话相对路径解析，必然定位不到文件；DSH 原生预览要求绝对路径。
  修复二（前端）：资源页整函数重写——行渲染改用与文件页同一套样式（图标 + 名称 + 悬停高亮），目录行可点进入浏览（带「↑ 上级 / 刷新 / ← 快捷目录」导航与当前路径显示），文件行可点开 DSH 原生预览并显示文件大小。
  修复三（去重复）：列表行样式与"打开原生预览"函数抽为文件页与资源页共用（`ROW_STYLE` / `ROW_HOVER` / `openNativePreview`），避免两页再次各自分叉。
  如何验证：测试套件新增两条契约断言（`/api/resources` 与 `/api/dirs` 的每一项都必须给出绝对路径 `abs`），**45/45 通过**；插件仓库 `node --check src/client.js` 通过、单测 5/5、已发 v1.1.1。

### 测试

- `ui/tests/run_integration.ps1` 的「端口回退集成验证」改为容错：8618 可能已被其他进程占用（例如用户实例的工作台后端正在运行），此时原实现自建占位监听会因端口已占用而抛错，被误报成测试失败；现在检测到端口已被占用即跳过占位，直接验证回退结果。
  如何验证：在本机 8618 已被实例后端占用的前提下重跑，三步全过、输出「集成测试全部通过」。

## 2.2.0（工作台原生面板 + 离线依赖修复）

### 变更

- **工作台插件升级到 1.1.0**（提交 `0fe5b1ec`，插件仓库已发 v1.1.0）：UI 容器由第三方 better-sidebar Tab 改为 **DSH 原生主面板**——`main` slot 承载面板本体、`sidebar.panellist` slot 注册侧栏入口，与官方「插件」面板同机制、同渲染路径；侧栏图标移到顶部与「插件」并排，再次点击可折叠回对话；界面文案「工作区」全量改称「文件区」；文件预览改用 DSH 原生右侧栏文档预览。
  为什么：原方案依赖第三方插件的 Tab 容器，工作台不是 DSH 的一等界面且受其版本约束；「工作区」与 DSH 自身的会话工作区重名，易混淆。
  如何验证：整合包实例验收通过——插件模块内 `文件区=10`、`工作区=0`、`sidebar.panellist` 已注册；原生预览可用；插件仓库 `npm test` 5/5。
- **移除工作台的「打开位置」按钮与 `/api/workbench/reveal` 路由**（前端 `revealInExplorer`/`parentDirOf`、host 端 `revealInFileManager`/`describeSpawnError`/`describeExitCode` 一并删除）。
  为什么：该功能经 `explorer.exe` 调起系统文件管理器，在无交互式桌面会话的环境下进程可创建但窗口无法显示，且退出码不能反映窗口是否弹出（易误报成功）；DSH 原生预览面板已承担文件定位职责。
  如何验证：`/api/workbench/reveal` 返回 404；前端 bundle 中已无该按钮与相关函数。

### 修复

- **pydeps 归档名版本失配导致离线依赖全部不可用**：`ui/server.py` 原硬编码 `PYDEP_TARBALL = "pydeps-2.0.0.tar.gz"`，而 2.1.0 起实际发布的是 `pydeps-2.1.0.tar.gz`。导入布局下 pydeps 目录只放 tar.gz、需惰性解压，查找失败即返回不完整目录，`PYTHONPATH` 指向空目录，`openpyxl`/`pandas`/`ezdxf` 等全部 import 失败——报价归一、报价比对、成本测算、差异核对等 Excel 工具必然报错。
  为什么：归档名含整合包版本号，版本升级时未同步更新该常量。
  修复：整函数重写 `pydeps_dir()`，改为按 `pydeps-*.tar.gz` 模式发现归档（多份时取最近修改者），以解压出 `openpyxl` 为准，不再硬编码版本号。
  如何验证：导入布局实测 `openpyxl=True`；整合包实例 `/api/env` 由 `pydeps.ok=false（ModuleNotFoundError: No module named 'openpyxl'）` 变为 `pydeps.ok=true`。
- **环境页技能计数在导入布局恒为 0**：原用 `PACK_ROOT / "skills"` 统计，而导入布局下 `PACK_ROOT = <profile>/wta`、该目录不存在（技能实际落在 `$DSH_HOME/skills`，共 11 个），环境页恒显示「技能 0 个」。
  修复：新增 `skills_dir()`，按「开发落点 → 契约推导的导入落点（`PACK_ROOT` 上溯三级）→ `DSH_HOME` 兜底」顺序定位，且只接受确实含 `SKILL.md` 的目录。`DSH_HOME` 不作首选——它可能指向其它整合包的家目录（实测本机即指向 `better-deepseek-harness-codex`，会误取到 3 个技能）。
  如何验证：两种布局均计数 11；实例 `/api/env` 由 `skills=0` 变为 `skills=11`。

### 测试

- `ui/tests/test_server.mjs` **整文件重写为密闭测试**：整合包内资源一律用 `@pack/` 前缀寻址（原用例写相对路径 `integration-pack/...`，而按契约相对路径优先落在「文件区」，用户一旦配置过文件区即 19 项失败）；输出断言改为「`reports/ui` 目录新增文件」（`/api/run` 的 `output` 字段随文件区配置在相对/绝对之间漂移）；已移除的静态前端相应用例改为断言 404 契约。
  为什么：原用例依赖本机「未配置文件区 + 手工遗留夹具」的理想状态，换机器即红，不能作为验收依据。
  如何验证：在**保留用户已配置文件区**的前提下 **43/43 通过**（改前 20/43）；测试不再改写用户文件区配置（原 4M 用例会把配置改成 `D:/DeepSeek Harness`，属破坏性副作用），并自动清理本次产生的输出文件。
- `ui/tests/test_safety.py`：4 个用例改为断言契约（`active_workspace()`、`@pack/`）而非默认值常量，**13/13 通过**。
- 新增 `ui/tests/make_fixtures.py`：按需生成 docx 预览夹具（原用例依赖手工遗留的 `reports/ui/4i-test.docx`，清空 `reports` 后即失败）。
- `ui/tests/run_integration.ps1`：补 **UTF-8 BOM**（原文件无 BOM，Windows PowerShell 5.1 会按系统 ANSI 读取，中文注释乱码并解析失败，目标机未装 pwsh 7 时无法运行）；夹具改用脚本文件调用（`py -3 -c "<含中文代码>"` 在 Windows 下经 ANSI 往返会触发 `NameError`）；设 `PYTHONIOENCODING=utf-8` 修正子进程中文日志乱码。
  如何验证：PowerShell 5.1 下 `-File` 完整跑通——「生成测试夹具」「端口回退集成验证」「HTTP 行为测试（43 项断言）」三步全过，输出「集成测试全部通过」。

## 2.1.0（工作台 UI 内嵌）

### 变更

- **工作台插件 UI 内嵌 DSH（`dsh-engineering-workbench` 1.0.0）**：侧边栏按钮不再 `window.open` 单开浏览器，改为 better-sidebar Tab 内嵌 5 页面（工具/文件/资源/设置/环境）；目录选择用插件自包含的 Node fs 目录浏览器（跨平台，不依赖本机 PowerShell / directoryPicker 后端）；host 加 `/api/workbench/proxy/*` 反向代理。
  为什么：可移植（不依赖本机环境）；对齐 DSH 内部 UI 规范（tender-workbench 同款 better-sidebar Tab）。
  如何验证：`0.2.0-rc.2_test` 单独测插件通过（Tab + 5 页面 + 目录浏览器）；插件仓库已发正式版 v1.0.0。
- **删除 server.py 旧前端 `static/`**：工作台 UI 内嵌 DSH 后，不再需要独立网页前端（`app.js`/`index.html`/`style.css`），保留全部 `/api/*` 后端。
  为什么：UI 单一化（只在 DSH 内），避免两套前端维护。
  如何验证：`server.py` 语法通过、`.dspack` 24 项自检通过、体积 116KB → 99KB。

## 2.0.0（契约重构）

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
- **文件区首次引导**：首次打开工作台弹出「选择文件区目录」对话框，支持**文件资源管理器**选择（`浏览…`）；选择后记录、实时同步到设置页，之后不再弹出。
- **设置页「更改」按钮**：随时通过资源管理器重新选择文件区；仅在已设定文件区时显示「打开」按钮。
- **后端资源清单 API**（`/api/resources`）：按整合包**实际内容**动态生成模板 / 参考数据 / 文档清单。

### 修复

- **文件区设置真实生效**：修复空路径被硬编码为整合包父目录的问题（此前「打开」与文件页始终指向开发目录），并移除硬编码默认文件区。
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
