# water-treatment-and-electrical-automation —— 水处理与电气自动化工程师整合包

> 作者：moqsting（GitHub）｜ 仓库：https://github.com/moqsting/dsh-water-treatment-and-electrical-automation
> 版本 v2.0.0 ｜ 适用：DSH 0.2.0-rc.2 + Windows + **Python 3.12（含 `py` 启动器，必装前置）**
> 本手册面向第一次使用的工程师，按顺序读一遍即可上手。

---

## 一、这是什么

一个给水处理/电气自动化工程师用的 DSH 工作环境整合包，装好后**直接用中文对话**就能：

| 能力 | 一句话用法示例 |
|---|---|
| ① PLC 程序开发 | "给 1# 提升泵写电机启停程序（本地/远程/自动），信捷 XC 系列" |
| ② 投标报价清单 | "把这两份供应商报价和招标清单比对，算成本出报价表" |
| ③ 招标与价格查询 | "查一下潜污泵 Q=100m³/h 的近 90 天招标公告" |
| ④ CAD 识图 | "把这张 PID 图纸的设备位号和仪表位号提出来" |
| ⑤ 水处理工艺计算 | "算曝气需氧量：水量 1 万吨/天，进出水 BOD 250/20" |
| ⑥ 电气计算 | "校核 YJV 4×25 电缆带 90kW 电机 120 米压降够不够" |
| ⑦ 规范查询 | "GB 50014-2021 关于泵站集水池有效容积的条文" |

核心能力全部由整合包自带（技能 + Python 脚本 + 模板数据），**不依赖任何第三方插件**。

## 二、目录结构

```
water-treatment-and-electrical-automation\
├─ README.md                  ← 本手册
├─ CHANGELOG.md               更新日志
├─ pack.json                  整合包自述清单（名称/版本/组件）
├─ setup\                     部署与导入脚本
│   ├─ 一键安装.cmd           双击即装（自动探测 DSH 实例目录）
│   ├─ install.ps1            部署脚本（Python 检查/依赖/自检/技能/快捷方式）
│   ├─ make-dspack.py         生成 .dspack 整合包
│   └─ import-into-dsh.md     DSH 内导入招标监控自动化（对话说"导入整合包自动化"）
├─ ui\                        本地工作台（侧边栏按钮或双击桌面快捷方式打开）
│   ├─ start.cmd              启动入口（自动选端口 + 打开浏览器）
│   ├─ server.py              本地服务（仅监听 127.0.0.1）
│   ├─ static\                页面（工作台/工具/文件/资源/设置）
│   └─ tests\                 自动化测试
├─ skills\                    11 个技能（<名称>\SKILL.md 结构）
├─ scripts\                   Python 工具脚本（runpy.cmd 是统一入口）
├─ templates\                 5 个 Excel 模板（投标报价/IO点表/设备清单/电缆清册/调试记录）
├─ data\                      行业参考数据（图例库/载流量表/工艺参数/规范清单）
├─ config\                    招标关键词、来源清单、CAD 路径记忆
├─ reports\                   产出目录（招标日报、冒烟测试结果）
├─ pydeps\                    Python 依赖库（19 个包，离线内置）
├─ plugins\                   插件（open-workbench 侧边栏按钮；vendor\ 含可离线安装的 tgz）
├─ release\                   生成物（.dspack 整合包 + .sha256）
└─ docs\                      用户文档（数据契约）；dev\ 为开发者文档（基线/审查报告）
```

## 三、快速上手（第一次使用）

### 3.0 前置：Python 3.12（必装）

本整合包的工作台是 Python 程序，**目标机必须已安装 Python 3.12（安装时勾选 `py launcher`）**。包内**不包含** Python 解释器。

- 未安装时：`setup\一键安装.cmd` 会询问是否用 `winget` 自动安装；
- 手动安装：https://www.python.org/downloads/ （勾选 "Add python.exe to PATH" 与 "py launcher"）。

