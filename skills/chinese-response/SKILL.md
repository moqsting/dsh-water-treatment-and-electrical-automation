---
name: chinese-response
description: "中文交流规范：思考过程与回复均使用中文，仅保留常见英文词语与专业术语（如 token、agent、API、xlsx、PLC）。触发：用户要求中文回复、默认交流语言、整理中文文档。"
---
# 中文交流规范

## 触发场景
- 用户使用中文提问、要求整理中文文档或报告
- 需要统一回复语言为中文

## 规则
1. **思考过程与最终回复一律使用中文**；不要在思考或输出里夹杂大段英文叙述。
2. **保留英文的例外**（这些照常使用，不翻译）：
   - 常见英文词：token、agent、API、GUI、CLI、profile、bundle、manifest、patch、plugin、skill、prompt、model、provider 等；
   - 专业术语与缩写：PLC、PID、BOD、COD、CAD、DXF、DWG、Modbus、xlsx、docx、pdf、YJV、GB/HG/CJ 等；
   - 代码、命令、文件路径、字段名、报错原文、URL、专有名词（GitHub、DSH、AutoCAD 等）。
3. **表述风格**：简洁、克制、面向工程师，不堆砌英文术语，能说人话的地方说人话。

## 注意
- 本规范与 moqsting-metadata（作者元数据）、moqsting-conventions（项目惯例）配合使用。
- 若用户明确要求用英文或其它语言，以用户当前指令为准。
