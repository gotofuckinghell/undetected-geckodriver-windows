# Vendored sources / Архив источников

Эти каталоги — **точные копии сторонних репозиториев**, положенные сюда, чтобы метод
можно было изучить и воспроизвести без доступа к GitHub. Код в них **не мой**, он
принадлежит авторам, перечисленным ниже. Лицензии оригиналов сохранены в их каталогах.

Копии сняты 2026-10-28. Мой патчер (`patch_xul_webdriver.py` в корне репозитория) —
самостоятельная реализация; ничего из этих каталогов он не импортирует и не содержит.

## Что где лежит

| Каталог | Источник | Коммит | Дата коммита | Лицензия |
|---|---|---|---|---|
| `bytexenon/` | https://github.com/bytexenon/undetected_geckodriver | `38d863ed115b` | 2024-11-20 | MIT (файл `LICENSE`) |
| `luauminati/` | https://github.com/luauminati/undetected_geckodriver | `38d863ed115b` | 2024-11-20 | MIT (файл `LICENSE`) |
| `coleleavitt/` | https://github.com/coleleavitt/undetected_geckodriver | `4a5daed69d00` | 2025-04-07 | MIT (заявлена в `Cargo.toml` и README; **файла `LICENSE` в оригинале нет**) |

Полные SHA:

```
bytexenon  38d863ed115b…
luauminati 38d863ed115b…   (тот же коммит)
coleleavitt 4a5daed69d00…
```

Коммиты восстановить точечно:

```bash
git clone https://github.com/<owner>/undetected_geckodriver.git
git -C undetected_geckodriver checkout <sha>
```

## Важные уточнения

**`luauminati/undetected_geckodriver` — не независимый форк с новым кодом.** На момент
снятия копии его HEAD совпадает с `bytexenon` байт в байт (тот же коммит `38d863ed115b`,
идентичные `setup.py`, `requirements.txt`, `README.md`). В репозитории обновлены метаданные
GitHub, но код тот же. Если ищете актуальную реализацию — смотрите upstream `bytexenon`,
а `luauminati` считайте зеркалом.

**`coleleavitt/undetected_geckodriver`** — единственный из трёх, кто патчит бинарник
напрямую (Rust, `libxul.so`): ищет строку `webdriver` и заменяет байты. Именно этот подход
перенесён в мой патчер под Windows (`xul.dll`). Файла `LICENSE` в репозитории нет —
лицензия MIT объявлена только в `Cargo.toml` (`license = "MIT"`) и разделе License README.
Формально этого достаточно для MIT-совместимого использования, но при переиспользовании
кода стоит сослаться на автора и указать, что файл лицензии в оригинале отсутствует.

**Ни один из трёх не работает на Windows** в исходном виде: `bytexenon`/`luauminati`
подменяют бинарник Firefox на Linux-путях, `coleleavitt` патчит `libxul.so`. Мой патчер —
адаптация того же метода под `xul.dll`.

## Как собрать/воспроизвести без доступа к источнику

1. Мой патчер: зависимостей нет, нужен только Python 3.8+.
   ```bash
   python patch_xul_webdriver.py --check  --browser-dir "C:/Program Files/LibreWolf"
   python patch_xul_webdriver.py          --browser-dir "C:/Program Files/LibreWolf"
   ```
2. Тесты: `python -m unittest -v test_xul_patcher`
3. Проверка в браузере: `python verify_selenium.py --browser-dir "..."`
4. Изучить оригиналы: `vendor/bytexenon/undetected_geckodriver/`, `vendor/coleleavitt/src/main.rs`

## Лицензионная гигиена

Код в `vendor/` распространяется под MIT соответствующих авторов — файлы лицензий лежат
рядом с кодом (`vendor/bytexenon/LICENSE`, `vendor/luauminati/LICENSE`). Для
`vendor/coleleavitt/` файл лицензии отсутствовал в оригинале; текст MIT приведён в корневом
`LICENSE` этого репозитория и в `Cargo.toml` оригинала.

Если кто-то из авторов возражает против архивной копии — каталог будет удалён по первому
требованию.
