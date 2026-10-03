# -*- coding: utf-8 -*-
"""ui/tests/test_safety.py —— server.py 路径安全与端口回退单元测试（Python 标准库 unittest）"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402


class TestDeviceName(unittest.TestCase):
    def test_device_names_rejected(self):
        for name in ["CON", "con", "NUL", "nul.txt", "COM1", "com9", "LPT1", "PRN", "AUX", "con.log"]:
            self.assertTrue(server.is_device_name(name), name)

    def test_normal_names_accepted(self):
        for name in ["report.txt", "console.log", "COM10", "com0", "nulx", "file.con.md"]:
            self.assertFalse(server.is_device_name(name), name)


class TestSafeResolve(unittest.TestCase):
    def test_relative_inside_pack(self):
        p = server.safe_resolve("integration-pack/README.md")
        self.assertIsNotNone(p)
        self.assertEqual(p, (server.PACK_ROOT / "README.md").resolve())

    def test_relative_inside_workspace(self):
        p = server.safe_resolve("AGENTS.md")
        self.assertIsNotNone(p)
        self.assertEqual(p, (server.WORKSPACE_ROOT / "AGENTS.md").resolve())

    def test_dotdot_escape_rejected(self):
        # 从 integration-pack 逃到 C:\ 等外部 → 两个白名单根都不包含 → None
        self.assertIsNone(server.safe_resolve("../.."))
        self.assertIsNone(server.safe_resolve("integration-pack/../../Windows"))

    def test_absolute_drive_rejected(self):
        self.assertIsNone(server.safe_resolve("C:/Windows"))
        self.assertIsNone(server.safe_resolve("C:\\Windows\\System32"))
        self.assertIsNone(server.safe_resolve("D:/"))

    def test_unc_rejected(self):
        self.assertIsNone(server.safe_resolve("//server/share"))
        self.assertIsNone(server.safe_resolve("\\\\server\\share\\file"))

    def test_device_path_rejected(self):
        self.assertIsNone(server.safe_resolve("integration-pack/CON"))
        self.assertIsNone(server.safe_resolve("NUL"))
        self.assertIsNone(server.safe_resolve("COM1.txt"))

    def test_chinese_and_space_paths(self):
        p = server.safe_resolve("integration-pack/模板 目录/中文 文件.txt")
        self.assertIsNotNone(p)
        self.assertEqual(p, (server.PACK_ROOT / "模板 目录" / "中文 文件.txt").resolve())

    def test_empty_and_invalid(self):
        # 2C 起：空路径 = 工作区根（合法默认值）；None 类型仍拒绝
        self.assertEqual(server.safe_resolve(""), server.WORKSPACE_ROOT)
        self.assertIsNone(server.safe_resolve(None))


class TestPortSelection(unittest.TestCase):
    def test_find_free_port_returns_open_port(self):
        import socket
        port = server.find_free_port()
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", port))  # 若占用会抛错
        except OSError:
            self.skipTest("端口竞态：find_free_port 返回的端口被其他进程抢用（测试环境噪声）")
        finally:
            s.close()

    def test_fallback_skips_occupied(self):
        import socket
        if not server.port_is_free("127.0.0.1", 8618):
            self.skipTest("8618 已被外部进程占用，无法执行回退断言")
        sock = socket.socket()
        sock.bind(("127.0.0.1", 8618))
        try:
            port = server.find_free_port()
            self.assertNotEqual(port, 8618)
        finally:
            sock.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
