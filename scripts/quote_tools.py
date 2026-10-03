# -*- coding: utf-8 -*-
"""
quote_tools.py —— 投标报价清单工具（解析 / 汇总比对 / 成本测算 / 差异核对）

数据契约（本文件顶部定义，入口统一校验）：
    normalize  输入: 表格(名称[required]; 规格/材质/单位/数量/备注[optional])
               输出: 设备表(序号/设备名称/规格型号/材质/单位/数量/备注) —— 无单价列
    compare    输入: 多张报价表(名称+单价[required]; 品牌/货期/质保[optional])
               输出: 比对表(供应商/设备名称/规格型号/品牌/单价/货期/质保/来源文件/异常标记)
    cost       输入: 含单价表(单价[required]; 数量/名称/规格/单位[optional])
               输出: 测算表(分项 sheet + 汇总 sheet)
    diff       输入: 两张表(名称[required]; 规格/数量[optional])
               输出: 差异报告(差异类型/条目)

串联规则（详见 docs/数据契约.md）：
    normalize → cost  ✗ 不可直连（normalize 输出无"单价"）
    compare  → cost  ✓ 可直连（比对表含单价；多供应商行需先筛选）
    normalize → diff  ✓（设备表可作为 diff 的任一输入）
    dxf_parse → *     ✗ 需人工整理（列名/语义不同）
"""
import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import openpyxl
    import pandas as pd
except ImportError:
    print("缺少依赖：请先运行 runpy.cmd bootstrap_libs.py")
    sys.exit(1)

# ────────────────────────── 数据契约定义 ──────────────────────────

class SchemaError(Exception):
    """数据契约错误：字段缺失 / 类型错误 / 空数据。消息按契约格式组织。"""


# 每个字段：规范名 → 可接受的列名别名
FIELD_ALIASES = {
    "名称": ["名称", "设备名称", "设备", "品名", "项目", "name", "item"],
    "规格": ["规格", "型号", "规格型号", "参数", "spec"],
    "材质": ["材质", "material"],
    "单位": ["单位", "unit"],
    "数量": ["数量", "quantity", "qty"],
    "备注": ["备注", "说明", "remark", "note"],
    "单价": ["单价", "价格", "报价", "含税", "成本", "price"],
    "品牌": ["品牌", "brand"],
    "货期": ["货期", "交期", "lead"],
    "质保": ["质保", "保修", "warranty"],
}

# 每个工具的 schema：required / optional / numeric（必须为数值的字段）
TOOL_SCHEMAS = {
    "normalize": {
        "required": ["名称"],
        "optional": ["规格", "材质", "单位", "数量", "备注"],
        "numeric": ["数量"],
    },
    "compare": {
        "required": ["名称", "单价"],
        "optional": ["规格", "品牌", "货期", "质保"],
        "numeric": ["单价"],
    },
    "cost": {
        "required": ["单价"],
        "optional": ["数量", "名称", "规格", "单位"],
        "numeric": ["单价", "数量"],
    },
    "diff": {
        "required": ["名称"],
        "optional": ["规格", "数量"],
        "numeric": ["数量"],
    },
}

# 串联建议（用于错误消息中的提示）
CONTRACT_HINTS = {
    "cost": "cost 需要单价列。可用 'compare' 的输出（比对表含单价）作为输入，"
            "或在设备表（normalize 输出）中人工填入单价后再运行。",
}


def _format_available(columns):
    return "、".join(str(c) for c in columns if str(c) not in ("", "None", "nan"))


def resolve_columns(df, tool, source):
    """按契约把列名映射到规范字段；返回 {规范字段: 实际列名}。违反契约抛 SchemaError。

    匹配规则：先精确相等，再子串包含（如"单价(含税)"匹配"单价"、"设备名称"匹配"名称"）。
    """
    spec = TOOL_SCHEMAS[tool]
    mapping = {}
    columns = [str(c) for c in df.columns]
    for field in spec["required"] + spec["optional"]:
        hit = None
        for alias in FIELD_ALIASES[field]:
            if alias in columns:
                hit = alias
                break
        if hit is None:
            for alias in FIELD_ALIASES[field]:
                for col in columns:
                    if alias in col or col in alias:
                        hit = col
                        break
                if hit is not None:
                    break
        if hit is not None:
            mapping[field] = hit
    missing = [f for f in spec["required"] if f not in mapping]
    if missing:
        lines = [
            "数据契约错误",
            f"Missing required field: {missing[0]}",
            f"Required by: {tool}",
            f"Available fields: {_format_available(df.columns)}",
        ]
        if tool in CONTRACT_HINTS:
            lines.append(f"提示: {CONTRACT_HINTS[tool]}")
        raise SchemaError("\n".join(lines))
    # 类型校验（required 与 optional 中的 numeric 字段，存在即校验）
    for field in spec["numeric"]:
        if field in mapping:
            try:
                pd.to_numeric(df[mapping[field]], errors="raise")
            except (ValueError, TypeError) as exc:
                raise SchemaError(
                    "数据契约错误\n"
                    f"字段类型错误: {field} 列 '{mapping[field]}' 含非数值内容\n"
                    f"Required by: {tool}\n"
                    f"来源: {source}\n"
                    f"原始错误: {exc}"
                ) from exc
    return mapping


