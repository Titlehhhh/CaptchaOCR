---
license: other
license_name: mixed-per-plugin-licences
tags:
- captcha
- ocr
- minecraft
- anti-bot
- synthetic
language:
- en
- ru
library_name: datasets
format: imagefolder
modality: image
size_categories: 10K<n<100K
---

# CaptchaOCR dataset — captchas of Minecraft anti-bot plugins, rendered

**46 captcha types · 23000 labelled PNG (500 per type) ·
23 upstream plugins · 218.2 МБ**

This repository holds the images and the labels of the CaptchaOCR captcha dataset: the
captchas that open-source Minecraft anti-bot plugins draw, re-rendered by **this project's own
generators**, with a machine-readable label for every image.

**Every PNG here is our own render** — 23000 images drawn by our Java generators.
No picture, page or answer taken from a third-party service is published here; the reference
screenshots of the upstream plugins stay in the project's working tree.

The dataset is published as **plain files** (PNG + `labels.jsonl`), not as a loading script:
every sample is a PNG next to a one-line JSON record, so any training loop can read it
without `datasets`, without a network round-trip and without trusting remote code.

## What is inside

| | |
|---|---|
| captcha types | **46** |
| labelled samples | **23000** |
| PNG files | **23000** |
| upstream plugins | **23** |
| trees | 2 |
| size of the PNG files | 218.2 МБ (228769043 B) |
| size of the whole repository (PNG + `labels.jsonl` + card) | ≈ 224.8 МБ |
| types with an answer band (`roi`) | 29 (rows with: 14499, without: 8501) |
| types where `text != answer` | 9 |
| reconstruction modes | faithful 25 · clean-room 16 · reconstructed 5 |
| combined alphabet size | 129 symbols |

### How this release was made

* **46 captcha types × 500 images = 23000 PNG.** Every type was
  re-rendered on **2026-10-22** on the author's machine with the project's **Java 21**
  generators (`dataset/generator` and `dataset/generator_ru`), then validated and uploaded.
* This dataset is a **machine artefact**. The generators are **not seeded**: the fonts are the
  same, but the samples themselves are random, so a re-render of the same type produces a
  *different* set of pictures. The images here are one particular render of 2026-10-22 — the
  generators and the labels are the reproducible part, the pixels are not.
* The reference screenshots of the upstream plugins (the `real_shots/` folders of the Russian
  tree — 517 reference screenshots, 523 files in total) are **not
  published here** — see *What is NOT published* below.

### Layout

```
data/<tree>/<...>/<type>/<file>
```

Concretely, the local generator tree `dataset` is uploaded as-is under `data/`:

* `data/<tree>/<...>/<type>/NNN.png` — the images,
* `data/<tree>/<...>/<type>/labels.jsonl` — the labels of that type,
* `README.md` — this card,
* `LICENSE` — the per-plugin licence breakdown of the data (the same table as below, plus what
  each licence means for you),
* `dataset_inventory.json` — the machine-readable summary of everything below,
* `.gitattributes` — the Git LFS rules for the binary files.

| дерево | типов | PNG | байт |
|---|---|---|---|
| `out` | 34 | 17000 | 167 МБ |
| `out_ru` | 12 | 6000 | 51.1 МБ |

## The label format

One JSON object per line, one line per image, UTF-8:

| field | meaning |
|---|---|
| `file` | PNG name in the same directory (`001.png` …) |
| `plugin` | upstream plugin the type came from |
| `captcha` | captcha type inside that plugin |
| `answer` | what the player has to type into the answer field |
| `text` | what is actually **drawn** on the picture (differs from `answer` in some types) |
| `prompt` | the task text as the plugin shows it |
| `roi` | the answer band `[x, y, w, h]`, or `null` if the answer is not in the frame |
| `width`, `height` | PNG size |
| `source` | where the type came from: upstream class and method (`file#method`) — the audit trail |

**`text` is the target for a recogniser, `answer` is the answer for a solver.** In the types
where they differ (Russian number words, arithmetic), the `text -> answer` conversion is a
separate step, not an OCR task.

**The band rule:** a band that does not fit into the frame is not a band; in that case
`roi` = `null`.

## The types

