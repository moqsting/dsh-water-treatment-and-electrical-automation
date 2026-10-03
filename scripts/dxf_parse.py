# -*- coding: utf-8 -*-
"""
dxf_parse.py —— DXF 图纸解析（水处理 PID / 电气图）

提取：设备位号（P-101 等）、仪表位号（FIT-101 等气泡圈）、文本标注，
按图例映射库（data/cad_legend.csv）归类，输出带置信度的 xlsx 清单。

用法：
    runpy.cmd dxf_parse.py <图纸.dxf> [--out 结果.xlsx] [--legend 图例.csv]

输出 xlsx 字段：位号/名称/类型/坐标X/坐标Y/图层/来源/置信度/复核标记
置信度规则：
    - INSERT 块 + ATTRIB 位号 + 图例映射命中        → 0.95
    - INSERT 块 + ATTRIB 位号，无图例映射           → 0.70（标注未知块名）
    - TEXT/MTEXT 匹配位号正则（如 P-101、FIT-101）  → 0.55（仅文本，无块结构）
"""
import argparse
import csv
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PACK_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEGEND = PACK_ROOT / "data" / "cad_legend.csv"

# 水处理行业位号惯例：设备前缀 + 仪表前缀
TAG_RE = re.compile(
    r"\b([A-Z]{1,3}[-_ ]?\d{2,5}[A-Za-z]?)\b"          # 通用位号：字母+数字
)
DEVICE_TAG_RE = re.compile(r"\b([PVAFMBT][- ]?\d{2,4}[A-Za-z]?)\b")   # 泵/阀/池/风机等设备
INSTR_TAG_RE = re.compile(
    r"\b((?:FIT|LIT|PIT|AIT|TIT|FE|LE|PE|AE|TE|LSH|LSL|PSH|FSH|"
    r"FT|LT|PT|AT|TT|FTE|LI|PI|AI|TI|FQI|FQ|PH|DO|MLSS|ORP|TU)[- ]?\d{2,4}[A-Za-z]?)\b"
)

# 常见图层关键字 → 类别
LAYER_CLASS = [
    ("设备", ("equip", "device", "pump", "blower", "equipment", "shebei")),
    ("仪表", ("instrument", "inst", "meter", "gauge", "yibiao", "instrumentation")),
    ("管线", ("pipe", "line", "pipeline", "guanxian")),
    ("电气", ("wire", "elec", "cable", "terminal", "dianqi", "power")),
    ("标注", ("text", "note", "label", "bz", "mark", "dim")),
]


def load_legend(path):
    """加载图例映射：block_name → (category, meaning)。CSV 列：block_name,category,meaning"""
    legend = {}
    if not path or not Path(path).exists():
        return legend
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("block_name") or "").strip().upper()
            if name:
                legend[name] = (
                    (row.get("category") or "未知").strip(),
                    (row.get("meaning") or "").strip(),
                )
    return legend


def layer_class_of(layer_name):
    low = (layer_name or "").lower()
    for cls, keys in LAYER_CLASS:
        if any(k in low for k in keys):
            return cls
    return "其他"


def parse(path, legend):
    import ezdxf

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    rows = []
    seen = set()

    # 1) 块引用 + 属性（位号最可靠来源）
    for ins in msp.query("INSERT"):
        block_name = ins.dxf.name
        attrs = {}
        for attrib in ins.attribs:
            attrs[(attrib.dxf.tag or "").upper()] = attrib.dxf.text or ""
        tag = ""
        for k in ("TAG", "TAGNO", "位号", "编号", "NO", "NAME"):
            if attrs.get(k):
                tag = attrs[k]
                break
        if not tag:
            # 块内无属性时，尝试块名本身匹配位号
            m = TAG_RE.search(block_name)
            tag = m.group(1) if m else block_name
        cat, meaning = legend.get(block_name.upper(), ("未知", ""))
        kind = None
        if cat != "未知":
            kind = cat
        elif INSTR_TAG_RE.match(tag):
            kind = "仪表"
        elif DEVICE_TAG_RE.match(tag):
            kind = "设备"
        key = (tag, block_name)
        if key in seen:
            continue
        seen.add(key)
        conf = 0.95 if cat != "未知" else 0.70
        rows.append({
            "位号": tag,
            "名称": meaning or block_name,
            "类型": kind or ("未知块名 " + block_name),
            "坐标X": round(ins.dxf.insert.x, 1),
            "坐标Y": round(ins.dxf.insert.y, 1),
            "图层": ins.dxf.layer,
            "来源": "块属性",
            "置信度": conf,
            "复核标记": "" if conf >= 0.8 else "⚠ 未知图例",
        })

    # 2) 独立文本位号（气泡圈/标注文本）
    for e in msp.query("TEXT MTEXT"):
        text = e.dxf.text if e.dxf.hasattr("text") else e.text
        text = (text or "").strip().replace("\n", " ")
        m = INSTR_TAG_RE.search(text) or DEVICE_TAG_RE.search(text)
        if not m:
            continue
        tag = m.group(1)
        key = (tag, "TEXT")
        if key in seen:
            continue
        seen.add(key)
        cls = layer_class_of(e.dxf.layer)
        rows.append({
            "位号": tag,
            "名称": text[:60],
            "类型": cls if cls in ("设备", "仪表") else "待定",
            "坐标X": round(e.dxf.insert.x, 1),
            "坐标Y": round(e.dxf.insert.y, 1),
            "图层": e.dxf.layer,
            "来源": "文本",
            "置信度": 0.55,
            "复核标记": "⚠ 仅文本",
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description="DXF 图纸解析 → 清单 xlsx")
    ap.add_argument("dxf", help="DXF 图纸路径")
    ap.add_argument("--out", default=None, help="输出 xlsx 路径（默认与图纸同名）")
    ap.add_argument("--legend", default=str(DEFAULT_LEGEND), help="图例映射 CSV")
    args = ap.parse_args()

    if not Path(args.dxf).exists():
        print(f"错误：文件不存在 {args.dxf}")
        sys.exit(1)

    legend = load_legend(args.legend)
    print(f"图例映射库：{len(legend)} 条（{args.legend}）")
    rows = parse(args.dxf, legend)
    print(f"提取条目：{len(rows)}")

    out = Path(args.out) if args.out else Path(args.dxf).with_suffix(".清单.xlsx")

    try:
        import openpyxl
    except ImportError:
        print("缺少 openpyxl，仅打印前 20 条：")
        for r in rows[:20]:
            print(r)
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "提取清单"
    headers = ["位号", "名称", "类型", "坐标X", "坐标Y", "图层", "来源", "置信度", "复核标记"]
    ws.append(headers)
    for r in rows:
        ws.append([r[h] for h in headers])
    wb.save(out)
    print(f"已输出：{out}")
    print("提醒：本结果为初稿，请人工复核（⚠ 标记项优先）。")


if __name__ == "__main__":
    main()
