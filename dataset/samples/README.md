# Образцы датасета — 5 картинок на каждый из 46 типов
Это **витрина**, а не датасет. Здесь лежит по 5 картинок (`001.png` … `005.png`)
на каждый тип капчи, чтобы было видно, что вообще бывает, не скачивая
полный набор.

Полный датасет — **23 000 размеченных PNG** (46 типов, по 500 на тип) — лежит на Hugging Face:
<https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset>

Скачать его одной командой (из корня репозитория):

```powershell
python tools\fetch_dataset.py
```

## Как устроен каталог

Имена каталогов повторяют структуру типов:

```
dataset/samples/<plugin>/<type>/001.png … 005.png
```

* Для типов из `dataset/out/` плагин записан как `owner/repo` (например `haq/mapcha`) —
  так он назван в `labels.jsonl` и в репозитории апстрима.
* Для типов из `dataset/out_ru/` плагин назван плоско (например `GalleryCaptcha`).

Подпись под каждой картинкой — поле `answer` из `labels.jsonl`: то, что игрок должен
ввести. В 9 типах из 46 `answer` отличается от того, что **нарисовано** (`text`) —
тогда рядом с ответом показано и нарисованное (см. таблицу в конце файла).

Девять из этих картинок (по одной на стиль — карта, латинский код, кириллица, «веб-капча»,
пазл-рамка, GUI-сцена, чат-сцена, цифры, числительные) выведены в галерею в начале
`README.md` репозитория.

## Полный список типов