Python 库依赖（`pydeps\`，19 个包）已随包**离线内置**，无需联网。

### 3.1 路线 A：DSHL 一键导入（推荐，最省事）

把 **`release\water-treatment-and-electrical-automation-2.0.0.dspack`** 拖进 DSHL 的「手动安装整合包」入口即可。导入后自动就位：

- 11 个技能 + `AGENTS.md` → `$DSH_HOME`
- 工作台 + 工具链 + 离线依赖 → `$DSH_HOME\wta`
- 侧边栏「工作台」按钮插件 → 挂到 `wet-automation` profile

之后在 DSH 侧边栏点「工作台」按钮即可启动（首次会弹窗让你选择文件区目录）。

### 3.2 路线 B：脚本部署（解压 zip 后）

把整个整合包目录拷贝到目标机后，**双击 `setup\一键安装.cmd`**（自动探测 DSH 实例目录；探测不到会提示输入），或：
```
powershell -NoProfile -ExecutionPolicy Bypass -File setup\install.ps1
```
自动完成：Python 检查（缺失可 winget 引导安装）→ 离线依赖 → 整体自检 → 11 个技能安装 → 侧边栏插件部署 → 桌面快捷方式。
最后**在 DSH 对话中说"导入整合包自动化"**完成招标监控定时任务导入（详见 setup\import-into-dsh.md）。

### 3.3 手动部署（或检查环境）
- 命令行运行 `py -3 --version`，应显示 Python 3.12.x（Windows 自带的 py 启动器即可，不需要把 python 加进 PATH）。

### 3.4 依赖说明（通常无需操作）
依赖库已随包内置在 `pydeps\`（19 个固定版本包），**开箱即用、无需联网**。
仅当 `pydeps\` 缺失或损坏时，才需联网重建：
```
scripts\runpy.cmd scripts\bootstrap_libs.py
```
- 从清华镜像下载固定版本依赖到 `pydeps\`（openpyxl/pandas/ezdxf/pymodbus 等 19 个包）；看到 `完成：成功 19/19` 即成功。

### 3.5 冒烟测试（确认一切正常）
```
scripts\runpy.cmd scripts\smoke_test.py
```
- 自动生成测试图纸和报价表并跑通全部链路，产物在 `reports\smoke\`。
- 全部显示 `OK` 即就绪。

### 3.6 开始使用
- **对话式**：直接在 DSH 对话框里用中文提出任务即可（十一项技能，见第四节）；
- **工作台式**：点 DSH 侧边栏「工作台」按钮（或双击桌面快捷方式 / `ui\start.cmd`）打开本地工作台：8 个工具一键运行、文件浏览与预览（xlsx/docx/md/文本）、模板与数据直达、CAD 环境探测、招标报告查看、文件区路径可改（设置页）。

## 四、技能使用指南（11 个）

| 技能 | 触发关键词 | 你需要提供 | 你得到 |
|---|---|---|---|
| PLC 程序开发辅助 | 写程序、控制逻辑、功能块、点表生成程序 | 设备/回路、控制模式、联锁条件、PLC 品牌 | 文字逻辑 + ST 伪码 + 品牌代码 + 变量表 |
| 投标报价清单 | 报价、清单、比对、测算 | 招标清单 + 各供应商报价表（xlsx） | 统一设备表、比对表、测算表、差异报告 |
| 招标与价格查询 | 查价格、招标公告、中标结果 | 设备名 + 规格 + 地区 | 带来源链接与日期的汇总表 |
| CAD 识图 | 读图纸、提取位号、核对点表 | DWG/DXF 图纸路径 | 设备/仪表清单 xlsx（初稿+复核标记） |
| 水处理工艺计算 | 曝气量、加药量、污泥量、水力计算 | 水量、水质、工艺类型 | 含公式与取值依据的计算书 |
| 电气计算 | 载流量、压降、短路、整定 | 功率/电流、电缆长度、敷设条件 | 计算书 + 明确结论句 |
| 规范标准查询 | 规范、条文、GB 编号 | 规范名/主题 + 问题 | 条文摘录 + 版本 + 来源链接 |
| 打开工作台 | 打开工作台、启动工作台 | 无 | 启动本地 UI 并打开浏览器 |
| 故障诊断 | 工具报错、连续失败 | 错误现象 | 按五步法（观察→假设→验证→行动→复核）排查 |
| 中文回复规范 | 全程中文（默认生效） | — | 中文术语规范、代码/路径不翻译 |
| 文件规范 | 创建新文件、修改文本文件（默认生效） | — | 解除 Windows 不受信任标记、UTF-8 编码铁律 |

**使用纪律（重要）**：
- 报价、招标信息必须带来源链接与日期，DSH 查不到的会明说，不会编造。
- PLC 代码是辅助材料，**必须经编程软件（XDPPro/AutoShop/TIA Portal/GX Works）编译仿真验证**后才能上现场。
- CAD 提取结果是初稿，⚠ 标记项需人工复核。
- 计算结果按现行规范版本校核。

## 五、常用脚本速查

| 脚本 | 用途 | 示例 |
|---|---|---|
| `scripts\cad_env.py` | 探测 AutoCAD/ODA 并记忆路径 | `runpy.cmd scripts\cad_env.py` |
| `scripts\dxf_parse.py` | DXF 图纸提取清单 | `runpy.cmd scripts\dxf_parse.py 图纸.dxf --out 清单.xlsx` |
| `scripts\quote_tools.py normalize` | 招标清单规整 | `runpy.cmd scripts\quote_tools.py normalize 清单.xlsx --out 设备表.xlsx` |
| `scripts\quote_tools.py compare` | 多报价横向比对 | `runpy.cmd scripts\quote_tools.py compare A.xlsx B.xlsx --out 比对.xlsx` |
| `scripts\quote_tools.py cost` | 成本测算 | `runpy.cmd scripts\quote_tools.py cost 报价.xlsx --tax 13 --profit 8 --out 测算.xlsx` |
| `scripts\quote_tools.py diff` | 投标/报价差异核对 | `runpy.cmd scripts\quote_tools.py diff 招标.xlsx 报价.xlsx --out 差异.xlsx` |
| `scripts\modbus_sim.py` | Modbus TCP 从站仿真 | `runpy.cmd scripts\modbus_sim.py --port 1502 --values 40001=250` |
| `scripts\smoke_test.py` | 整体自检 | `runpy.cmd scripts\smoke_test.py` |

> 统一入口是 `scripts\runpy.cmd`，它会自动带上 `pydeps` 依赖目录，不用手动配环境变量。
>
> **工具间数据契约**（哪些可直接串联、哪些必须转换）见 `docs\数据契约.md`：
> - `normalize → cost` **不可直连**（normalize 输出无"单价"；工具会报 `Missing required field: 单价` 并给出建议）；
> - `compare → cost` 可直连（比对表含单价，多供应商行需先筛选）；
> - `dxf_parse` 输出需人工整理后才能进 `normalize`/`diff`。
> 所有工具入口做 schema 校验（字段缺失/类型错误/空数据都会给出明确的"数据契约错误"，不会抛底层 KeyError）。

## 六、招标监控自动化（A1）

**目标机导入**：在 DSH 对话中说"**导入整合包自动化**"，DSH 会按 `setup\import-into-dsh.md` 自动创建定时任务（每天 08:30，Asia/Shanghai），随后自动检索水处理设备招标信息，写入 `reports\tender\YYYY-MM-DD.md`（纯摘要，单次 ≤10 条，自动去重，控制 token 消耗）。

### 查看报告
- 打开 `integration-pack\reports\tender\` 目录下当天日期的 md 文件。

### 修改监控关键词
- 编辑 `integration-pack\config\tender-keywords.txt`，每组一行（最多 5 组），`#` 开头为注释。保存即生效。

