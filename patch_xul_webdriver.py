#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
undetected-geckodriver-windows — патч WebDriver-флага в xul.dll / libxul.so

Убирает navigator.webdriver, обходя требование W3C, без инъекций JS и без
патчинга geckodriver. Selenium/Marionette продолжают работать.

Метод (идея взята из проектов, перечисленных в README):
    В бинарнике Gecko имя DOM-свойства лежит отдельной C-строкой в пуле строк:
        ... using_webdriver\\0 webdriver\\0 ...
    Переименовываем строку, сохраняя длину:
        ... using_webdriver\\0 webdrivXr\\0 ...
    WebIDL регистрирует свойство под новым именем, поэтому:
        navigator.webdriver        === undefined
        'webdriver' in navigator   === false

Проверено на:
    LibreWolf Portable 158.0.1 (Windows) + geckodriver 0.37 + selenium 4.49
    bot.sannysoft.com -> WebDriver (New): missing (passed)

Использование:
    python patch_xul_webdriver.py --check                 # авто-поиск бинарника
    python patch_xul_webdriver.py --check  <путь>
    python patch_xul_webdriver.py          <путь>         # пропатчить (+ бэкап)
    python patch_xul_webdriver.py --restore <путь>        # откатить
    python patch_xul_webdriver.py --browser-dir "C:/Program Files/LibreWolf"

Требования: только стандартная библиотека Python 3.8+.
Лицензия: MIT (см. LICENSE).
"""
import argparse
import glob
import os
import shutil
import sys

# Отдельная NUL-терминированная C-строка "webdriver" в пуле строк Gecko.
# Требуемая длина замены — ровно 9 байт, чтобы не смещать оффсеты в секции.
SIGNATURE = b"\x00webdriver\x00"
REPLACEMENT = b"\x00webdrivXr\x00"

# Где искать бинарник, если путь не задан
SEARCH_NAMES = ("xul.dll", "libxul.so", "XUL")            # Windows / Linux / macOS
SEARCH_DIRS = (
    r"C:\Program Files\LibreWolf",
    r"C:\Program Files\Mozilla Firefox",
    r"C:\Program Files (x86)\Mozilla Firefox",
    "/usr/lib/librewolf",
    "/usr/lib/firefox",
    "/usr/lib64/librewolf",
    "/opt/firefox",
    "/opt/librewolf",
    "/Applications/Firefox.app/Contents/MacOS",
    "/Applications/LibreWolf.app/Contents/MacOS",
)
BROWSER_EXES = ("librewolf.exe", "firefox.exe", "firefox", "librewolf")


def die(msg):
    print("ОШИБКА: " + msg)
    sys.exit(1)


def find_targets(browser_dir=None):
    """Возвращает список путей к бинарникам Gecko."""
    found = []
    dirs = [browser_dir] if browser_dir else list(SEARCH_DIRS)
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for name in SEARCH_NAMES:
            for path in glob.glob(os.path.join(d, "**", name), recursive=True):
                if os.path.isfile(path) and path not in found:
                    found.append(path)
    return found


def scan(path):
    """Возвращает (статус, оффсет, размер)."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        data = f.read()
    off = data.find(SIGNATURE)
    if off != -1:
        return "clean", off, size
    if REPLACEMENT in data:
        return "patched", -1, size
    return "notfound", -1, size


def browser_version(browser_dir):
    """Пытается прочитать версию из application.ini рядом с бинарником."""
    for pattern in ("application.ini", "**/application.ini", "platform.ini"):
        for ini in glob.glob(os.path.join(browser_dir, pattern), recursive=True):
            try:
                txt = open(ini, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            ver = None
            for line in txt.splitlines():
                if line.lower().startswith("version="):
                    ver = line.split("=", 1)[1].strip()
            if ver:
                return ver
    return None


def do_check(path, show_version=True):
    status, off, size = scan(path)
    print(f"файл:   {path}")
    print(f"размер: {size / 1024 / 1024:.1f} МБ")
    if show_version:
        ver = browser_version(os.path.dirname(path))
        if ver:
            print(f"версия: {ver}")
    if status == "clean":
        print(f"статус: НЕ пропатчен (сигнатура найдена по смещению {off})")
    elif status == "patched":
        print("статус: УЖЕ ПРОПАТЧЕН")
    else:
        print("статус: сигнатура не найдена — эта сборка не поддерживается")
        print("        (нужен Firefox/LibreWolf >= 157: там строка 'webdriver'")
        print("         хранится отдельно; в 156 и ниже её в бинарнике нет)")
    return status


def do_patch(path):
    status, off, size = scan(path)
    if status == "patched":
        print(f"{path}: уже пропатчен, ничего не делаю")
        return 0
    if status == "notfound":
        print(f"{path}: ОШИБКА — сигнатура не найдена (неподдерживаемая сборка)")
        return 1

    backup = path + ".orig"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print(f"бэкап:  {backup}")
    else:
        print(f"бэкап:  уже существует, не перезаписываю ({backup})")

    with open(path, "rb") as f:
        data = bytearray(f.read())
    data[off:off + len(SIGNATURE)] = REPLACEMENT

    try:
        with open(path, "wb") as f:
            f.write(data)
    except PermissionError:
        print("ОШИБКА: файл занят. Закрой браузер (все процессы) и повтори.")
        return 1
    print(f"патч:   'webdriver' -> 'webdrivXr' по смещению {off}")
    return 0


def do_restore(path):
    backup = path + ".orig"
    if not os.path.exists(backup):
        print(f"ОШИБКА: бэкап не найден: {backup}")
        return 1
    try:
        shutil.copy2(backup, path)
    except PermissionError:
        print("ОШИБКА: файл занят. Закрой браузер и повтори.")
        return 1
    print(f"восстановлено из {backup}")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Патч navigator.webdriver в бинарнике Gecko (xul.dll / libxul.so)")
    ap.add_argument("xul", nargs="?", help="путь к xul.dll / libxul.so")
    ap.add_argument("--browser-dir", help="каталог браузера (найдёт бинарник сам)")
    ap.add_argument("--check", action="store_true", help="только проверить статус")
    ap.add_argument("--restore", action="store_true", help="откатить из .orig")
    ap.add_argument("--list", action="store_true", help="показать найденные сборки")
    a = ap.parse_args()

    targets = [a.xul] if a.xul else find_targets(a.browser_dir)

    if a.list:
        if not targets:
            die("ничего не найдено — укажи путь явно")
        for t in targets:
            st, _, size = scan(t)
            print(f"[{st:8}] {size / 1024 / 1024:7.1f} МБ  {t}")
        return 0

    if not targets:
        die("бинарник Gecko не найден. Укажи путь аргументом или через --browser-dir")

    rc = 0
    for t in targets:
        if not os.path.isfile(t):
            die(f"файл не найден: {t}")
        print("-" * 70)
        if a.check:
            do_check(t)
        elif a.restore:
            rc |= do_restore(t)
        else:
            rc |= do_patch(t)
    return rc


if __name__ == "__main__":
    sys.exit(main())
