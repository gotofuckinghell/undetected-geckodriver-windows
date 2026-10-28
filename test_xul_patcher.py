#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты patch_xul_webdriver.py. Запуск: python -m unittest -v (или python test_xul_patcher.py)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import patch_xul_webdriver as P  # noqa: E402

PATCHER = os.path.join(HERE, "patch_xul_webdriver.py")


class PatcherTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="xulpatcher-test-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def make(self, data, name="xul.dll"):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def read(self, path):
        with open(path, "rb") as f:
            return f.read()

    # --- сигнатура и замена ---

    def test_replacement_keeps_length(self):
        """Длина замены обязана совпадать с сигнатурой, иначе поедут оффсеты."""
        self.assertEqual(len(P.SIGNATURE), len(P.REPLACEMENT))
        self.assertIn(b"webdriver", P.SIGNATURE)
        self.assertIn(b"webdrivXr", P.REPLACEMENT)

    # --- scan ---

    def test_scan_clean(self):
        p = self.make(b"HDR" + P.SIGNATURE + b"TAIL")
        status, off, size = P.scan(p)
        self.assertEqual(status, "clean")
        self.assertEqual(off, 3)
        self.assertEqual(size, 3 + len(P.SIGNATURE) + 4)

    def test_scan_patched(self):
        p = self.make(b"HDR" + P.REPLACEMENT + b"TAIL")
        self.assertEqual(P.scan(p)[0], "patched")

    def test_scan_notfound(self):
        p = self.make(b"no signature here" * 50)
        self.assertEqual(P.scan(p)[0], "notfound")

    # --- patch / restore ---

    def test_patch_then_restore_roundtrip(self):
        payload = b"HDR" + P.SIGNATURE + b"TAIL" * 10
        p = self.make(payload)

        self.assertEqual(P.do_patch(p), 0)
        patched = self.read(p)
        self.assertIn(b"\x00webdrivXr\x00", patched)
        self.assertNotIn(b"\x00webdriver\x00", patched)
        self.assertEqual(len(patched), len(payload), "размер не должен меняться")
        self.assertTrue(patched.startswith(b"HDR") and patched.endswith(payload[-8:]))
        self.assertTrue(os.path.exists(p + ".orig"))

        self.assertEqual(P.do_restore(p), 0)
        self.assertEqual(self.read(p), payload, "откат обязан быть побайтовым")

    def test_patch_is_idempotent(self):
        p = self.make(b"HDR" + P.SIGNATURE)
        self.assertEqual(P.do_patch(p), 0)
        once = self.read(p)
        self.assertEqual(P.do_patch(p), 0)
        self.assertEqual(self.read(p), once, "повторный патч не должен ничего менять")

    def test_patch_refuses_unsupported(self):
        p = self.make(b"nothing useful" * 20)
        self.assertEqual(P.do_patch(p), 1)
        self.assertFalse(os.path.exists(p + ".orig"))
        self.assertEqual(self.read(p), b"nothing useful" * 20, "файл не должен портиться")

    def test_restore_without_backup(self):
        p = self.make(P.SIGNATURE)
        self.assertEqual(P.do_restore(p), 1)

    def test_backup_not_overwritten(self):
        p = self.make(b"HDR" + P.SIGNATURE)
        original = self.read(p)
        P.do_patch(p)
        P.do_restore(p)
        content = self.read(p + ".orig")
        self.assertEqual(content, original)
        # правим .orig — повторный патч не должен его затереть
        with open(p + ".orig", "wb") as f:
            f.write(b"marker")
        self.assertEqual(P.do_patch(p), 0)
        self.assertEqual(self.read(p + ".orig"), b"marker")

    # --- версия и поиск ---

    def test_browser_version_from_ini(self):
        with open(os.path.join(self.dir, "application.ini"), "w", encoding="utf-8") as f:
            f.write("[App]\nName=LibreWolf\nVersion=158.0.1\n")
        self.assertEqual(P.browser_version(self.dir), "158.0.1")

    def test_browser_version_missing(self):
        self.assertIsNone(P.browser_version(self.dir))

    def test_find_targets_respects_dir(self):
        self.make(b"x", name="xul.dll")
        found = P.find_targets(self.dir)
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].endswith("xul.dll"))

    # --- CLI ---

    def cli(self, *args):
        r = subprocess.run([sys.executable, PATCHER, *args],
                           capture_output=True, text=True, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def test_cli_check_and_patch(self):
        p = self.make(b"HDR" + P.SIGNATURE)
        rc, out = self.cli("--check", p)
        self.assertEqual(rc, 0)
        self.assertIn("НЕ пропатчен", out)

        rc, out = self.cli(p)
        self.assertEqual(rc, 0)
        self.assertIn("webdrivXr", out)

        rc, out = self.cli("--check", p)
        self.assertIn("УЖЕ ПРОПАТЧЕН", out)

    def test_cli_missing_file(self):
        rc, out = self.cli("--check", os.path.join(self.dir, "absent.dll"))
        self.assertEqual(rc, 1)
        self.assertIn("не найден", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