| тип | дерево | PNG | с полосой | алфавит | длина text (мин/мед/макс) | уник. ответов | лицензия |
|---|---|---|---|---|---|---|---|
| `out/Archy-X/Krypton/map` | out | 500 | 500/500 | латиница (62) | 5/5/5 | 500 | no licence (all rights reserved) |
| `out/Archy-X/Krypton/menu` | out | 500 | 0/500 | латиница+знаки (26) | 3/9/18 | 72 | no licence (all rights reserved) |
| `out/China2B2T/Captcha/wool` | out | 500 | 0/500 | латиница+знаки (7) | 9/9/9 | 1 | GPL-3.0 |
| `out/FeelingAlive0/AdvancedCaptcha/button` | out | 500 | 500/500 | латиница+пробел+знаки (29) | 18/24/28 | 220 | MIT |
| `out/FeelingAlive0/AdvancedCaptcha/math` | out | 500 | 500/500 | цифры+пробел+знаки (14) | 5/6/7 | 134 | MIT |
| `out/InstantlyMoist/Captcha/textcaptcha` | out | 500 | 0/500 | латиница (26) | 5/5/5 | 500 | MIT |
| `out/JSH32/Minecaptcha/map` | out | 500 | 500/500 | латиница (61) | 4/4/4 | 500 | MIT |
| `out/Joey61021/captcha/colorgui` | out | 500 | 500/500 | латиница (19) | 3/4/6 | 6 | MIT |
| `out/LagBug/XProtect/code` | out | 500 | 0/500 | латиница (62) | 6/6/6 | 500 | MIT |
| `out/LagBug/XProtect/color` | out | 500 | 0/500 | латиница+пробел (20) | 3/5/9 | 11 | MIT |
| `out/LagBug/XProtect/different` | out | 500 | 0/500 | латиница+знаки (11) | 13/13/13 | 1 | MIT |
| `out/LagBug/XProtect/drop` | out | 500 | 500/500 | латиница (4) | 4/4/4 | 1 | MIT |
| `out/LagBug/XProtect/equation` | out | 500 | 500/500 | цифры+пробел+знаки (13) | 5/6/7 | 29 | MIT |
| `out/LagBug/XProtect/gui` | out | 500 | 500/500 | латиница+пробел+знаки (41) | 3/9/17 | 42 | MIT |
| `out/LagBug/XProtect/jump` | out | 500 | 500/500 | латиница (4) | 4/4/4 | 1 | MIT |
| `out/LagBug/XProtect/map` | out | 500 | 0/500 | латиница (62) | 6/6/6 | 500 | MIT |
| `out/LagBug/XProtect/picture` | out | 500 | 0/500 | латиница (20) | 3/4/6 | 20 | MIT |
| `out/LagBug/XProtect/reverse` | out | 500 | 500/500 | латиница (62) | 6/6/6 | 500 | MIT |
| `out/LagBug/XProtect/slot` | out | 500 | 500/500 | цифры (8) | 1/1/1 | 8 | MIT |
| `out/LagBug/XProtect/sneak` | out | 500 | 500/500 | латиница (5) | 5/5/5 | 1 | MIT |
| `out/Mrbysco/Captcha/math` | out | 500 | 500/500 | цифры+пробел+знаки (12) | 5/7/7 | 152 | MIT |
| `out/Yukun99/Captchas/itemslot` | out | 500 | 500/500 | латиница+пробел+знаки (47) | 3/10/20 | 188 | no licence (all rights reserved) |
| `out/Z4OLLIEZ4/reCaptcha/captchasx` | out | 500 | 500/500 | латиница+пробел (20) | 3/5/10 | 13 | MIT |
| `out/haq/mapcha/map` | out | 500 | 499/500 | латиница (61) | 4/4/4 | 500 | MIT |
| `out/irootdev/AnBot/captcha` | out | 500 | 0/500 | латиница (36) | 3/3/3 | 475 | GPL-3.0 |
| `out/jSdCool/minecaptcha/image` | out | 500 | 500/500 | латиница+пробел+знаки (15) | 61/67/70 | 500 | CC0-1.0 |
| `out/jSdCool/minecaptcha/text` | out | 500 | 500/500 | латиница (62) | 8/8/8 | 500 | CC0-1.0 |
| `out/jonesdevelopment/sonar/complex` | out | 500 | 0/500 | латиница (20) | 3/4/4 | 494 | GPL-3.0 |
| `out/jonesdevelopment/sonar/legacy` | out | 500 | 0/500 | латиница (20) | 3/4/4 | 496 | GPL-3.0 |
| `out/jonesdevelopment/sonar/standard` | out | 500 | 0/500 | латиница (20) | 3/3/4 | 500 | GPL-3.0 |
| `out/just-captcha/ProstoCaptcha/map` | out | 500 | 500/500 | латиница (58) | 6/6/6 | 500 | MIT |
| `out/laforetbrut/are-you-sure/code` | out | 500 | 500/500 | латиница (32) | 6/6/6 | 500 | MIT |
| `out/n1zamu/NCaptcha/anvil` | out | 500 | 500/500 | цифры (10) | 3/5/5 | 495 | MIT |
| `out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | out | 500 | 500/500 | латиница (16) | 5/5/5 | 500 | no licence file (all rights reserved) |
| `out_ru/BotFilter/map` | out_ru | 500 | 0/500 | цифры (10) | 4/5/5 | 494 | BSD-2-Clause + запрет на коммерческий хостинг |
| `out_ru/CaptchaGUI/clickblock` | out_ru | 500 | 0/500 | цифры (7) | 1/1/1 | 7 | no licence file (all rights reserved) |
| `out_ru/CaptchaVerifyZ/map` | out_ru | 500 | 500/500 | латиница (36) | 5/5/5 | 500 | all rights reserved (Modrinth) |
| `out_ru/GalleryCaptcha/ru-numberword` | out_ru | 500 | 500/500 | кириллица+пробел (20) | 7/21/28 | 382 | не установлена (см. source в labels.jsonl) |
| `out_ru/GalleryCaptcha/ru-numberword-caption` | out_ru | 500 | 500/500 | кириллица+пробел (20) | 3/21/28 | 380 | не установлена (см. source в labels.jsonl) |
| `out_ru/GalleryCaptcha/ru-object-swatch` | out_ru | 500 | 0/500 | кириллица (15) | 5/6/7 | 5 | не установлена (см. source в labels.jsonl) |
| `out_ru/GalleryCaptcha/ru-symbols` | out_ru | 500 | 500/500 | кириллица (43) | 3/3/3 | 499 | не установлена (см. source в labels.jsonl) |
| `out_ru/GalleryCaptcha/ru-web` | out_ru | 500 | 500/500 | латиница (62) | 5/5/5 | 500 | не установлена (см. source в labels.jsonl) |
| `out_ru/LimboFilter/framed2x2` | out_ru | 500 | 0/500 | кириллица+пробел (20) | 6/21/28 | 389 | AGPL-3.0 |
| `out_ru/LimboFilter/framed3x3` | out_ru | 500 | 0/500 | кириллица+пробел (20) | 6/22/28 | 386 | AGPL-3.0 |
| `out_ru/LimboFilter/map` | out_ru | 500 | 500/500 | кириллица+пробел (20) | 6/21/28 | 388 | AGPL-3.0 |
| `out_ru/LimboFilter/symbols` | out_ru | 500 | 500/500 | кириллица (43) | 3/3/3 | 499 | AGPL-3.0 |

## The plugins and their licences

Each row of the dataset comes from a different upstream plugin, and those plugins do **not**
share one licence. The licence of the data is the licence of the plugin the row came from —
check the column before you use the data. The `mode` column says how the type was rebuilt:

* **faithful** — the upstream algorithm was re-implemented exactly, including its defects;
* **clean-room** — rebuilt from the upstream behaviour without copying its assets;
* **reconstructed** — *measured from reference screenshots* and rebuilt from scratch, so the
  pixels are not the upstream ones.

| плагин | типов | PNG | лицензия | режим |
|---|---|---|---|---|
| `Archy-X/Krypton` | 2 | 1000 | no licence (all rights reserved) | clean-room |
| `BotFilter` | 1 | 500 | BSD-2-Clause + запрет на коммерческий хостинг | clean-room |
| `CaptchaGUI` | 1 | 500 | no licence file (all rights reserved) | clean-room |
| `CaptchaVerifyZ` | 1 | 500 | all rights reserved (Modrinth) | clean-room |
| `China2B2T/Captcha` | 1 | 500 | GPL-3.0 | clean-room |
| `FeelingAlive0/AdvancedCaptcha` | 2 | 1000 | MIT | faithful |
| `GalleryCaptcha` | 5 | 2500 | не установлена (см. source в labels.jsonl) | reconstructed |
| `InstantlyMoist/Captcha` | 1 | 500 | MIT | faithful |
| `JSH32/Minecaptcha` | 1 | 500 | MIT | faithful |
| `Joey61021/captcha` | 1 | 500 | MIT | faithful |
| `LagBug/XProtect` | 12 | 6000 | MIT | faithful |
| `LimboFilter` | 4 | 2000 | AGPL-3.0 | clean-room |
| `Mrbysco/Captcha` | 1 | 500 | MIT | faithful |
| `Yukun99/Captchas` | 1 | 500 | no licence (all rights reserved) | clean-room |
| `Z4OLLIEZ4/reCaptcha` | 1 | 500 | MIT | faithful |
| `haq/mapcha` | 1 | 500 | MIT | faithful |
| `irootdev/AnBot` | 1 | 500 | GPL-3.0 | clean-room |
| `jSdCool/minecaptcha` | 2 | 1000 | CC0-1.0 | faithful |
| `jonesdevelopment/sonar` | 3 | 1500 | GPL-3.0 | clean-room |
| `just-captcha/ProstoCaptcha` | 1 | 500 | MIT | faithful |
| `laforetbrut/are-you-sure` | 1 | 500 | MIT | faithful |
| `n1zamu/NCaptcha` | 1 | 500 | MIT | faithful |
| `ringoame196-s-mcPlugin/ReproductionCAPTCHA` | 1 | 500 | no licence file (all rights reserved) | clean-room |

### Licence by licence

| licence | upstream plugins | captcha types | PNG |
|---|---|---|---|
| AGPL-3.0 | `LimboFilter` | 4 | 2000 |
| BSD-2-Clause + запрет на коммерческий хостинг | `BotFilter` | 1 | 500 |
| CC0-1.0 | `jSdCool/minecaptcha` | 2 | 1000 |
| GPL-3.0 | `China2B2T/Captcha`, `irootdev/AnBot`, `jonesdevelopment/sonar` | 5 | 2500 |
| MIT | `FeelingAlive0/AdvancedCaptcha`, `InstantlyMoist/Captcha`, `JSH32/Minecaptcha`, `Joey61021/captcha`, `LagBug/XProtect`, `Mrbysco/Captcha`, `Z4OLLIEZ4/reCaptcha`, `haq/mapcha`, `just-captcha/ProstoCaptcha`, `laforetbrut/are-you-sure`, `n1zamu/NCaptcha` | 23 | 11500 |
| all rights reserved (Modrinth) | `CaptchaVerifyZ` | 1 | 500 |
| no licence (all rights reserved) | `Archy-X/Krypton`, `Yukun99/Captchas` | 3 | 1500 |
| no licence file (all rights reserved) | `CaptchaGUI`, `ringoame196-s-mcPlugin/ReproductionCAPTCHA` | 2 | 1000 |
| не установлена (см. source в labels.jsonl) | `GalleryCaptcha` | 5 | 2500 |

`source` in every `labels.jsonl` row points at the upstream class and method the type was
re-implemented from, so the provenance of each row can be audited without trusting this table.

* `out/Archy-X/Krypton/map` — режим **clean-room**, плагин `Archy-X/Krypton`; происхождение: com.archyx.krypton.captcha.MapGenerator#generateCode
* `out/Archy-X/Krypton/menu` — режим **clean-room**, плагин `Archy-X/Krypton`; происхождение: com.archyx.krypton.captcha.CaptchaMenu
* `out/China2B2T/Captcha/wool` — режим **clean-room**, плагин `China2B2T/Captcha`; происхождение: org.china2b2t.captchalib.Main#onJoin
* `out/Yukun99/Captchas/itemslot` — режим **clean-room**, плагин `Yukun99/Captchas`; происхождение: me.yukun.captchas.gui.Captcha
* `out/irootdev/AnBot/captcha` — режим **clean-room**, плагин `irootdev/AnBot`; происхождение: iroot.Main#getCaptcha
* `out/jonesdevelopment/sonar/complex` — режим **clean-room**, плагин `jonesdevelopment/sonar`; происхождение: xyz.jonesdev.sonar.captcha.complex.ComplexCaptchaGenerator#createImage
* `out/jonesdevelopment/sonar/legacy` — режим **clean-room**, плагин `jonesdevelopment/sonar`; происхождение: xyz.jonesdev.sonar.captcha.legacy.LegacyCaptchaGenerator#createImage
* `out/jonesdevelopment/sonar/standard` — режим **clean-room**, плагин `jonesdevelopment/sonar`; происхождение: xyz.jonesdev.sonar.captcha.StandardCaptchaGenerator#createImage
* `out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` — режим **clean-room**, плагин `ringoame196-s-mcPlugin/ReproductionCAPTCHA`; происхождение: AuthMapManager#makeAuthImage
* `out_ru/BotFilter/map` — режим **clean-room**, плагин `BotFilter`; происхождение: ru.leymooo.botfilter.captcha.generator.CaptchaPainter#draw
* `out_ru/CaptchaGUI/clickblock` — режим **clean-room**, плагин `CaptchaGUI`; происхождение: me.supl1na.captcha.CaptchaListener#onPlayerJoin
* `out_ru/CaptchaVerifyZ/map` — режим **clean-room**, плагин `CaptchaVerifyZ`; происхождение: com.Mateitaa1.CaptchaVerifyZ$CaptchaMapRenderer#render
* `out_ru/GalleryCaptcha/ru-numberword` — режим **reconstructed**, плагин `GalleryCaptcha`; происхождение: GalleryCaptcha/ru-numberword: clean-room reconstruction of a gallery-style captcha family, measured from reference screenshots; no vendor assets redistributed; renderer: net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha; net.elytrium.limbofilter.captcha.CaptchaGenerator#randomAnswer; net.elytrium.limbofilter.captcha.CaptchaGenerator#spellNumber
* `out_ru/GalleryCaptcha/ru-numberword-caption` — режим **reconstructed**, плагин `GalleryCaptcha`; происхождение: GalleryCaptcha/ru-numberword: clean-room reconstruction of a gallery-style captcha family, measured from reference screenshots; no vendor assets redistributed; renderer: net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha; net.elytrium.limbofilter.captcha.CaptchaGenerator#randomAnswer; net.elytrium.limbofilter.captcha.CaptchaGenerator#spellNumber
* `out_ru/GalleryCaptcha/ru-object-swatch` — режим **reconstructed**, плагин `GalleryCaptcha`; происхождение: GalleryCaptcha/ru-object-swatch: clean-room reconstruction of the object-grid captcha family, measured from reference screenshots; no vendor assets redistributed
* `out_ru/GalleryCaptcha/ru-symbols` — режим **reconstructed**, плагин `GalleryCaptcha`; происхождение: GalleryCaptcha/ru-symbols: clean-room reconstruction of a gallery-style captcha family, measured from reference screenshots; no vendor assets redistributed; renderer: net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha; net.elytrium.limbofilter.captcha.CaptchaGenerator#randomAnswer
* `out_ru/GalleryCaptcha/ru-web` — режим **reconstructed**, плагин `GalleryCaptcha`; происхождение: GalleryCaptcha/ru-web: clean-room reconstruction of the generic web-captcha family, measured from reference screenshots; no vendor assets redistributed
* `out_ru/LimboFilter/framed2x2` — режим **clean-room**, плагин `LimboFilter`; происхождение: net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha; net.elytrium.limbofilter.captcha.CaptchaGenerator#randomAnswer; net.elytrium.limbofilter.captcha.CaptchaGenerator#spellNumber
* `out_ru/LimboFilter/framed3x3` — режим **clean-room**, плагин `LimboFilter`; происхождение: net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha; net.elytrium.limbofilter.captcha.CaptchaGenerator#randomAnswer; net.elytrium.limbofilter.captcha.CaptchaGenerator#spellNumber
* `out_ru/LimboFilter/map` — режим **clean-room**, плагин `LimboFilter`; происхождение: net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha; net.elytrium.limbofilter.captcha.CaptchaGenerator#randomAnswer; net.elytrium.limbofilter.captcha.CaptchaGenerator#spellNumber
* `out_ru/LimboFilter/symbols` — режим **clean-room**, плагин `LimboFilter`; происхождение: net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha; net.elytrium.limbofilter.captcha.CaptchaGenerator#randomAnswer

## Alphabets

The labels are not pure ASCII: some types are Russian number words, some are arithmetic
expressions, some contain spaces and punctuation.

* `out/Archy-X/Krypton/map` — алфавит (62 символов): `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`
* `out/Archy-X/Krypton/menu` — алфавит (26 символов): `ABCDEFGHIJKLMNOPQRSTUVWYZ_`
* `out/China2B2T/Captcha/wool` — алфавит (7 символов): `EILMOW_`
* `out/FeelingAlive0/AdvancedCaptcha/button` — алфавит (29 символов): ` CHMNPST[]abcdeghiklnoprstuwy`
* `out/FeelingAlive0/AdvancedCaptcha/math` — алфавит (14 символов): ` *+-0123456789`
* `out/InstantlyMoist/Captcha/textcaptcha` — алфавит (26 символов): `abcdefghijklmnopqrstuvwxyz`
* `out/JSH32/Minecaptcha/map` — алфавит (61 символов): `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYabcdefghijklmnopqrstuvwxyz`
* `out/Joey61021/captcha/colorgui` — алфавит (19 символов): `BLOPRYadegiklmnoruw`
* `out/LagBug/XProtect/code` — алфавит (62 символов): `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`
* `out/LagBug/XProtect/color` — алфавит (20 символов): ` abcdeghiklnopqrtuwy`
* `out/LagBug/XProtect/different` — алфавит (11 символов): `ABCDEKLMOR_`
* `out/LagBug/XProtect/drop` — алфавит (4 символов): `dopr`
* `out/LagBug/XProtect/equation` — алфавит (13 символов): ` +-0123456789`
* `out/LagBug/XProtect/gui` — алфавит (41 символов): ` 'BCDEGHIJLMNOPQRSabcdefghiklmnoprstuvwyz`
* `out/LagBug/XProtect/jump` — алфавит (4 символов): `jmpu`
* `out/LagBug/XProtect/map` — алфавит (62 символов): `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`
* `out/LagBug/XProtect/picture` — алфавит (20 символов): `abcdefghiklmnoprstuw`
* `out/LagBug/XProtect/reverse` — алфавит (62 символов): `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`
* `out/LagBug/XProtect/slot` — алфавит (8 символов): `12345678`
* `out/LagBug/XProtect/sneak` — алфавит (5 символов): `aekns`
* `out/Mrbysco/Captcha/math` — алфавит (12 символов): ` +0123456789`
* `out/Yukun99/Captchas/itemslot` — алфавит (47 символов): ` 'ABCDEFGHIJLMNOPQRSTVWabcdefghiklmnoprstuvwxyz`
* `out/Z4OLLIEZ4/reCaptcha/captchasx` — алфавит (20 символов): ` abcdeghiklmnoprtuwy`
* `out/haq/mapcha/map` — алфавит (61 символов): `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYabcdefghijklmnopqrstuvwxyz`
* `out/irootdev/AnBot/captcha` — алфавит (36 символов): `0123456789abcdefghijklmnopqrstuvwxyz`
* `out/jSdCool/minecaptcha/image` — алфавит (15 символов): ` ,0123456789gim`
* `out/jSdCool/minecaptcha/text` — алфавит (62 символов): `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`
* `out/jonesdevelopment/sonar/complex` — алфавит (20 символов): `abcdefhjkmnoprstuxyz`
* `out/jonesdevelopment/sonar/legacy` — алфавит (20 символов): `abcdefhjkmnoprstuxyz`
* `out/jonesdevelopment/sonar/standard` — алфавит (20 символов): `abcdefhjkmnoprstuxyz`
* `out/just-captcha/ProstoCaptcha/map` — алфавит (58 символов): `23456789ABCDEFGHIJKLMNPQRSTUVWXYZabcdefghijklmnpqrstuvwxyz`
* `out/laforetbrut/are-you-sure/code` — алфавит (32 символов): `23456789ABCDEFGHJKLMNPQRSTUVWXYZ`
* `out/n1zamu/NCaptcha/anvil` — алфавит (10 символов): `0123456789`
* `out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` — алфавит (16 символов): `0123456789ABCDEF`
* `out_ru/BotFilter/map` — алфавит (10 символов): `0123456789`
* `out_ru/CaptchaGUI/clickblock` — алфавит (7 символов): `1234567`
* `out_ru/CaptchaVerifyZ/map` — алфавит (36 символов): `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ`
* `out_ru/GalleryCaptcha/ru-numberword` — алфавит (20 символов): ` авдеикмнопрстцчшыья`
* `out_ru/GalleryCaptcha/ru-numberword-caption` — алфавит (20 символов): ` авдеикмнопрстцчшыья`
* `out_ru/GalleryCaptcha/ru-object-swatch` — алфавит (15 символов): `абежзйклнрстчыё`
* `out_ru/GalleryCaptcha/ru-symbols` — алфавит (43 символов): `0123456789ЁАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ`
* `out_ru/GalleryCaptcha/ru-web` — алфавит (62 символов): `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`
* `out_ru/LimboFilter/framed2x2` — алфавит (20 символов): ` авдеикмнопрстцчшыья`
* `out_ru/LimboFilter/framed3x3` — алфавит (20 символов): ` авдеикмнопрстцчшыья`
* `out_ru/LimboFilter/map` — алфавит (20 символов): ` авдеикмнопрстцчшыья`
* `out_ru/LimboFilter/symbols` — алфавит (43 символов): `0123456789ЁАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ`

