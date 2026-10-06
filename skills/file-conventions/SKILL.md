---
name: file-conventions
description: "文件规范：创建新文件后解除 Windows 不受信任标记、修改文本文件遵守 UTF-8 编码铁律。全局默认生效。"
---
本规范全局默认生效。

文件信任：生成新文件后，若其在 Windows 打开时提示“不受信任的来源”，执行 Unblock-File 解除 Zone.Identifier 标记；受限环境无法执行时，如实说明需要完整权限并请求授权。

编码铁律：修改任何文本文件（源码、JSON、YAML、Markdown、CSV、TXT 等）一律按 UTF-8 处理，优先用读取与编辑工具，禁止用 shell 做全文重写或批量字符替换。原因：Windows PowerShell 5.x 的 Get-Content、Set-Content、Out-File 与重定向默认按系统 ANSI 代码页（中文系统为 GBK）读写，会把 UTF-8 文件读成乱码再写回，永久损坏。万不得已必须用 shell 写文本文件时，显式指定 UTF-8：PowerShell 7 用 -Encoding utf8NoBOM，Windows PowerShell 5.1 用 [System.IO.File]::WriteAllText 配合 UTF8Encoding(false)；禁止裸 Set-Content、Out-File 或重定向。修改前先确认原文件的编码与 BOM 状态；读取工具对非 UTF-8 文件报 FS_NOT_TEXT 时，立即停止并向用户报告，不得用 shell 绕过。
