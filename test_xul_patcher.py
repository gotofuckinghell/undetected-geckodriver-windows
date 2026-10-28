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

    # --- обновление браузера ---

    def set_version(self, ver):
        with open(os.path.join(self.dir, "application.ini"), "w", encoding="utf-8") as f:
            f.write("[App]\nName=LibreWolf\nVersion=%s\n" % ver)

    def test_meta_written_on_patch(self):
        self.set_version("158.0.1")
        p = self.make(b"HDR" + P.SIGNATURE)
        P.do_patch(p)
        self.assertTrue(os.path.exists(P.meta_path(p)), "meta-файл должен появиться")
        meta = P.read_meta(p)
        self.assertEqual(meta["app_version"], "158.0.1")
        self.assertEqual(meta["size"], os.path.getsize(p + ".orig"))
        self.assertEqual(len(meta["sha256"]), 64)

    def test_restore_refuses_on_version_mismatch(self):
        """Бэкап от 158 при браузере 159 — откат смешал бы версии."""
        self.set_version("158.0.1")
        p = self.make(b"HDR" + P.SIGNATURE)
        P.do_patch(p)
        self.set_version("159.0.1")           # браузер обновился
        self.assertEqual(P.do_restore(p), 1, "должен отказать")
        self.assertTrue(os.path.exists(p + ".orig"))

    def test_restore_force_bypasses_version_check(self):
        self.set_version("158.0.1")
        payload = b"HDR" + P.SIGNATURE
        p = self.make(payload)
        P.do_patch(p)
        self.set_version("159.0.1")
        self.assertEqual(P.do_restore(p, force=True), 0)
        self.assertEqual(self.read(p), payload)

    def test_restore_allowed_when_versions_match(self):
        self.set_version("158.0.1")
        payload = b"HDR" + P.SIGNATURE
        p = self.make(payload)
        P.do_patch(p)
        self.assertEqual(P.do_restore(p), 0)

    def test_backup_recreated_after_browser_update(self):
        """После обновления xul.dll чистый, а .orig — от старой версии: бэкап обновляется."""
        self.set_version("158.0.1")
        p = self.make(b"OLD158" + P.SIGNATURE)
        P.do_patch(p)
        self.assertEqual(P.read_meta(p)["app_version"], "158.0.1")

        # имитация обновления: новый чистый бинарник + новая версия в ini
        with open(p, "wb") as f:
            f.write(b"NEW159" + P.SIGNATURE)
        self.set_version("159.0.1")

        self.assertEqual(P.do_patch(p), 0)
        self.assertTrue(self.read(p + ".orig").startswith(b"NEW159"),
                        "бэкап должен соответствовать новой версии")
        self.assertEqual(P.read_meta(p)["app_version"], "159.0.1")
        self.assertIn(b"\x00webdrivXr\x00", self.read(p))

    def test_cli_force_flag_exists(self):
        rc, out = self.cli("--help")
        self.assertEqual(rc, 0)
        self.assertIn("--force", out)

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

    def cli(self, *args, env=None):
        r = subprocess.run([sys.executable, PATCHER, *args],
                           capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace", env=env)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def cli_non_utf8(self, *args):
        """Запуск под консолью с чужой локалью — как на англоязычном Windows."""
        env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
        return self.cli(*args, env=env)

    def test_cli_survives_cp1252_console(self):
        p = self.make(b"HDR" + P.SIGNATURE)
        rc, out = self.cli_non_utf8("--check", p)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("UnicodeEncodeError", out)
        self.assertIn("НЕ пропатчен", out, "русский вывод должен доходить целиком")

    def test_cli_error_survives_cp1252_console(self):
        rc, out = self.cli_non_utf8("--check", os.path.join(self.dir, "absent.dll"))
        self.assertEqual(rc, 1, out)
        self.assertNotIn("UnicodeEncodeError", out)
        self.assertIn("не найден", out)

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