### 随时开关（防 token 消耗，重要）
自动化名：`水处理设备招标监控`（导入后可在 DSH 自动化列表中看到）

| 操作 | 命令（在 DSH 中直接说） |
|---|---|
| 暂停监控 | "暂停水处理设备招标监控" |
| 恢复监控 | "恢复水处理设备招标监控" |
| 立即跑一次 | "立即运行水处理设备招标监控" |
| 彻底删除 | "删除水处理设备招标监控"（保留历史记录） |

### 数据来源（供查证）
完整清单见 `config\tender-sources.md`：中国政府采购网、中国招标投标公共服务平台、全国公共资源交易平台、各省公共资源交易中心（权威公开源）；1688/京东工业品/震坤行/西域等价格参考源。每条信息都会附来源链接与日期。

## 七、内置插件（2.0.0 起随包自动安装）

整合包通过 manifest 依赖声明，导入时由 DSHL 的规范导入器**自动 `pnpm install` 并挂载**以下插件，**无需任何手动操作**：

| 插件 | 版本/坐标 | 作用 |
|---|---|---|
| `dsh-engineering-workbench` | git `86b65368` | 侧边栏「工作台」按钮（一键启停本地工作台） |
| `dsh-tender-workbench` | git `21a6a85e` | 招投标工作台（企查查 MCP 查询 + Excel/PDF 导出） |
| `dsh-mcp-connector` | npm `0.2.66` | 企查查 MCP 连接器（提供 `mcp__qcc-tender__*` 查询工具） |
| `dsh-better-sidebar` | npm `0.24.1` | 可视化工作台 Tab 容器 |
| `@michengai/dsh-skills-manager` | npm `1.1.8` | 技能管理器 |
| `@michengai/dsh-automation` | npm `0.1.53` | 自动化 / 定时任务 |
| `dshmarket` | npm `1.66.8` | 插件市场浏览 |
| `dsh-bottom-info-bar` | npm `1.20.13` | 底部信息栏 |
| `@dsh-packforge/dsh-pack-plugin` | npm `0.3.5` | 官方整合包导入/导出器（DSH-PackForge 规范必备） |

