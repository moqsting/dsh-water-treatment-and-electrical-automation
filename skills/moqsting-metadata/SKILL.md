---
name: moqsting-metadata
description: "作者元数据与文件信任标注：为生成/交付的文件标注作者 moqsting，并解除 Windows“不受信任的来源”标记（Zone.Identifier）。触发：创建/生成文档、报告、配置文件，或文件提示不受信任。"
---
# 作者元数据与文件信任标注

## 触发场景
- 生成 .md、.json、.py、.yaml、.cmd 等交付文件
- 文件用记事本/Office 打开提示“不受信任的来源”或“此文件来自其他计算机”
- 为 moqsting 的项目补全作者、版权、来源信息

## 规则

### 1. 作者元数据（一律 moqsting）
- Markdown 文档：正文前写作者行，例如 `> 作者：moqsting（GitHub）`，或 frontmatter 加 `author: moqsting`；
- package.json / pack.json：`"author": "moqsting"`；
- Python/JS 等源码：文件头部注释标注 `# author: moqsting`（按语言用对应注释符）；
- LICENSE：`Copyright (c) <年份> moqsting`。

### 2. 解除“不受信任的来源”（Windows MotW）
“不受信任”的根因是 Windows 给文件附加了 **Zone.Identifier**（Mark of the Web，标记来源为互联网/其他计算机），**不是文件内容里的作者字段**。处理：
1. 检查标记：
   `Get-Item <文件> -Stream Zone.Identifier -ErrorAction SilentlyContinue`
   返回了内容 → 有标记；无输出 → 无标记。
2. 解除标记（按文件或目录递归）：
   `Unblock-File -Path <文件>`（单个）
   `Get-ChildItem <目录> -Recurse -File | Unblock-File`（批量）
3. 若当前环境禁止解除（受限沙箱），如实说明“需要完整权限”，不要改用其它方式绕过。

### 3. 配合
- 项目级惯例见 `moqsting-conventions` 技能；
- 中文回复规范见 `chinese-response` 技能；
- 修改任何文本文件遵守工作区编码铁律（UTF-8、用 read/edit/write 工具，禁用 shell 全文重写）。
