# 全局协作约定（water-treatment-and-electrical-automation）

本文件为整合包随附的全局指令，DSH 每次对话都会加载。约定如下：

## 1. 语言
- 思考过程与回复一律使用中文；仅保留常见英文词语与专业术语（如 token、agent、API、GUI、profile、bundle、manifest、plugin、skill、prompt、xlsx、PLC、PID、BOD、CAD、DXF、Modbus 等），代码、命令、路径、报错原文、URL、专有名词不翻译。
- 表述简洁克制、面向工程师。

## 2. 作者元数据
- 为 moqsting 的项目生成或交付文件时，作者一律标注 `moqsting`（GitHub 账号）：
  - Markdown：正文前 `> 作者：moqsting（GitHub）` 或 frontmatter `author: moqsting`；
  - package.json / pack.json：`"author": "moqsting"`；
  - LICENSE：`Copyright (c) <年份> moqsting`。

## 3. 文件信任与编码
- 生成新文件后，若其在 Windows 打开提示“不受信任的来源”，执行 `Unblock-File` 解除 Zone.Identifier 标记（受限环境则如实说明需要完整权限）。
- 修改任何文本文件遵守 UTF-8 编码铁律：用 read/edit/write 工具，禁止用 shell 做全文重写或批量字符替换。

## 4. 自动化任务与手动补救
- 凡是本应由自动化（脚本 / 工具 / 流程）完成的任务，若因故被手动完成，必须：
  1. 当场**做标记**（在产物、代码注释、日志或交付说明中明确注明「此步骤本应自动化、本次为手动完成」）；
  2. 在后续**补救**（把该手动步骤补进自动化脚本 / 流程，避免下次再手动重复）。
- 目的：不让「手动顶替自动化」悄悄变成长期惯例，也不让技术债无记录地累积。

## 5. 关联技能
- `chinese-response`：中文交流规范（本条约定第 1 项的展开）；
- `moqsting-metadata`：作者元数据与文件信任标注（第 2、3 项的展开）；
- `moqsting-conventions`：项目级惯例（命名、代理、GitHub 发布，若已安装）。
