#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка результата патча через Selenium.

Запускает браузер на пропатченном бинарнике Gecko и печатает отпечаток,
плюс прогоняет bot.sannysoft.com, если доступен интернет.

Использование:
    python verify_selenium.py --browser-dir "C:/Program Files/LibreWolf"
    python verify_selenium.py --binary ".../librewolf.exe" --geckodriver ".../geckodriver.exe"
    python verify_selenium.py --url https://example.com/     # без sannysoft

Требуется: selenium 4.x и geckodriver в PATH либо указанный явно.
"""
import argparse
import os
import sys
import tempfile
import time

try:
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service
except ImportError:
    sys.exit("нужен selenium: pip install selenium")

BINARY_NAMES = ("librewolf.exe", "firefox.exe", "librewolf", "firefox")
DRIVER_NAMES = ("geckodriver.exe", "geckodriver")


def find_first(directory, names):
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if f.lower() in names:
                return os.path.join(root, f)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser-dir", help="каталог установки браузера")
    ap.add_argument("--binary", help="путь к librewolf.exe / firefox")
    ap.add_argument("--geckodriver", help="путь к geckodriver (иначе из PATH)")
    ap.add_argument("--url", default="https://bot.sannysoft.com/")
    ap.add_argument("--headless", action="store_true")
    a = ap.parse_args()

    binary = a.binary
    if not binary:
        if not a.browser_dir:
            sys.exit("укажи --binary или --browser-dir")
        binary = find_first(a.browser_dir, BINARY_NAMES)
        if not binary:
            sys.exit(f"браузер не найден в {a.browser_dir}")

    o = Options()
    o.binary_location = binary
    if a.headless:
        o.add_argument("-headless")
    profile = tempfile.mkdtemp(prefix="verify_gecko_")
    o.add_argument("-no-remote")
    o.add_argument("-profile")
    o.add_argument(profile)

    kwargs = {}
    if a.geckodriver:
        kwargs["service"] = Service(a.geckodriver)

    d = webdriver.Firefox(options=o, **kwargs)
    try:
        d.get("data:text/html,<script>window.__r={"
              "wd:navigator.webdriver,"
              "inNav:('webdriver' in navigator),"
              "keys:Object.getOwnPropertyNames(Navigator.prototype).filter(k=>/driv/i.test(k)),"
              "plugins:navigator.plugins.length,"
              "cores:navigator.hardwareConcurrency,"
              "langs:navigator.languages"
              "};</script>")
        time.sleep(1)
        r = d.execute_script("return window.__r;")

        print("=" * 60)
        print("браузер:             ", os.path.basename(binary))
        print("browserVersion:      ", d.capabilities.get("browserVersion"))
        print("=" * 60)
        print("navigator.webdriver: ", r["wd"])
        print("'webdriver' in nav:  ", r["inNav"])
        print("свойства с 'driv':   ", r["keys"])
        print("plugins:             ", r["plugins"])
        print("cores:               ", r["cores"])
        print("languages:           ", r["langs"])

        ok = (r["wd"] in (None, False)) and (r["inNav"] is False)
        print("=" * 60)
        print("РЕЗУЛЬТАТ:", "ПАТЧ РАБОТАЕТ" if ok else "ФЛАГ ВСЁ ЕЩЁ ВИДЕН")

        if "sannysoft" in a.url:
            print("\nпрогон", a.url)
            d.get(a.url)
            time.sleep(6)
            rows = d.execute_script("""
              return Array.from(document.querySelectorAll('table tr')).map(tr => {
                const c = tr.querySelectorAll('td');
                return c.length >= 2
                  ? (c[0].innerText.trim() + ' => ' + c[1].innerText.trim()).slice(0, 95)
                  : null;
              }).filter(Boolean);
            """)
            keys = ("webdriver", "plugins", "languages", "permissions", "webrtc", "headless")
            for row in rows:
                if any(k in row.lower() for k in keys):
                    print("  ", row)
        return 0 if ok else 2
    finally:
        d.quit()


if __name__ == "__main__":
    sys.exit(main())