**npm 版本认证**：上表 npm 坐标均为各包在 npm registry 的**精确发布版本**（可用 `pnpm view <包名> version` 核实，均已实测可装）；两个 git 坐标指向 `moqsting` 仓库的**固定 commit sha**（钉死，可复现）。

### 招投标工作台（dsh-tender-workbench）

- **定位**：与第 4 节「招标与价格查询」技能互补——技能走公开源 web 检索；本插件走**企查查 MCP** 专项查询（找招标机会 + 拟建项目），支持规则初筛、人工复核、Excel/PDF 导出。
- **首次授权**：企查查数据源用 **OAuth 2.0 PKCE 本机授权**（发行方 `https://agent.qcc.com`，scope `mcp:tools`）。**授权令牌只存你本机、由连接器自动刷新，整合包不含任何 Token/凭据**。
- **注意**：本插件只调用 `mcp__qcc-tender__search_tenders` 与 `mcp__qcc-tender__search_proposed_projects` 两个工具；真实查询额度与费用由你自己的企查查账号决定。

## 八、CAD 环境配置（重要）

1. **开发机（无 AutoCAD）**：识图前先跑 `runpy.cmd scripts\cad_env.py`，会给出安装指引（推荐免费 ODA File Converter）；无法转换时可把图纸打印成 PDF 用 OCR 兜底。
2. **目标机（装有 AutoCAD，路径未知）**：脚本会**自动查找**（注册表 + 常见路径）。若还是找不到：
   ```
   runpy.cmd scripts\cad_env.py --set-autocad "D:/Program Files/Autodesk/AutoCAD 2024"
   ```
   路径会记忆在 `config\cad_env.json`。
3. **整包迁移**：把整合包整个目录拷贝到目标机 → 跑 3.0 一键部署 → 配置 CAD 路径（工作台设置页有"重新探测"按钮）。

## 九、常见问题排查

| 现象 | 处理 |
|---|---|
| 脚本报"缺少 openpyxl" | 跑 3.2 重建依赖（`bootstrap_libs.py`） |
| 终端中文乱码 | 无碍使用；或用 Windows Terminal / VS Code 终端运行 |
| 图纸解析置信度低 | 正常。补图例：在 `data\cad_legend.csv` 加一行（块名,类别,含义），重跑解析 |
| 报价比对列错位 | 报价表表头需含"名称/规格/单价"等关键字；先看 `normalize` 输出再比对 |
| 插件安装失败 | 卸载（`dsh plugin remove <包名>`）并回退脚本路线；核心功能不受影响 |
| 自动化不想要了 | 见第六节开关表，暂停即可，随时可恢复 |

## 十、安全与数据边界（必读）

1. **报价/招标信息**：全部带来源链接与日期；价格是参考价，正式报价以供应商书面报价单为准。
2. **PLC 代码**：辅助生成，必须经编程软件编译仿真验证；保护信号必须硬接线+程序双保险。
3. **图纸**：整合包只读图纸，不修改源文件；提取结果为初稿，需人工复核。
4. **计算**：按现行规范版本校核，施工图设计以注册工程师复核为准。
5. **插件**：已做安全审查（无恶意代码），但第三方插件本质上是外部代码；建议只装需要的，装完看 `plugins\审查报告.md` 的注意事项。
6. **招标监控自动化**：只做公开信息检索与摘要，不涉及任何账号登录。

## 十一、维护与更新

- 扩充 CAD 图例库：编辑 `data\cad_legend.csv`
- 扩充参考参数：编辑 `data\water_params.csv`、`data\cable_ampacity.csv`、`data\standards_list.md`
- 更新监控关键词：编辑 `config\tender-keywords.txt`
- 依赖版本升级：编辑 `scripts\bootstrap_libs.py` 顶部 `PKGS` 列表后重跑
- 技能内容修改：编辑 `skills\*.md` 源文件后，对 DSH 说"更新技能 xxx"重新注册