def check_not_empty(df, tool, source):
    if df.dropna(how="all").empty:
        raise SchemaError(f"数据契约错误\n空数据: {source} 无数据行\nRequired by: {tool}")


def check_duplicate_keys(df, mapping, tool, source, allow_duplicates):
    """cost 语义保护：同一设备（名称+规格）多行会重复计价，默认拒绝。"""
    if allow_duplicates or tool != "cost":
        return
    key = df[mapping["名称"]].astype(str) if "名称" in mapping else None
    if key is None:
        return
    if "规格" in mapping:
        key = key + "|" + df[mapping["规格"]].astype(str)
    dup = key[key.duplicated()]
    if len(dup) > 0:
        raise SchemaError(
            "数据契约错误\n"
            f"重复条目: 同一设备出现多行（如 '{dup.iloc[0]}'），cost 会重复计价\n"
            f"Required by: cost\n"
            "建议: 先用 compare 比对并筛选供应商行，或人工合并同设备行\n"
            "如确认需要逐行计价，加 --allow-duplicates 显式放行"
        )


def _read_sheet(path):
    """读取输入表（xlsx/csv）为 DataFrame，自动定位 xlsx 表头行。"""
    p = Path(path)
    if not p.exists():
        raise SchemaError(f"数据契约错误\n文件不存在: {path}")
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p, encoding="utf-8-sig")
    wb = openpyxl.load_workbook(p, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header_idx = 0
    for i, row in enumerate(rows[:8]):
        if row and any(
            isinstance(c, str) and re.search(r"名称|设备|品名|项目|description|item", c, re.I)
            for c in row if c is not None
        ):
            header_idx = i
            break
    df = pd.DataFrame(rows[header_idx + 1:], columns=rows[header_idx])
    df = df.dropna(how="all").reset_index(drop=True)
    return df


# ────────────────────────── 子命令（业务逻辑保持不变） ──────────────────────────

def normalize(input_path, out_path):
    df = _read_sheet(input_path)
    check_not_empty(df, "normalize", input_path)
    m = resolve_columns(df, "normalize", input_path)
    result = pd.DataFrame({
        "序号": range(1, len(df) + 1),
        "设备名称": df[m["名称"]],
        "规格型号": df[m["规格"]] if "规格" in m else "",
        "材质": df[m["材质"]] if "材质" in m else "",
        "单位": df[m["单位"]] if "单位" in m else "台",
        "数量": pd.to_numeric(df[m["数量"]], errors="coerce").fillna(1) if "数量" in m else 1,
        "备注": df[m["备注"]] if "备注" in m else "",
    })
    result.to_excel(out_path, index=False)
    print(f"已规整 {len(result)} 行 → {out_path}")
    print("输出字段：序号/设备名称/规格型号/材质/单位/数量/备注（不含单价）。")
    print("注意：本输出不能直接作为 cost 的输入——请先询价填入单价，或用 compare 的输出。")


def compare(paths, out_path):
    frames = []
    for p in paths:
        df = _read_sheet(p)
        check_not_empty(df, "compare", p)
        m = resolve_columns(df, "compare", p)
        sup = Path(p).stem
        t = pd.DataFrame({
            "供应商": sup,
            "设备名称": df[m["名称"]],
            "规格型号": df[m["规格"]] if "规格" in m else "",
            "品牌": df[m["品牌"]] if "品牌" in m else "",
            "单价": pd.to_numeric(df[m["单价"]], errors="raise"),
            "货期": df[m["货期"]] if "货期" in m else "",
            "质保": df[m["质保"]] if "质保" in m else "",
            "来源文件": p,
        })
        frames.append(t)
    merged = pd.concat(frames, ignore_index=True)
    # 同参数归组，标记异常
    merged["归组键"] = merged["设备名称"].astype(str) + "|" + merged["规格型号"].astype(str)
    grp = merged.groupby("归组键")["单价"]
    merged["组内最低"] = grp.transform("min")
    merged["异常标记"] = merged.apply(
        lambda r: "⚠ 异常低价" if pd.notna(r["单价"]) and r["单价"] < r["组内最低"] * 1.1
        else ("⚠ 高于最低 30%+" if pd.notna(r["单价"]) and r["单价"] > r["组内最低"] * 1.3 else ""),
        axis=1,
    )
    merged.drop(columns=["归组键", "组内最低"]).to_excel(out_path, index=False)
    print(f"已比对 {len(paths)} 份报价、{len(merged)} 行 → {out_path}")
    print("输出字段：供应商/设备名称/规格型号/品牌/单价/货期/质保/来源文件/异常标记。")
    print("注意：同一设备多供应商会占多行；作为 cost 输入前请先筛选供应商行。")
    print("⚠ 标注行为参考，最终选型须结合货期/质保/资质人工决策。")


def cost(input_path, out_path, tax, freight, install, admin, profit, allow_duplicates=False):
    df = _read_sheet(input_path)
    check_not_empty(df, "cost", input_path)
    m = resolve_columns(df, "cost", input_path)
    check_duplicate_keys(df, m, "cost", input_path, allow_duplicates)
    base = pd.to_numeric(df[m["单价"]], errors="raise")
    qty = pd.to_numeric(df[m["数量"]], errors="raise") if "数量" in m else pd.Series(1, index=df.index)
    subtotal = base * qty
    total_base = subtotal.sum()
    freight_val = float(freight)
    install_val = total_base * float(install) / 100
    admin_val = (total_base + freight_val + install_val) * float(admin) / 100
    profit_val = (total_base + freight_val + install_val + admin_val) * float(profit) / 100
    untaxed = total_base + freight_val + install_val + admin_val + profit_val
    tax_val = untaxed * float(tax) / 100
    res = pd.DataFrame({
        "设备名称": df[m["名称"]] if "名称" in m else "",
        "规格型号": df[m["规格"]] if "规格" in m else "",
        "单位": df[m["单位"]] if "单位" in m else "台",
        "数量": qty,
        "单价(未税)": base,
        "小计": subtotal,
    })
    summary = pd.DataFrame({
        "项目": ["设备合计", "运费", "安装费", "管理费", "利润", "未税合计", f"税金({tax}%)", "含税总价"],
        "金额": [
            round(total_base, 2), round(freight_val, 2), round(install_val, 2),
            round(admin_val, 2), round(profit_val, 2), round(untaxed, 2),
            round(tax_val, 2), round(untaxed + tax_val, 2),
        ],
    })
    with pd.ExcelWriter(out_path) as xw:
        res.to_excel(xw, sheet_name="分项", index=False)
        summary.to_excel(xw, sheet_name="汇总", index=False)
    print(f"测算完成（含税总价 {round(untaxed + tax_val, 2)} 元）→ {out_path}")
    print("输出字段：分项 sheet(设备名称/规格型号/单位/数量/单价(未税)/小计) + 汇总 sheet(项目/金额)。")


def diff(tender_path, quote_path, out_path):
    td = _read_sheet(tender_path)
    qd = _read_sheet(quote_path)
    check_not_empty(td, "diff", tender_path)
    check_not_empty(qd, "diff", quote_path)
    mt = resolve_columns(td, "diff", tender_path)
    mq = resolve_columns(qd, "diff", quote_path)
    t_key = td[mt["名称"]].astype(str) + ("|" + td[mt["规格"]].astype(str) if "规格" in mt else "")
    q_key = qd[mq["名称"]].astype(str) + ("|" + qd[mq["规格"]].astype(str) if "规格" in mq else "")
    t_set, q_set = set(t_key), set(q_key)
    missing = sorted(t_set - q_set)
    extra = sorted(q_set - t_set)
    rows = [{"差异类型": "报价缺失（漏项）", "条目": x} for x in missing]
    rows += [{"差异类型": "报价多出（清单外）", "条目": x} for x in extra]
    if "数量" in mt and "数量" in mq:
        tq = td.set_index(t_key)[mt["数量"]]
        qq = qd.set_index(q_key)[mq["数量"]]
        for k in t_set & q_set:
            try:
                a = float(pd.to_numeric(tq[k], errors="raise"))
                b = float(pd.to_numeric(qq[k], errors="raise"))
                if abs(a - b) > 1e-6:
                    rows.append({"差异类型": f"数量差异(招标 {a:g} / 报价 {b:g})", "条目": k})
            except (ValueError, KeyError, TypeError):
                pass
    pd.DataFrame(rows).to_excel(out_path, index=False)
    print(f"差异报告：漏项 {len(missing)}、多出 {len(extra)}、数量差异 {len(rows) - len(missing) - len(extra)} → {out_path}")


def main():
    ap = argparse.ArgumentParser(description="投标报价清单工具（数据契约见文件头注释）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("normalize"); p1.add_argument("input"); p1.add_argument("--out", required=True)
    p2 = sub.add_parser("compare"); p2.add_argument("inputs", nargs="+"); p2.add_argument("--out", required=True)
    p3 = sub.add_parser("cost"); p3.add_argument("input"); p3.add_argument("--out", required=True)
    p3.add_argument("--tax", default=13); p3.add_argument("--freight", default=0)
    p3.add_argument("--install", default=0); p3.add_argument("--admin", default=5); p3.add_argument("--profit", default=8)
    p3.add_argument("--allow-duplicates", action="store_true", help="允许同一设备多行（默认拒绝，防重复计价）")
    p4 = sub.add_parser("diff"); p4.add_argument("tender"); p4.add_argument("quote"); p4.add_argument("--out", required=True)

    args = ap.parse_args()
    try:
        if args.cmd == "normalize":
            normalize(args.input, args.out)
        elif args.cmd == "compare":
            compare(args.inputs, args.out)
        elif args.cmd == "cost":
            cost(args.input, args.out, args.tax, args.freight, args.install, args.admin, args.profit, args.allow_duplicates)
        elif args.cmd == "diff":
            diff(args.tender, args.quote, args.out)
    except SchemaError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