| # | Дерево | Тип (плагин / капча) | Ответы (5 шт.) |
|---|---|---|---|
| 1 | `out` | `Archy-X/Krypton` / `map` | `93j79`, `2r1zZ`, `8Sg36`, `mnPhJ`, `d2IL9` |
| 2 | `out` | `Archy-X/Krypton` / `menu` | `PODZOL`, `RAIL`, `SLIME_BLOCK`, `CRAFTING_TABLE`, `HAY_BLOCK` |
| 3 | `out` | `China2B2T/Captcha` / `wool` | `LIME_WOOL`, `LIME_WOOL`, `LIME_WOOL`, `LIME_WOOL`, `LIME_WOOL` |
| 4 | `out` | `FeelingAlive0/AdvancedCaptcha` / `button` | `[PressThis] in pink color`, `[Push] in red color`, `[Press] in black color`, `[ChooseNow] in gray color`, `[PushHere] in black color` |
| 5 | `out` | `FeelingAlive0/AdvancedCaptcha` / `math` | `21`, `31`, `-2`, `21`, `20` |
| 6 | `out` | `InstantlyMoist/Captcha` / `textcaptcha` | `qnspj`, `tfkec`, `qjxtv`, `nhpje`, `kazmb` |
| 7 | `out` | `JSH32/Minecaptcha` / `map` | `HClf`, `6xhX`, `TDF6`, `QucT`, `c6yD` |
| 8 | `out` | `Joey61021/captcha` / `colorgui` | `Pink`, `Yellow`, `Yellow`, `Yellow`, `Orange` |
| 9 | `out` | `LagBug/XProtect` / `code` | `g5vyu3`, `rrFsOz`, `Y8R0sj`, `iOGdA3`, `jHkKiY` |
| 10 | `out` | `LagBug/XProtect` / `color` | `green`, `purple`, `gray`, `gray`, `white` |
| 11 | `out` | `LagBug/XProtect` / `different` | `EMERALD_BLOCK`, `EMERALD_BLOCK`, `EMERALD_BLOCK`, `EMERALD_BLOCK`, `EMERALD_BLOCK` |
| 12 | `out` | `LagBug/XProtect` / `drop` | `drop`, `drop`, `drop`, `drop`, `drop` |
| 13 | `out` | `LagBug/XProtect` / `equation` | `16`, `16`, `3`, `27`, `8` |
| 14 | `out` | `LagBug/XProtect` / `gui` | `Purpur Block`, `Snow Block`, `Gold Block`, `Bone Block`, `Iron Ore` |
| 15 | `out` | `LagBug/XProtect` / `jump` | `jump`, `jump`, `jump`, `jump`, `jump` |
| 16 | `out` | `LagBug/XProtect` / `map` | `k1VIUF`, `lcub2N`, `1zDARp`, `HR71uw`, `Ewp0Hr` |
| 17 | `out` | `LagBug/XProtect` / `picture` | `fish`, `cat`, `lamp`, `book`, `boat` |
| 18 | `out` | `LagBug/XProtect` / `reverse` | `8wIsZg`, `kDbamd`, `MroG03`, `1uc1AU`, `BGvYH5` |
| 19 | `out` | `LagBug/XProtect` / `slot` | `8`, `4`, `8`, `4`, `6` |
| 20 | `out` | `LagBug/XProtect` / `sneak` | `sneak`, `sneak`, `sneak`, `sneak`, `sneak` |
| 21 | `out` | `Mrbysco/Captcha` / `math` | `122`, `77`, `159`, `27`, `80` |
| 22 | `out` | `Yukun99/Captchas` / `itemslot` | `Brown Mushroom`, `Iron Block`, `Snow Ball`, `Flint and Steel`, `Iron Axe` |
| 23 | `out` | `Z4OLLIEZ4/reCaptcha` / `captchasx` | `red`, `brown`, `cyan`, `cyan`, `blue` |
| 24 | `out` | `haq/mapcha` / `map` | `zPyf`, `YQm2`, `SkGn`, `NQcm`, `eDHG` |
| 25 | `out` | `irootdev/AnBot` / `captcha` | `998`, `107`, `lpy`, `227`, `bdc` |
| 26 | `out` | `jSdCool/minecaptcha` / `image` | `img2223, img2990, img2721, img2117, img85, img1197, img2061, img442`, `img2522, img2324, img2325, img579, img1427, img1636, img1418, img2105`, `img921, img2274, img3057, img1199, img191, img2373, img1163, img912`, `img2310, img2397, img381, img322, img2613, img6, img224, img1969`, `img1911, img1577, img938, img492, img100, img226, img31, img2382` |
| 27 | `out` | `jSdCool/minecaptcha` / `text` | `BhagzUQJ`, `VnW4kksa`, `03YGJWrb`, `Rw6KyWWF`, `OUrZNkPm` |
| 28 | `out` | `jonesdevelopment/sonar` / `complex` | `pkr`, `fcds`, `ukzc`, `uufu`, `rzcs` |
| 29 | `out` | `jonesdevelopment/sonar` / `legacy` | `jdhe`, `bch`, `aefm`, `yhre`, `suk` |
| 30 | `out` | `jonesdevelopment/sonar` / `standard` | `beh`, `hzop`, `mepm`, `tyca`, `xxte` |
| 31 | `out` | `just-captcha/ProstoCaptcha` / `map` | `PWw33f`, `ktuzed`, `kVbWyj`, `P4ZteS`, `vW8JJa` |
| 32 | `out` | `laforetbrut/are-you-sure` / `code` | `MPFFM5`, `ZSPSMA`, `WCSVTJ`, `LETQAB`, `BCHNTK` |
| 33 | `out` | `n1zamu/NCaptcha` / `anvil` | `37761`, `6211`, `37473`, `51762`, `3957` |
| 34 | `out` | `ringoame196-s-mcPlugin/ReproductionCAPTCHA` / `map` | `61143`, `B7E7F`, `D4D6E`, `A1BB7`, `77040` |
| 35 | `out_ru` | `BotFilter` / `map` | `38920`, `92423`, `8703`, `5422`, `6486` |
| 36 | `out_ru` | `CaptchaGUI` / `clickblock` | `3`, `6`, `6`, `5`, `7` |
| 37 | `out_ru` | `CaptchaVerifyZ` / `map` | `NR6PI`, `BLROT`, `NSPXI`, `5DIOI`, `JXGIN` |
| 38 | `out_ru` | `GalleryCaptcha` / `ru-numberword` | `578`, `316`, `692`, `837`, `436` |
| 39 | `out_ru` | `GalleryCaptcha` / `ru-numberword-caption` | `384`, `220`, `766`, `631`, `571` |
| 40 | `out_ru` | `GalleryCaptcha` / `ru-object-swatch` | `красный`, `чёрный`, `зелёный`, `белый`, `красный` |
| 41 | `out_ru` | `GalleryCaptcha` / `ru-symbols` | `5МП`, `УНЛ`, `ЕЖТ`, `ЫБЁ`, `НЁЖ` |
| 42 | `out_ru` | `GalleryCaptcha` / `ru-web` | `DdtOv`, `DELss`, `JlKsa`, `Lpo2L`, `lmpFS` |
| 43 | `out_ru` | `LimboFilter` / `framed2x2` | `406`, `813`, `147`, `899`, `414` |
| 44 | `out_ru` | `LimboFilter` / `framed3x3` | `536`, `955`, `464`, `345`, `932` |
| 45 | `out_ru` | `LimboFilter` / `map` | `481`, `699`, `550`, `987`, `539` |
| 46 | `out_ru` | `LimboFilter` / `symbols` | `ШМШ`, `ЬЙХ`, `УНЬ`, `ДОТ`, `0ИР` |