## What is NOT published here

* **The reference screenshots of the upstream plugins.** The author's working tree contains
  517 reference screenshots of other people's plugins (523 files in
  total in the `real_shots/` directories of the Russian tree). They are other people's images:
  they are **not** part of this repository and are not redistributed in any form. Every published
  PNG is our own render.
* No picture, page or answer taken from a third-party commercial service is published here.
* No model weights, no training logs, no measured-result files — this repository is data only.

## How to load it

The dataset is a directory of files. The shortest way:

```python
import json
from pathlib import Path

root = Path("data")           # clone of the repository
for labels in root.rglob("labels.jsonl"):
    for line in labels.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        image = labels.parent / row["file"]     # PNG next to the label
        band = row["roi"]                        # [x, y, w, h] or None
        answer = row["answer"]                  # what the player types
        drawn = row["text"]                     # what is drawn
```

`dataset_inventory.json` in the root of the repository is the per-type summary: sample count,
alphabet, label lengths, presence of the band, licence. Read it to build a list of training
types without walking the pictures.

## Provenance and honesty

* **Every published image is our own render.** All 23000 PNG in this repository were
  produced by this project's **own Java generators** — not by a live server, not by a
  third-party service, and not by copying anybody else's pictures. The renders reproduce the
  upstream algorithms (font, palette, noise, layout, even the upstream defect), but the pixels
  are a re-render, not a screenshot of a real session.
