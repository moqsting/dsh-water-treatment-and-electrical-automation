# 导入整合包自动化（供 DSH 会话 Agent 执行）

> 目标机用户在 DSH 对话中说"**导入整合包自动化**"后，Agent 读取本文件并执行以下步骤。
> 本文件是"自动导入定时任务"的载体：Agent 用 `automation_create` 工具按下方定义创建即可，无需手工操作。

## 任务：创建招标监控定时任务

调用 `automation_create` 工具，参数如下：

- **name**：`水处理设备招标监控`
- **kind**：`daily`，**time**：`08:30`，**time_zone**：`Asia/Shanghai`
- **permission**：`workspace-write`（需要写 reports/tender 报告文件）
- **max_concurrent_runs**：`1`
- **prompt**（完整原文，不得改写）：

```
你是水处理设备招标信息监控员。每次运行独立执行以下任务：

1. 读取 <整合包根目录>\config\tender-keywords.txt 中的关键词（每组一行，最多 5 组，跳过 # 注释行）。
2. 用 web_search 按关键词检索最近 24~48 小时新增的招标/采购公告，公开源优先：中国政府采购网、中国招标投标公共服务平台、全国公共资源交易平台、各省公共资源交易中心。需会员才能查看的行业站点只提示入口。
3. 对每条检索结果提取：标题、发布日期、来源名称、链接。必须真实，禁止编造来源或链接。
4. 去重：读取 <整合包根目录>\reports\tender\seen.json（JSON 数组，存已收录的链接；文件不存在则视为空），跳过已收录链接。
5. 输出：把新增条目（最多 10 条）追加写入 <整合包根目录>\reports\tender\YYYY-MM-DD.md（当天日期），格式为 Markdown 摘要，每行一条：- [标题](链接) ｜ 来源 ｜ 发布日期。无新增时写入"今日无新增招标信息"。
6. 把本次新收录的链接合并写回 seen.json。
7. Token 控制（重要）：不做全文阅读、不展开详情、不跟踪页面内容，只输出摘要列表；单次结果不超过 10 条；查完即结束，不写长报告。
8. 报告路径不存在时先创建目录。
```

其中 `<整合包根目录>` 替换为用户放置整合包的实际绝对路径（例如 `D:\DeepSeek Harness\integration-pack`）。

## 创建后验证

1. `automation_list` 确认该任务状态为 active、下次运行时间为明天 08:30；
2. 建议立即 `automation_run_now` 试运行一次，检查 `reports\tender\` 生成报告与 seen.json；
3. 把"每日 08:30 自动运行、报告在 reports\tender"告知用户。

## 注意

- 若用户工作区中已存在同名自动化，先询问再处理，不覆盖；
- 关键词文件由用户自行维护（config\tender-keywords.txt，≤5 组，`#` 开头为注释）。