## Типы, где ответ ≠ нарисованный текст (9 из 46)

В этих типах поле `answer` (то, что игрок вводит) отличается от поля `text` (то, что
**нарисовано** на картинке). Ниже — пять показанных выше картинок каждого такого типа:
`ответ` → `нарисованный текст`.

| Тип | 001.png | 002.png | 003.png | 004.png | 005.png |
|---|---|---|---|---|---|
| `FeelingAlive0/AdvancedCaptcha/math` | `21` → `20 + 1` | `31` → `20 + 11` | `-2` → `1 - 3` | `21` → `13 + 8` | `20` → `1 * 20` |
| `LagBug/XProtect/equation` | `16` → `6 + 10` | `16` → `5 + 11` | `3` → `8 - 5` | `27` → `13 + 14` | `8` → `14 - 6` |
| `LagBug/XProtect/reverse` | `8wIsZg` → `gZsIw8` | `kDbamd` → `dmabDk` | `MroG03` → `30GorM` | `1uc1AU` → `UA1cu1` | `BGvYH5` → `5HYvGB` |
| `Mrbysco/Captcha/math` | `122` → `71 + 51` | `77` → `44 + 33` | `159` → `80 + 79` | `27` → `13 + 14` | `80` → `37 + 43` |
| `GalleryCaptcha/ru-numberword` | `578` → `пятьсот семьдесят восемь` | `316` → `триста шестнадцать` | `692` → `шестьсот девяносто два` | `837` → `восемьсот тридцать семь` | `436` → `четыреста тридцать шесть` |
| `GalleryCaptcha/ru-numberword-caption` | `384` → `триста восемьдесят четыре` | `220` → `двести двадцать` | `766` → `семьсот шестьдесят шесть` | `631` → `шестьсот тридцать один` | `571` → `пятьсот семьдесят один` |
| `LimboFilter/framed2x2` | `406` → `четыреста шесть` | `813` → `восемьсот тринадцать` | `147` → `сто сорок семь` | `899` → `восемьсот девяносто девять` | `414` → `четыреста четырнадцать` |
| `LimboFilter/framed3x3` | `536` → `пятьсот тридцать шесть` | `955` → `девятьсот пятьдесят пять` | `464` → `четыреста шестьдесят четыре` | `345` → `триста сорок пять` | `932` → `девятьсот тридцать два` |
| `LimboFilter/map` | `481` → `четыреста восемьдесят один` | `699` → `шестьсот девяносто девять` | `550` → `пятьсот пятьдесят` | `987` → `девятьсот восемьдесят семь` | `539` → `пятьсот тридцать девять` |

Картинки скопированы из сгенерированного датасета **дословно** — это те же PNG,
что лежат в `dataset/out/` и `dataset/out_ru/`, без перерисовки и сжатия.
