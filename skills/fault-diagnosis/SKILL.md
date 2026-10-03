---
name: fault-diagnosis
description: "故障诊断纪律：五步法（Observation→Hypothesis→Verification→Action→Validation）、错误分类表、盲目重试限制、EPERM rename 专项排查。触发：工具错误、EPERM/EACCES/ENOENT、编码/语法/schema 错误、连续失败。"
---
# 故障诊断纪律（Observation → Hypothesis → Verification → Action → Validation）

## 触发场景
- 任何工具调用失败：FS_* 错误（EPERM/EACCES/ENOENT/FS_STALE_VERSION/FS_BUSY/FS_PERMISSION/FS_NOT_TEXT 等）
- 命令报错、HTTP 错误、编译/语法错误、依赖缺失、schema 校验失败
- 连续两次同样的失败

## 五步法（严格按序，不得跳步）
1. **Observation**：记录错误码、错误消息原文、失败调用、文件路径、时间。不得凭印象转述。
2. **Hypothesis**：可提假设，必须显式写 `Hypothesis:`，与事实分开，不得当事实陈述。
3. **Verification**：假设能用工具验证的先验证（Test-Path / 列目录 / Get-Process / 重读文件 / 检查残留 / job 列表），通过才行动。
4. **Action**：只执行与已验证假设对应的动作；未验证假设不得动手修改。
5. **Validation**：修复后立即验证并写明"是否被证明有效"。

## 错误分类表（观察时归类）
| 类别 | 典型信号 | 应对 |
|---|---|---|
| permission | EACCES/EPERM/EROFS、401/403 | 只读查权限后报告，禁止盲目重试 |
| file lock | EBUSY/ETXTBSY、共享冲突 | 提示用户关闭占用程序，不覆盖 |
| antivirus/security | 瞬时 EPERM、扫描延迟 | 只提示用户检查，不点名软件 |
| encoding | FS_NOT_TEXT、UnicodeDecodeError、乱码 | 停下报告，禁止 shell 重写 |
| network | ECONNREFUSED/ETIMEDOUT/TLS/5xx | 查连通性后限次重试（≤2） |
| dependency | ModuleNotFoundError、缺库 | 确认来源版本再装 |
| syntax | SyntaxError/IndentationError | 停下报告，不边修边猜 |
| input/schema | 参数校验、schema validation | 查参数格式后重试 |
| tool implementation | 工具崩溃/未实现 | 报告，不绕过工具 |
| model/API | LLM 流中断、截断 | 报告或请用户处理 |

## 铁律
1. **"重试后成功" ≠ 证明原因**——成功只是新观察，原假设仍未证实，除非有独立证据。
2. **盲目重试限制**：EPERM、EACCES、ENOENT、encoding、syntax、schema 错误禁止无变更重复同一操作；无变更最多重试 1 次；重试前必须有实质变更。
3. **外部环境软件**（防病毒/Windows Search/OneDrive/Git/IDE/同步工具）：只提示用户自行检查；禁止擅自停服务、改注册表/组策略、删索引/隔离区、改同步设置、kill 其他进程。
4. **不点名猜测具体软件**：无明确证据（如用户提供的事件日志）时，结论只能是"原因未证实"+ 证据清单 + 建议检查项。

## Windows EPERM rename 专项排查（按顺序，任一命中即停）
1. Harness 自身并发：本会话后台任务 / job 列表 / 其他 Agent 是否在写同一文件；
2. 目标是否已存在且为目录（或 staging 残留同名）；
3. 临时目录残留：`.<文件名>.<pid>.<uuid>.tmpdir` 模式（列目录可见）；
4. 文件/目录权限（只读 `Get-Acl`/`icacls`，不修改）；
5. 外部进程占用（只报告现象与建议）。

全部无证据 → 结论"原因未证实"，列出证据与建议检查项。

## 输出格式
故障处理的每步按 O/H/V/A/V 五段记录输出，供用户审查。向用户汇报的结论只允许两种状态："已验证"（附证据）或"未证实"（明确标注）。
