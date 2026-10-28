# undetected-geckodriver-windows

[![tests](https://github.com/gotofuckinghell/undetected-geckodriver-windows/actions/workflows/tests.yml/badge.svg)](https://github.com/gotofuckinghell/undetected-geckodriver-windows/actions/workflows/tests.yml)

Патч бинарника Gecko (`xul.dll` / `libxul.so`), убирающий `navigator.webdriver` —
Windows-порт метода из проекта **undetected_geckodriver**. Без JS-инъекций, без
патчинга geckodriver, без внешних зависимостей. Selenium/Marionette продолжают работать.

> **Форк по методу, не по коду.** Здесь реализация с нуля на Python stdlib.
> Авторство самой техники принадлежит авторам, перечисленным в разделе
> [Credits](#credits) — см. также [Отказ от ответственности](#отказ-от-ответственности).

---

## Проблема

Firefox и LibreWolf под управлением Selenium (через Marionette/geckodriver) **обязаны**
отдавать `navigator.webdriver === true`. Это требование спецификации W3C WebDriver, а не
настройка:

* **Mozilla Bug 1632821** — префы `dom.webdriver.enabled` и `marionette.enabled`
  [удалены из Firefox](https://bugzilla.mozilla.org/show_bug.cgi?id=1632821). Свойство
  жёстко привязано к запущенному сервису Marionette, выключателя нет.
* **Mozilla Bug 1632556** — наоборот, требует, чтобы флаг *всегда* отражал состояние
  Marionette ([ссылка](https://bugzilla.mozilla.org/show_bug.cgi?id=1632556)).
* Запрос сообщества на опцию отключения отклонён:
  [geckodriver issue #1680](https://github.com/mozilla/geckodriver/issues/1680).

Следствие: `options.set_preference("dom.webdriver.enabled", ...)` в Selenium **не работает**
ни в каком значении, а `driver.execute_script("Object.defineProperty(...)")` срабатывает уже
после того, как страница прочитала флаг.

## Метод

В бинарнике Gecko имя DOM-свойства хранится отдельной NUL-терминированной C-строкой в пуле
строк WebIDL:

```
... using_webdriver\0 webdriver\0 ...
```

Патч переименовывает эту строку, **сохраняя длину** (9 байт), чтобы не смещать оффсеты
внутри секции:

```
... using_webdriver\0 webdrivXr\0 ...
```

WebIDL регистрирует свойство под новым именем, поэтому:

```js
navigator.webdriver         // undefined
'webdriver' in navigator    // false
```

Marionette при этом не затронут — управление браузером из Selenium работает как обычно.

Ключевая деталь под Windows: в сборках **156 и ниже** отдельной строки `webdriver` в
`xul.dll` нет (встречается лишь внутри `using_webdriver` — это телеметрия). Начиная
примерно с **157** строка присутствует отдельно и патчится. Проверено на 158.0.1.

## Установка

Зависимостей нет — только Python 3.8+.

```bash
git clone https://github.com/gotofuckinghell/undetected-geckodriver-windows.git
cd undetected-geckodriver-windows
```

### Состав репозитория

```
patch_xul_webdriver.py    патчер (stdlib, без зависимостей)
verify_selenium.py        проверка результата в живом браузере
test_xul_patcher.py       22 теста (unittest)
vendor/                   точные копии трёх исходных проектов + PROVENANCE.md
```

`vendor/` содержит архивы оригиналов с зафиксированными коммитами — метод можно изучить и
воспроизвести, даже если GitHub недоступен. Подробности, SHA и лицензии:
[`vendor/PROVENANCE.md`](vendor/PROVENANCE.md).

## Использование

```bash
# посмотреть, что найдено в системе
python patch_xul_webdriver.py --list

# проверить статус (ничего не меняет)
python patch_xul_webdriver.py --check --browser-dir "C:/Program Files/LibreWolf"

# пропатчить (создаст xul.dll.orig; бэкап не перезаписывается)
python patch_xul_webdriver.py --browser-dir "C:/Program Files/LibreWolf"

# откатить
python patch_xul_webdriver.py --restore --browser-dir "C:/Program Files/LibreWolf"
```

> **Перед патчем закрой браузер полностью** — `xul.dll` занят, иначе `PermissionError`.
> Проверить: `tasklist | findstr librewolf`.

Автопоиск смотрит в типовые каталоги (`C:\Program Files\LibreWolf`,
`C:\Program Files\Mozilla Firefox`, `/usr/lib/firefox`, `/opt/librewolf`,
`/Applications/*.app/Contents/MacOS` и др.). Если браузер стоит нестандартно — путь
указывается явно:

```bash
python patch_xul_webdriver.py "D:/Portable/LibreWolf/xul.dll"
```

## Проверка

### Тесты

```bash
python -m unittest -v test_xul_patcher
```

14 тестов без внешних зависимостей: сигнатура и длина замены, `scan` (clean / patched /
notfound), побайтовый roundtrip patch→restore, идемпотентность повторного патча, отказ на
неподдерживаемой сборке (файл не портится), `restore` без бэкапа, неприкосновенность
`.orig`, чтение версии из `application.ini`, поиск бинарника, CLI-смоук.

### Прогон в браузере

```bash
python verify_selenium.py --browser-dir "C:/Program Files/LibreWolf"
```

Скрипт запускает браузер на пропатченном бинарнике, печатает отпечаток и прогоняет
`bot.sannysoft.com`. Ожидаемый вывод:

```
navigator.webdriver:  None
'webdriver' in nav:   False
свойства с 'driv':    ['webdrivXr']
```

### Результат реального прогона

LibreWolf Portable **158.0.1** (Windows) + geckodriver 0.37 + selenium 4.49,
`bot.sannysoft.com`:

```
WebDriver (New)                  => missing (passed)
WebDriver Advanced               => passed
Plugins Length                   => 5
Plugins is of type PluginArray   => passed
Languages                        => en-US
```

Плагины при этом **настоящие**, а не подделанные через `Object.defineProperty` —
в отличие от JS-обходов, здесь ничего не эмулируется на стороне страницы.

## Обновление браузера

Обновление LibreWolf/Firefox заменяет `xul.dll` — патч при этом **исчезает**, флаг
возвращается. Сам файл не портится: патчер либо находит сигнатуру и применяет патч, либо
отказывается, ничего не трогая.

После каждого обновления:

```bash
python patch_xul_webdriver.py --check --browser-dir "C:/Program Files/LibreWolf"
python patch_xul_webdriver.py --browser-dir "C:/Program Files/LibreWolf"   # если «НЕ пропатчен»
```

Что делает патчер сам:

* рядом с бэкапом пишет `xul.dll.orig.json` — версия приложения, размер, sha256;
* если версия браузера изменилась, а `xul.dll` чистый — **пересоздаёт бэкап** под новую
  версию (старый `.orig` от прежней сборки не годится);
* `--restore` **отказывается** восстанавливать бэкап от другой версии, потому что это
  смешало бы файлы разных сборок и сломало браузер. Обойти осознанно: `--force`.

## Ограничения

* **Только движок Gecko.** Chromium/Chrome решается штатным
  `--disable-blink-features=AutomationControlled` (без `--enable-automation`).
* **Firefox/LibreWolf ≥ 157.** В более старых сборках строки в бинарнике нет.
* **Не обходит всё подряд.** `webdriver` — лишь один сигнал. Остаются: headless-режим,
  WebGL-рендерер, тайминги, TLS-отпечаток, поведенческие факторы. Для Cloudflare/BotD
  одного патча недостаточно.
* **Ломается при обновлении браузера.** После апдейта `xul.dll` заменяется свежим —
  патч нужно применять заново (и сверять, что сигнатура на месте: `--check`).
* **Обратимо.** Оригинал сохраняется в `xul.dll.orig` и не перезаписывается, откат —
  `--restore`.
* **macOS**: `XUL` лежит внутри фреймворка; сигнатура не проверялась.

## Credits

Метод придуман не мной. Оригинальные проекты и их авторы:

* **[bytexenon/undetected_geckodriver](https://github.com/bytexenon/undetected_geckodriver)** —
  исходный проект: находит бинарник Firefox, копирует его и патчит, чтобы тот не выставлял
  `navigator.webdriver`. Идейная основа (Linux).
* **[luauminati/undetected_geckodriver](https://github.com/luauminati/undetected_geckodriver)** —
  зеркало того же проекта: на момент снятия копии HEAD совпадал с upstream байт в байт
  (коммит `38d863ed115b`), независимых правок кода нет.
* **[coleleavitt/undetected_geckodriver](https://github.com/coleleavitt/undetected_geckodriver)** —
  Rust-патчер, который прямо патчит `libxul`: ищет строку `webdriver` в бинарнике и заменяет
  байты. Именно из его подхода взят способ работы со строкой в пуле строк.

Точные копии всех трёх лежат в [`vendor/`](vendor/PROVENANCE.md) — с зафиксированными
коммитами, датами и лицензиями, чтобы метод можно было изучить и воспроизвести даже если
GitHub недоступен.

Вклад этого репозитория: адаптация под Windows (`xul.dll`), точная сигнатура
`\0webdriver\0` вместо широкого поиска (чтобы не задеть строку телеметрии
`using_webdriver`), сохранение длины замены, читаемое имя `webdrivXr` вместо случайных
байтов, реверсивный патч с бэкапом и проверка статуса.

## Отказ от ответственности

Инструмент предназначен для тестирования собственных сайтов, доступности и
исследовательских задач. Использование для обхода защит чужих сервисов может нарушать
их условия и законные требования. Ответственность за применение — на пользователе.

## Лицензия

MIT — см. [LICENSE](LICENSE). Условия MIT распространяются и на идеи, заимствованные из
перечисленных выше проектов; их собственные лицензии остаются в силе для их кода.
