# PLUGINS — 23 плагина-источника, 46 типов

Каждый тип капчи в датасете воспроизводит капчу одного открытого Minecraft-плагина-антибота.
Ниже — полная таблица: плагин, платформа, лицензия апстрима, типы и режим реконструкции.

**Режимы:**

| Режим | Что это | Когда так бывает |
|---|---|---|
| `faithful` | построчная реализация по исходникам плагина | лицензия апстрима это разрешает |
| `clean-room` | алгоритм прочитан по исходникам, но код, имена и комментарии написаны заново | лицензия запрещает копирование, либо лицензии нет |
| `reconstructed` | плагина за капчей нет; стиль восстановлен по эталонным скриншотам | группа `GalleryCaptcha/*` |

## `dataset/out/` — 18 плагинов, 34 типа

Путь: `dataset/out/<owner>/<repo>/<тип>/NNN.png`.

| Плагин | Платформа | Лицензия | Типы | Режим |
|---|---|---|---|---|
| [LagBug/XProtect](https://github.com/LagBug/XProtect) | Bukkit/Spigot | MIT | `code` `color` `different` `drop` `equation` `gui` `jump` `map` `picture` `reverse` `slot` `sneak` | faithful |
| [jonesdevelopment/sonar](https://github.com/jonesdevelopment/sonar) | Velocity | GPL-3.0 | `standard` `complex` `legacy` | clean-room |
| [Archy-X/Krypton](https://github.com/Archy-X/Krypton) | Bukkit | нет | `map` `menu` | clean-room |
| [FeelingAlive0/AdvancedCaptcha](https://github.com/FeelingAlive0/AdvancedCaptcha) | Bukkit | MIT | `button` `math` | faithful |
| [jSdCool/minecaptcha](https://github.com/jSdCool/minecaptcha) | Fabric (серверный мод) | CC0-1.0 | `text` `image` | faithful |
| [Z4OLLIEZ4/reCaptcha](https://github.com/Z4OLLIEZ4/reCaptcha) | Bukkit | MIT | `captchasx` | faithful |
| [Joey61021/captcha](https://github.com/Joey61021/captcha) | Bukkit | MIT | `colorgui` | faithful |
| [laforetbrut/are-you-sure](https://github.com/laforetbrut/are-you-sure) | Forge + NeoForge (клиент) | MIT | `code` | faithful |
| [Mrbysco/Captcha](https://github.com/Mrbysco/Captcha) | Forge (сервер) | MIT | `math` | faithful |
| [Yukun99/Captchas](https://github.com/Yukun99/Captchas) | Bukkit | нет | `itemslot` | clean-room |
| [China2B2T/Captcha](https://github.com/China2B2T/Captcha) | Bukkit | GPL-3.0 | `wool` | clean-room |
| [InstantlyMoist/Captcha](https://github.com/InstantlyMoist/Captcha) | Bukkit/Spigot | MIT | `textcaptcha` | faithful |
| [JSH32/Minecaptcha](https://github.com/JSH32/Minecaptcha) | Bukkit | MIT | `map` | faithful |
| [haq/mapcha](https://github.com/haq/mapcha) | Bukkit | MIT | `map` | faithful |
| [just-captcha/ProstoCaptcha](https://github.com/just-captcha/ProstoCaptcha) | Velocity 3 | MIT | `map` | faithful |
| [irootdev/AnBot](https://github.com/irootdev/AnBot) | BungeeCord | GPL-3.0 | `captcha` | clean-room |
| [ringoame196-s-mcPlugin/ReproductionCAPTCHA](https://github.com/ringoame196-s-mcPlugin/ReproductionCAPTCHA) | Paper (Kotlin) | файла лицензии нет | `map` | clean-room |
| [n1zamu/NCaptcha](https://github.com/n1zamu/NCaptcha) | Bukkit | MIT | `anvil` | faithful |

## `dataset/out_ru/` — 5 источников, 12 типов

Путь: `dataset/out_ru/<Плагин>/<тип>/NNN.png`.

| Источник | Платформа | Лицензия | Типы | Режим |
|---|---|---|---|---|
| [Elytrium/LimboFilter](https://github.com/Elytrium/LimboFilter) | Velocity | AGPL-3.0 | `map` `symbols` `framed2x2` `framed3x3` | clean-room |
| `BotFilter` (Leymooo, BungeeCord) | BungeeCord | BSD с дополнительной оговоркой | `map` | clean-room |
| `CaptchaGUI` (Supl1n) | Bukkit | не указана | `clickblock` | clean-room |
| `CaptchaVerifyZ` | Bukkit | все права защищены (Modrinth: `LicenseRef-All-Rights-Reserved`) | `map` | clean-room, **проверено по пикселям** |
| группа `GalleryCaptcha/*` | — | — | `ru-numberword` `ru-numberword-caption` `ru-symbols` `ru-web` `ru-object-swatch` | reconstructed |

> Два разных плагина называются **Minecaptcha**: `JSH32/Minecaptcha` (пакет `riku32.captcha`) и
> `jSdCool/minecaptcha` (пакет `org.cbigames.captcha`). Это разные кодовые базы с разными
> платформами, их нельзя сливать.

## Итоги

| | |
|---|---|
| Всего источников | **23** (18 + 5) |
| Всего типов | **46** (34 + 12) |
| По режимам (типы) | 25 faithful · 16 clean-room · 5 reconstructed |
| По режимам (плагины) | 12 faithful · 10 clean-room · 1 reconstructed |
| Ссылка на исходник не найдена | только у группы `GalleryCaptcha/*` — помечена `reconstructed` |

Каждый тип в `labels.jsonl` несёт поле `source` — класс и метод апстрима, откуда взят алгоритм.
Аудит-тропа: `tools/audit_sources.py`. Выдуманных ссылок на исходники в проекте нет.

## Связанные документы

* Лицензии и что покрыто MIT — [`LICENSES.md`](LICENSES.md).
* Дефекты апстрима, которые воспроизводятся, а не чинятся — [`UPSTREAM_DEFECTS.md`](UPSTREAM_DEFECTS.md).
* Контракт данных — [`DATASET_FORMAT.md`](DATASET_FORMAT.md).