* The reference screenshots of the upstream plugins are **not** part of this repository: they
  are other people's images, they stay in the project's working tree and are not redistributed.
* **25 of the 46 types are faithful ports** — the upstream algorithm was
  re-implemented exactly, including its defects.
* **16 types are clean-room reconstructions**, and 5
  are marked `reconstructed`: they were **measured from reference screenshots** and rebuilt
  from scratch, so they are *not* faithful ports and their pixels are not the upstream ones.
  The list is below, with the provenance string each type carries in `labels.jsonl`.

* Numbers in this card are computed from `labels.jsonl` by `tools/upload_dataset.py` at
  upload time; they are not typed by hand.

## Licence

* The **data** is published under the licences of the upstream plugins, one per type — see the
  plugin table above. There is no single licence for the whole dataset; that is what the YAML
  field `license_name: mixed-per-plugin-licences` means.
* The **file `LICENSE`** in the root of this repository holds the same breakdown in full: the
  per-plugin table, what each licence means for you, and an explicit note about the plugins that
  granted no licence at all.
* The **generator code** of the project is under a separate licence.
* A user of this dataset must comply with the licence of the plugin each row came from.

<!-- captchaocr-gallery:begin -->

## Gallery

Три контактных листа: все 46 типов, по шесть картинок на тип. Красная рамка — полоса (roi), из неё модель читает ответ; подпись «модель: …» — ответ опубликованной модели (зелёная — точный, красная — ошибка).

