# Образцы датасета — 5 картинок на каждый из 46 типов
Это **витрина**, а не датасет. Здесь лежит по 5 картинок (`001.png` … `005.png`)
на каждый тип капчи, чтобы было видно, что вообще бывает, не скачивая
полный набор.

Полный датасет — **4600 размеченных PNG** — лежит на Hugging Face:
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
ввести. В 9 типах из 46 `answer` отличается от того, что **нарисовано** (`text`).

Девять из этих картинок (по одной на стиль — карта, латинский код, кириллица, «веб-капча»,
пазл-рамка, GUI-сцена, чат-сцена, цифры, числительные) выведены в галерею в начале
`README.md` репозитория.

## Полный список типов

| # | Дерево | Тип (плагин / капча) | Ответы (5 шт.) |
|---|---|---|---|
| 1 | `out` | `Archy-X/Krypton` / `map` | `lCKuj`, `Sdtga`, `90L4k`, `fnU66`, `Pjsbn` |
| 2 | `out` | `Archy-X/Krypton` / `menu` | `TALL_GRASS`, `OBSIDIAN`, `REDSTONE_TORCH`, `SPRUCE_LOG`, `OAK_LEAVES` |
| 3 | `out` | `China2B2T/Captcha` / `wool` | `LIME_WOOL`, `LIME_WOOL`, `LIME_WOOL`, `LIME_WOOL`, `LIME_WOOL` |
| 4 | `out` | `FeelingAlive0/AdvancedCaptcha` / `button` | `[ClickThat] in white color`, `[PressNow] in blue color`, `[Pick] in green color`, `[PressThis] in white color`, `[ClickNow] in white color` |
| 5 | `out` | `FeelingAlive0/AdvancedCaptcha` / `math` | `130`, `221`, `8`, `-7`, `16` |
| 6 | `out` | `InstantlyMoist/Captcha` / `textcaptcha` | `vwmoq`, `mzzpu`, `fakve`, `mgvyk`, `lbexv` |
| 7 | `out` | `JSH32/Minecaptcha` / `map` | `PTAY`, `9Tll`, `SPlu`, `tw8A`, `c7v4` |
| 8 | `out` | `Joey61021/captcha` / `colorgui` | `Red`, `Pink`, `Yellow`, `Lime`, `Lime` |
| 9 | `out` | `LagBug/XProtect` / `code` | `EzhYNY`, `XnKgu7`, `U3ECHx`, `1cT5Fa`, `LiNwNd` |
| 10 | `out` | `LagBug/XProtect` / `color` | `blue`, `white`, `gray`, `green`, `red` |
| 11 | `out` | `LagBug/XProtect` / `different` | `EMERALD_BLOCK`, `EMERALD_BLOCK`, `EMERALD_BLOCK`, `EMERALD_BLOCK`, `EMERALD_BLOCK` |
| 12 | `out` | `LagBug/XProtect` / `drop` | `drop`, `drop`, `drop`, `drop`, `drop` |
| 13 | `out` | `LagBug/XProtect` / `equation` | `15`, `22`, `14`, `21`, `10` |
| 14 | `out` | `LagBug/XProtect` / `gui` | `Glowstone`, `Netherrack`, `Emerald Block`, `Pumpkin`, `Netherrack` |
| 15 | `out` | `LagBug/XProtect` / `jump` | `jump`, `jump`, `jump`, `jump`, `jump` |
| 16 | `out` | `LagBug/XProtect` / `map` | `rYnf3j`, `pLnnLN`, `zbffJ2`, `rR6hrf`, `IopLVU` |
| 17 | `out` | `LagBug/XProtect` / `picture` | `sun`, `book`, `dog`, `book`, `bird` |
| 18 | `out` | `LagBug/XProtect` / `reverse` | `SyBFrM`, `YXJHAr`, `UI3OZ5`, `eijjae`, `45JMyS` |
| 19 | `out` | `LagBug/XProtect` / `slot` | `2`, `4`, `4`, `4`, `2` |
| 20 | `out` | `LagBug/XProtect` / `sneak` | `sneak`, `sneak`, `sneak`, `sneak`, `sneak` |
| 21 | `out` | `Mrbysco/Captcha` / `math` | `131`, `117`, `57`, `81`, `23` |
| 22 | `out` | `Yukun99/Captchas` / `itemslot` | `Obsidian`, `Dispenser`, `Stone Button`, `Golden Hoe`, `Torch` |
| 23 | `out` | `Z4OLLIEZ4/reCaptcha` / `captchasx` | `orange`, `red`, `red`, `white`, `purple` |
| 24 | `out` | `haq/mapcha` / `map` | `s8TO`, `4AUe`, `slWI`, `TrXD`, `kkQ6` |
| 25 | `out` | `irootdev/AnBot` / `captcha` | `via`, `081`, `jkz`, `635`, `s7j` |
| 26 | `out` | `jSdCool/minecaptcha` / `image` | `img2360, img2959, img1571, img621, img2446, img951, img1375, img1509`, `img2988, img1230, img1333, img346, img699, img2257, img874, img1891`, `img1991, img151, img2733, img2201, img2847, img1810, img2962, img1914`, `img2703, img1212, img2161, img1185, img2961, img633, img2473, img1558`, `img1563, img1483, img2382, img83, img2366, img937, img2966, img1346` |
| 27 | `out` | `jSdCool/minecaptcha` / `text` | `4nznyZ4U`, `Fk6ZNfzZ`, `n7Orhbxr`, `eg5kmeo4`, `c97S64ac` |
| 28 | `out` | `jonesdevelopment/sonar` / `complex` | `scoc`, `zcxk`, `yks`, `ypby`, `pxyn` |
| 29 | `out` | `jonesdevelopment/sonar` / `legacy` | `namz`, `dpkh`, `hax`, `mooe`, `btx` |
| 30 | `out` | `jonesdevelopment/sonar` / `standard` | `foj`, `uzhn`, `fdjj`, `ksp`, `jpy` |
| 31 | `out` | `just-captcha/ProstoCaptcha` / `map` | `tGbMyw`, `UPkV6q`, `pT7ADf`, `Mg2K49`, `JJ9QTA` |
| 32 | `out` | `laforetbrut/are-you-sure` / `code` | `AJQM6P`, `ZSHDP9`, `69XR2K`, `JFJVA3`, `5JQLDW` |
| 33 | `out` | `n1zamu/NCaptcha` / `anvil` | `28612`, `6319`, `9096`, `26321`, `57250` |
| 34 | `out` | `ringoame196-s-mcPlugin/ReproductionCAPTCHA` / `map` | `F2311`, `D9F60`, `12AA0`, `8235A`, `F39ED` |
| 35 | `out_ru` | `BotFilter` / `map` | `67726`, `5742`, `41378`, `6807`, `3893` |
| 36 | `out_ru` | `CaptchaGUI` / `clickblock` | `1`, `3`, `6`, `7`, `6` |
| 37 | `out_ru` | `CaptchaVerifyZ` / `map` | `MIKA6`, `XA8FT`, `LI7X3`, `TUAEL`, `VEXI6` |
| 38 | `out_ru` | `GalleryCaptcha` / `ru-numberword` | `825`, `287`, `701`, `459`, `881` |
| 39 | `out_ru` | `GalleryCaptcha` / `ru-numberword-caption` | `417`, `165`, `874`, `113`, `467` |
| 40 | `out_ru` | `GalleryCaptcha` / `ru-object-swatch` | `жёлтый`, `белый`, `чёрный`, `красный`, `зелёный` |
| 41 | `out_ru` | `GalleryCaptcha` / `ru-symbols` | `ХФЩ`, `РЧИ`, `2ФЁ`, `ЪПЮ`, `Ы0О` |
| 42 | `out_ru` | `GalleryCaptcha` / `ru-web` | `DpZ7D`, `UMT6u`, `KWNta`, `HV3UI`, `qOWJW` |
| 43 | `out_ru` | `LimboFilter` / `framed2x2` | `638`, `560`, `621`, `576`, `243` |
| 44 | `out_ru` | `LimboFilter` / `framed3x3` | `287`, `375`, `639`, `482`, `778` |
| 45 | `out_ru` | `LimboFilter` / `map` | `901`, `961`, `766`, `330`, `217` |
| 46 | `out_ru` | `LimboFilter` / `symbols` | `ЪМИ`, `СБД`, `О5Д`, `4ПЪ`, `Ъ0Ю` |

Картинки скопированы из сгенерированного датасета **дословно** — это те же PNG,
что лежат в `dataset/out/` и `dataset/out_ru/`, без перерисовки и сжатия.
