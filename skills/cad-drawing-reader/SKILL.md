# CAD 识图（水处理 PID / 电气图）

## 触发场景
- 从 DWG/DXF 图纸提取设备清单、仪表清单、IO 点
- 核对图纸与点表/清单一致性
- PDF 图纸内容提取

## 识图优先级（业内惯例）
1. **水处理 PID/P&ID**：设备位号（P-101 泵、V-101 阀门）、仪表位号（FIT/LIT/PIT/AIT 气泡圈）、管线介质/管径
2. **电气原理图/端子图**：元件编号、线号、端子号、电缆型号、I/O 地址
3. 总平面/布置图：辅助定位，不做深度解析

## 工具链（按顺序执行）
1. **环境探测**：`integration-pack\scripts\runpy.cmd integration-pack\scripts\cad_env.py` —— 自动查找 AutoCAD / ODA File Converter（注册表+常见路径），打印转换能力；找不到时给出安装指引
2. **DWG → DXF**：优先 AutoCAD 核心控制台（accoreconsole 无界面批量转换）；无 AutoCAD 用 ODA File Converter
3. **DXF 解析**：`integration-pack\scripts\runpy.cmd integration-pack\scripts\dxf_parse.py <图纸.dxf> --out <结果.xlsx>`
4. **OCR 兜底**：无任何转换工具时，图纸打开在屏幕上用 wincu OCR 截取识别；已装 modlens 插件可配合（视觉桥 OCR）

## 解析策略（dxf_parse.py 内置）
- 图层过滤：按常见图层名（设备/仪表/管道/TEXT/标注等）筛选
- 块解析：INSERT/ATTRIB → 位号 + 坐标
- 文本聚类：TEXT/MTEXT 就近归属到块/管线
- 图例映射：data\cad_legend.csv（块名 → 设备/仪表类型）；无映射的标注"未知块名 XXX"，建议人工补充图例库

## 输出规范
- xlsx 清单字段：位号 / 名称 / 类型 / 坐标 / 图层 / 置信度 / 复核标记
- 置信度 <0.8 或无图例映射的条目 → 复核列标 ⚠
- 交付声明：**初稿需人工复核**；标准图纸目标准确率 ≥80%（人工复核口径）

## 注意事项
- 识别率取决于图纸规范程度（图层/块命名）；乱图降级为 OCR + 人工
- 只读原图纸，绝不修改源文件
- 位号命名习惯：泵 P-、阀门 V-、仪表功能字母 F(流量)/L(液位)/P(压力)/A(分析)/T(温度)