![Контактный лист 1/3 — 46 типов, 6 картинок на тип](gallery/sheet_01.png)

![Контактный лист 2/3 — 46 типов, 6 картинок на тип](gallery/sheet_02.png)

![Контактный лист 3/3 — 46 типов, 6 картинок на тип](gallery/sheet_03.png)

### Скорее таблица — опубликованная модель на всех 46 типах

`Titlehhhh/captchaocr-ppocrv6` (PP-OCRv6_medium_rec + WiSE-FT, α = 0.4). Кроп: полоса `roi`, где она есть, иначе кадр, обрезанный по рамке чернил. Эталон — нарисованная строка `text`. «все 500» открывает папку типа на Hub.

| Тип | n | exact match | CER | все 500 |
|---|---|---|---|---|
| `out/Archy-X/Krypton/map` | 500 | 90.8% | 0.020 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/Archy-X/Krypton/map) |
| `out/Archy-X/Krypton/menu` | 500 | 0.0% | 0.999 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/Archy-X/Krypton/menu) |
| `out_ru/BotFilter/map` | 500 | 74.0% | 0.084 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/BotFilter/map) |
| `out_ru/CaptchaGUI/clickblock` | 500 | 0.0% | 6.274 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/CaptchaGUI/clickblock) |
| `out_ru/CaptchaVerifyZ/map` | 500 | 99.8% | 0.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/CaptchaVerifyZ/map) |
| `out/China2B2T/Captcha/wool` | 500 | 0.0% | 1.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/China2B2T/Captcha/wool) |
| `out/FeelingAlive0/AdvancedCaptcha/button` | 500 | 0.0% | 0.605 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/FeelingAlive0/AdvancedCaptcha/button) |
| `out/FeelingAlive0/AdvancedCaptcha/math` | 500 | 99.8% | 0.001 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/FeelingAlive0/AdvancedCaptcha/math) |
| `out_ru/GalleryCaptcha/ru-numberword` | 500 | 0.0% | 1.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/GalleryCaptcha/ru-numberword) |
| `out_ru/GalleryCaptcha/ru-numberword-caption` | 500 | 0.0% | 1.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/GalleryCaptcha/ru-numberword-caption) |
| `out_ru/GalleryCaptcha/ru-object-swatch` | 500 | 0.0% | 1.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/GalleryCaptcha/ru-object-swatch) |
| `out_ru/GalleryCaptcha/ru-symbols` | 500 | 0.8% | 0.902 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/GalleryCaptcha/ru-symbols) |
| `out_ru/GalleryCaptcha/ru-web` | 500 | 94.6% | 0.012 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/GalleryCaptcha/ru-web) |
| `out/InstantlyMoist/Captcha/textcaptcha` | 500 | 10.8% | 0.598 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/InstantlyMoist/Captcha/textcaptcha) |
| `out/JSH32/Minecaptcha/map` | 500 | 95.0% | 0.013 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/JSH32/Minecaptcha/map) |
| `out/Joey61021/captcha/colorgui` | 500 | 82.8% | 0.029 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/Joey61021/captcha/colorgui) |
| `out/LagBug/XProtect/code` | 500 | 0.0% | 0.990 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/code) |
| `out/LagBug/XProtect/color` | 500 | 0.0% | 1.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/color) |
| `out/LagBug/XProtect/different` | 500 | 0.0% | 1.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/different) |
| `out/LagBug/XProtect/drop` | 500 | 100.0% | 0.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/drop) |
| `out/LagBug/XProtect/equation` | 500 | 100.0% | 0.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/equation) |
| `out/LagBug/XProtect/gui` | 500 | 100.0% | 0.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/gui) |
| `out/LagBug/XProtect/jump` | 500 | 100.0% | 0.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/jump) |
| `out/LagBug/XProtect/map` | 500 | 0.0% | 0.992 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/map) |
| `out/LagBug/XProtect/picture` | 500 | 0.0% | 1.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/picture) |
| `out/LagBug/XProtect/reverse` | 500 | 90.4% | 0.018 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/reverse) |
| `out/LagBug/XProtect/slot` | 500 | 100.0% | 0.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/slot) |
| `out/LagBug/XProtect/sneak` | 500 | 100.0% | 0.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/LagBug/XProtect/sneak) |
| `out_ru/LimboFilter/framed2x2` | 500 | 0.0% | 1.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/LimboFilter/framed2x2) |
| `out_ru/LimboFilter/framed3x3` | 500 | 0.0% | 1.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/LimboFilter/framed3x3) |
| `out_ru/LimboFilter/map` | 500 | 0.0% | 1.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/LimboFilter/map) |
| `out_ru/LimboFilter/symbols` | 500 | 0.4% | 0.905 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out_ru/LimboFilter/symbols) |
| `out/Mrbysco/Captcha/math` | 500 | 86.4% | 0.030 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/Mrbysco/Captcha/math) |
| `out/Yukun99/Captchas/itemslot` | 500 | 81.4% | 0.018 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/Yukun99/Captchas/itemslot) |
| `out/Z4OLLIEZ4/reCaptcha/captchasx` | 500 | 92.6% | 0.011 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/Z4OLLIEZ4/reCaptcha/captchasx) |
| `out/haq/mapcha/map` | 500 | 94.4% | 0.015 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/haq/mapcha/map) |
| `out/irootdev/AnBot/captcha` | 500 | 94.8% | 0.018 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/irootdev/AnBot/captcha) |
| `out/jSdCool/minecaptcha/image` | 500 | 0.0% | 0.554 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/jSdCool/minecaptcha/image) |
| `out/jSdCool/minecaptcha/text` | 500 | 98.6% | 0.002 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/jSdCool/minecaptcha/text) |
| `out/jonesdevelopment/sonar/complex` | 500 | 48.4% | 0.219 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/jonesdevelopment/sonar/complex) |
| `out/jonesdevelopment/sonar/legacy` | 500 | 45.8% | 0.255 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/jonesdevelopment/sonar/legacy) |
| `out/jonesdevelopment/sonar/standard` | 500 | 63.8% | 0.150 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/jonesdevelopment/sonar/standard) |
| `out/just-captcha/ProstoCaptcha/map` | 500 | 66.4% | 0.078 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/just-captcha/ProstoCaptcha/map) |
| `out/laforetbrut/are-you-sure/code` | 500 | 1.8% | 0.681 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/laforetbrut/are-you-sure/code) |
| `out/n1zamu/NCaptcha/anvil` | 500 | 100.0% | 0.000 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/n1zamu/NCaptcha/anvil) |
| `out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | 500 | 95.6% | 0.009 | [все 500 →](https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/tree/main/data/out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map) |

Микро по всем 46 типам: **50.2%** exact, CER **0.5322**; медиана по типам: **65.1%** exact, CER **0.1173**. На тех же 7 удержанных типах этот код даёт **61.2%** micro / **63.8%** median — опубликованные с моделью числа были 61.2% / 63.8%, то есть пайплайн воспроизводится.

Почему «все 46» ниже, чем «7 удержанных»: в наборе 46 типов есть типы без полосы (кадр целиком), группа C (это вообще не задача OCR: ответ — название цвета, номер слота, картинка) и кириллические типы, символы которых **нет в словаре модели** (в словаре PP-OCRv6 нет ни одной кириллической буквы).

### Модели

Единый протокол: 20 картинок на тип, два режима — «полоса» и «весь кадр»; число — micro exact match по 29 типам, у которых есть полоса. Строки «наши» измерены другим протоколом (500 картинок на тип, разбиение по типам) и в один столбец с чужими моделями не сопоставимы.

| Модель | полоса | кадр | лицензия | примечание |
|---|---|---|---|---|
| [PaddlePaddle/PP-OCRv6_medium_rec_onnx](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_onnx) | 55.2% | 3.4% | Apache-2.0 | 29 типов с полосой, 20 картинок на тип |
| [PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec_onnx](https://huggingface.co/PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec_onnx) | 46.2% | 1.6% | Apache-2.0 | 29 типов с полосой, 20 картинок на тип |
| [PaddlePaddle/PP-OCRv5_mobile_rec_onnx](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec_onnx) | 46.2% | 0.7% | Apache-2.0 | 29 типов с полосой, 20 картинок на тип |
| easyocr | 32.8% | — | Apache-2.0 | только старый набор legacy64 (8 типов) |
| [anuashok/ocr-captcha-v3](https://huggingface.co/anuashok/ocr-captcha-v3) | 29.7% | 1.6% | Apache-2.0 | 29 типов с полосой, 20 картинок на тип |
| [graycat660/doctr-crnn-vgg16-bn-russian-onnx](https://huggingface.co/graycat660/doctr-crnn-vgg16-bn-russian-onnx) | 27.8% | 0.5% | Apache-2.0 | 29 типов с полосой, 20 картинок на тип |
| [Graf-J/captcha-crnn-base](https://huggingface.co/Graf-J/captcha-crnn-base) | 8.3% | 0.3% | MIT | 29 типов с полосой, 20 картинок на тип |
| [Graf-J/captcha-crnn-finetuned](https://huggingface.co/Graf-J/captcha-crnn-finetuned) | 6.7% | 0.0% | MIT | 29 типов с полосой, 20 картинок на тип |
| [Graf-J/captcha-conv-transformer-finetuned](https://huggingface.co/Graf-J/captcha-conv-transformer-finetuned) | 6.4% | 0.3% | MIT | 29 типов с полосой, 20 картинок на тип |
| [emelnov/ocr-captcha-v4-mailru](https://huggingface.co/emelnov/ocr-captcha-v4-mailru) | 4.3% | 0.0% | (tag not set; base TrOCR = MIT) | 29 типов с полосой, 20 картинок на тип |
| [jtrecenti/txtcaptcha-crnn](https://huggingface.co/jtrecenti/txtcaptcha-crnn) | 0.3% | 0.0% | MIT | 29 типов с полосой, 20 картинок на тип |
| [microsoft/trocr-base-printed](https://huggingface.co/microsoft/trocr-base-printed) | — | — | MIT | замер не состоялся: ValueError: You need to specify either `text` or `text_target`. |
| [Titlehhhh/captchaocr-ppocrv6](https://huggingface.co/Titlehhhh/captchaocr-ppocrv6) | 61.2% | — | Apache-2.0 | PP-OCRv6_medium_rec + WiSE-FT α=0.4; 7 удержанных типов, 3500 картинок — другой протокол, с чужими моделями в один столбец не сравнивается |
| наш CRNN + CTC (обучен с нуля, не опубликован) | 38.1% | — | - | другой протокол (500 картинок на тип, разбиение по типам): невиданные типы micro 38.1% (n=1999), свои типы 100.0% — это запоминание, а не обобщение |

Полный замер по 46 типам (с примерами «эталон → ответ модели»): `reports/model_scoreboard.json` в репозитории проекта.

<!-- captchaocr-gallery:end -->
