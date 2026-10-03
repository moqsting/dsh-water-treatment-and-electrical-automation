---
name: moqsting-metadata
description: "作者元数据与文件信任：为 moqsting 的项目生成或交付文件时标注作者、解除下载文件的信任标记。全局默认生效。"
---
本规范全局默认生效。为 moqsting 的项目生成或交付文件时，作者一律标注 moqsting（GitHub 账号）。Markdown 文件在正文前写作者行 moqsting（GitHub），或 frontmatter 写 author: moqsting。package.json 与 pack.json 写 author 字段 moqsting。LICENSE 写 Copyright (c) 年份 moqsting。

文件信任。生成新文件后，若其在 Windows 打开提示不受信任的来源，执行 Unblock-File 解除标记，受限环境则如实说明需要完整权限。修改任何文本文件遵守 UTF-8 编码铁律：用读取与编辑工具，禁止用 shell 做全文重写或批量字符替换。
