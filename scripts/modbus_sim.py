# -*- coding: utf-8 -*-
"""
modbus_sim.py —— Modbus TCP 从站仿真（联调用 POC）

模拟一台仪表/PLC 从站，供主站（PLC / 上位机 / 组态软件）联调：
- 保持寄存器（功能码 03/06/16）模拟仪表测量值，如流量、液位、pH、DO
- 线圈（01/05/15）模拟设备状态

用法示例（模拟 pH 计，地址 1，端口 1502，寄存器 40001 起）：
    py -3 modbus_sim.py --port 1502 --slave 1
    py -3 modbus_sim.py --port 1502 --values 40001=7.2,40002=250,40003=4.5
    py -3 modbus_sim.py --port 1502 --float32 40010=1.234,40012=56.7

运行时在控制台输入 "set 40001 8.0" 可修改寄存器值，Ctrl+C 退出。
"""
import argparse
import struct
import threading
import time

try:
    from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
    from pymodbus.server import StartTcpServer
except ImportError:
    print("缺少 pymodbus：py -3 -m pip install pymodbus")
    raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(description="Modbus TCP 从站仿真")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=1502)
    ap.add_argument("--slave", type=int, default=1)
    ap.add_argument("--values", default="",
                    help="保持寄存器初值，格式 40001=7.2,40002=250（整数）")
    ap.add_argument("--float32", default="",
                    help="32 位浮点初值（占 2 个寄存器），格式 40010=1.234")
    args = ap.parse_args()

    hr = [0] * 200
    for item in args.values.split(","):
        item = item.strip()
        if not item:
            continue
        addr, val = item.split("=")
        idx = int(addr.strip()) - 40001
        hr[idx] = int(float(val.strip()))
    for item in args.float32.split(","):
        item = item.strip()
        if not item:
            continue
        addr, val = item.split("=")
        idx = int(addr.strip()) - 40001
        raw = struct.unpack(">HH", struct.pack(">f", float(val.strip())))
        hr[idx], hr[idx + 1] = raw[0], raw[1]

    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0] * 100),
        co=ModbusSequentialDataBlock(0, [0] * 100),
        hr=ModbusSequentialDataBlock(0, hr),
        ir=ModbusSequentialDataBlock(0, [0] * 100),
    )
    context = ModbusServerContext(slaves={args.slave: store}, single=False)

    def console():
        while True:
            try:
                line = input()
            except (EOFError, KeyboardInterrupt):
                return
            line = line.strip()
            if not line:
                continue
            if line == "help":
                print("输入 set40001=8.0 修改保持寄存器；Ctrl+C 退出。")
            elif "=" in line:
                try:
                    addr, val = line.replace("set", "").strip().split("=")
                    idx = int(addr.strip()) - 40001
                    store.setValues(3, idx, [int(float(val.strip()))])
                    print(f"寄存器 {addr.strip()} → {val.strip()}")
                except Exception as e:
                    print("解析失败（格式：set40001=8.0）：", e)

    t = threading.Thread(target=console, daemon=True)
    t.start()

    print(f"Modbus TCP 从站已启动  从站地址={args.slave}  {args.host}:{args.port}")
    print("保持寄存器(40001 起)可读写；输入 'set40001=8.0' 修改值，Ctrl+C 退出。")
    StartTcpServer(context=context, address=(args.host, args.port))


if __name__ == "__main__":
    main()
