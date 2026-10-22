# REVIEW_RESEARCH — fact-check of the Russian / GalleryCaptcha-type research reports

---

> **ADR 0003 — Как мы идентифицируем плагины и что делаем, когда апстрим не найден.**
>
> - **Дата:** 2026-10-22 · **Статус:** принято · **Решение автора проекта:** владелец
> - **Контекст:** этот документ — факт-чек исследований по русским плагинам и типам группы GalleryCaptcha.
>   Найдено 14 неподтверждаемых утверждений (F1-F14) и 7 противоречий (C1-C7); часть исправлена
>   в тот же день, часть — нет.
> - **Решение:** **никогда не выдумывать источник.** Если апстрим не найден — писать «не найдено» и
>   помечать реконструкцию (`reconstructed`), вести её по эталонным скриншотам; если лицензия не
>   позволяет копировать — делать `clean-room` с нуля; если лицензия позволяет — `faithful` с
>   указанием `класс#метод` в `source()`. Веб-архив — источник доказательств (так найден FAQ
> - **Последствия:** в `labels.jsonl` у каждой строки есть поле `source` — это аудит-трейл.
>   Спорные утверждения остаются помеченными, а не «исправленными по догадке».

**Reviewer:** fact-check pass over the research documents and the generators they describe.
**Audit window:** 2026-10-21, 18:03–18:25 (local, Asia/Yekaterinburg).
**Audited document versions** (SHA-256 prefix / mtime):

| File | sha256[:16] | mtime |
|---|---|---|
| `reports/SITE_CAPTCHAS.md` | `2B82CCAEA27DB831` | 2026-10-21 18:05:22 |
| `reports/PUZZLE_OBJECT_FAMILIES.md` | `A4F7F23B6122D0CB` | 2026-10-21 17:48:26 |
| `reports/RU_PLUGINS_CAPTCHA_VERIFYZ_SMARTCAPTCHA.md` | `EE1CFE8B0633B6DF` | 2026-10-21 17:28:37 |
| `research/RU_CAPTCHA_SOURCES.md` | `4F8E297541A898DE` | 2026-10-21 17:34:51 |
| `dataset/out_ru/SmartCaptcha/README.txt` | `F5ED98D711BC1583` | — |
| `dataset/out_ru/WeatherActionCaptcha/real_shots/README.txt` | `63D0F8861C8F4163` | — |

> **Note on concurrent edits.** `reports/SITE_CAPTCHAS.md` was rewritten at 18:05:22, *during* this
> audit (it grew from 388 to 431 lines; a new §3.4 and §3.5 were added). All line references below are
> against the 431-line version. `dataset/out_ru/BotFilter/real_shots/` was **created at 18:19:11**, also
> during the audit — it did not exist when I first checked at ~18:08 — and the whole of
> `dataset/out_ru/` was regenerated at least once while I worked (so the *file names* of the samples
> mentioned in C6 change on every rebuild; the counts do not). Findings that depend on those states
> are flagged with the timestamp.

**Nothing was modified.** The only file written by this review is this one. All scratch work is under
`build/audit/` (compiled classes, jar downloads, image crops, measurement scripts). `research/`,
`dataset/`, `reports/` (other than this file) and `site/` are untouched.

---

## Status of this review (added later, the findings above are unchanged)

This audit ran on 2026-10-21 between 18:03 and 18:25, against a tree that has moved on since. The
findings are kept as they were written; each one is annotated below with what has happened to it.
Every finding of the first group (F1-F14) and of the second (C1-C7) was **acted on** - that is what
the current `reports/SITE_CAPTCHAS.md` and `reports/PUZZLE_OBJECT_FAMILIES.md` show. What has changed
since then is the dataset itself:

| finding | state |
|---|---|
| **F1** "6 coal blocks" | **fixed** - `reports/SITE_CAPTCHAS.md` §7.4 now says plainly that no count of blocks and no coal is claimed |
| **F2**, **F3**, **F4** the nearest-neighbour example and the V2 median | **fixed** - the table and the example in `reports/SITE_CAPTCHAS.md` §4 are the corrected ones |
| **F5** "the swatches were JPEG-encoded before tiling" | **fixed** - `reports/PUZZLE_OBJECT_FAMILIES.md` §3.3 now says the grid was JPEG-encoded **after** the cells were drawn, with the measurement |
| **F6** the "128-entry" map palette | **fixed** - `research/RU_CAPTCHA_SOURCES.md` now says 144 entries |
| **F7** the SmartCaptcha config block | **fixed** - `reports/RU_PLUGINS_CAPTCHA_VERIFYZ_SMARTCAPTCHA.md` carries the upstream values, with the real item and the decoy the right way round |
| **F8** "byte-identical across versions" | **fixed** - both documents now say the *bytecode* is identical and that the class files differ only in the line-number table |
| **F9** "No generator has been written for BotFilter yet" | **fixed** - the generator exists and ships 100 samples |
| **F10** "800 images, 8 captcha types" | **fixed, and the correction is now stale too**: `dataset/out_ru/` holds **12 types x 100 = 1200** images |
| **F11** "each folder holds `real_shots/`" | **fixed** - every reserved folder has one, and each carries a `README.md` |
| **F12**, **F13** the Goku description and the socket | **fixed** in `reports/PUZZLE_OBJECT_FAMILIES.md` §2.5 and §3.2 |
| **F14** the "no generator" labels for `ru-puzzle*` | **obsolete** - the `ru-puzzle*` types and `PuzzleCaptcha.java` are gone |
| **C1** the puzzle family's base image | **resolved** - the base art is natively 250x150; the family itself is now LimboFilter's `FRAMED_CAPTCHA` |
| **C2** the `Supl1n` generator label | **fixed** - the javadoc now says clean-room |
| **C4** `tools/glyphs.py` picking the wrong mask | **fixed** - the tool now matches the version number exactly |
| **C5** the `WebCaptcha` rotation comment | **obsolete** - the code is gone |
| **C6** 12/100 `ru-object-swatch` samples without the answer colour | **fixed** - the target is the minority colour that is in the grid |
| **C7** the `AGENTS.md` BotFilter figures | **fixed** - `AGENTS.md` now quotes the measured numbers (13.0 vs 13.5 colours, 41.6 % vs 41.3 % coverage, 121x110 vs 120x108) |

The dataset has also grown: `dataset/out_ru/` is now **12 types x 100 = 1200** images, the two
`ru-puzzle*` types are gone, the reference inventory is **1240** images, and `labels.jsonl` carries
the two new fields `text` and `roi`.

---

## 0. Summary

The research is, on the whole, **careful and largely accurate**: I re-derived almost every upstream
algorithm from the live sources and it matches line-for-line, and I reproduced the pixel measurements
exactly. The documentation habit of "the jar was not obtainable, the claim rests on the README" is
honest and is repeated where it matters.

What I did **not** find: any invented GitHub URL, any invented method name, any fabricated upstream
source location. Every plugin the reports name exists where they say it does.

What I **did** find, in order of importance:

1. Two numbers in a published table are wrong (the V1 #275 nearest-neighbour example; the V2 median).
2. One "measured" pixel claim is exactly reproducible — but only because the helper script has a
   substring bug that selects the wrong ink mask.
3. A substantive contradiction about what the puzzle family's *base image* is, between
   `research/WEB_CAPTCHA_V6_FINDINGS.md`, `reports/PUZZLE_OBJECT_FAMILIES.md`,
   `reports/SITE_CAPTCHAS.md` and the generator `WebCaptcha.java`.
4. A wrong statement about when the V8 swatches were JPEG-encoded ("before tiling" — it was after).
5. A swapped pair of config values in a block presented as a verbatim upstream quote.
6. "Byte-identical across versions" is false as written (the class files differ), true at the
   bytecode level; and "1.2 is the fat jar" is misattributed (1.0/1.1/1.2 are all fat jars).
7. Two claims that the repo state does not support: "No generator has been written for BotFilter yet"
   (one exists, with 100 samples) and "800 images, 8 captcha types" (it is 1000 images, 10 types).
8. Two real defects in the *generators*, found by auditing against the references: the puzzle
   rotation produces black-padded, clipped tiles, and 12/100 `ru-object-swatch` samples have an
   answer colour that is not in the image at all.
9. One detail in the reports ("6 coal blocks") that no evidence in the repo or upstream supports.

---

## 1. Fabricated or unverifiable claims

### F1 — "6 coal blocks" is not supported by any evidence (unverifiable)

*Document:* `reports/SITE_CAPTCHAS.md:280`
> "and has to break 6 coal blocks, use a crafting table or use an enchanting table within a
> time limit shown on a boss bar (`У вас есть N секунд, чтобы войти.`)."

**Truth.** The upstream page says only *"в котором будут нужные блоки, по типу верстака для крафта
или стола зачарования"* — "in which there will be the needed blocks, for example a crafting table
or an enchanting table". It says nothing about coal, and nothing about a count of 6.
The two frames kept as evidence do not show coal blocks either:
`dataset/out_ru/WeatherActionCaptcha/real_shots/yt_62jp1hEeSFk.png` is a promo title card (a small
world with a crafting table, an enchanting table, a chest and a furnace), and
`yt_a3_VRVRGuEc.png` is a **NeoWare 2.3.0 bot-client debug overlay** on `play.reserv.fun` with the
boss bar reading *"У вас есть 48 секунд, чтобы войти."* — i.e. the *attacker* side, not a player
doing the action. A repo-wide grep for `coal|уголь` finds exactly one hit: the sentence above.
**The "6 coal blocks" detail is unsupported; drop it or cite where it came from.**

### F2 — the worked nearest-neighbour example is misattributed (wrong fact)

*Document:* `reports/SITE_CAPTCHAS.md:162-164`
> "Example: site V1 #275 is Cyrillic `ЬЯШНИ` in a blackletter face on cream; its nearest neighbour
> is `irootdev/AnBot/captcha` (`eth` in blue italic on white), at 0.0231."

**Truth.** The *image* description is correct — I opened `site/captchas/s00_…_V1/275.png` and it is
Cyrillic blackletter on cream. The *nearest neighbour* is wrong. From `site/site_matches.json`:

```
V1/275.png  best: jonesdevelopment/sonar/complex      0.0282
               InstantlyMoist/Captcha/textcaptcha      0.0297
               InstantlyMoist/Captcha/textcaptcha      0.0307
```

`irootdev/AnBot/captcha` at **0.0231** is the neighbour of **V1.1 #015** and **V2 #001**, not of
V1 #275. The 0.0231/irootdev pairing is real — it is just attached to the wrong sample.

### F3 — the parenthesis naming the false-positive types is also wrong

*Document:* `reports/SITE_CAPTCHAS.md:160-161`
> "Only a handful of site images reach that, and **every one of them was checked by eye and is a
> false positive** — a white background with sparse dark text (`irootdev/AnBot`, `InstantlyMoist`,
> `jonesdevelopment/sonar`) matches almost any other white-background-with-text image at 16×16."

**Truth.** Exactly **three** images in the whole 525-image catalogue reach ≤ 0.025, and their
top-1 neighbours are:

| section | file | nearest neighbour | dist |
|---|---|---|---|
| V1 | 136.png | `Mrbysco/Captcha/math` | 0.0228 |
| V1.1 | 015.png | `irootdev/AnBot/captcha` | 0.0231 |
| V2 | 001.png | `irootdev/AnBot/captcha` | 0.0231 |

`InstantlyMoist` and `jonesdevelopment/sonar` are never the top-1 neighbour of a ≤0.025 image
(they appear in the lists of the 0.028–0.031 images, e.g. V1 #275). `Mrbysco/Captcha/math` — the
actual V1 false positive — is not in the list.

### F4 — one row of the distance table does not reproduce

*Document:* `reports/SITE_CAPTCHAS.md:150` — `| V2 | 0.023 / 0.105 |`

**Truth.** Recomputed from `site/site_matches.json`: V2 min **0.0231** ✓, median **0.0980** ✗
(claimed 0.105). Every other row reproduces to within rounding (V1 0.0228/0.1230, V1.1
0.0231/0.0854, V3 0.0303/0.0977, V4 0.0781/0.1502, V5 0.0332/0.1332, V52 0.0562/0.0562,
V53 0.0900/0.1089, V6 0.0304/0.0919, V8 0.1042/0.1920). Note 0.098 is **V3's** median — this looks
like a row shift or a copy slip. If the table was computed against a different `dataset/out` state,
that should be stated.

### F5 — "the swatches were JPEG-encoded before tiling" is backwards

*Document:* `reports/PUZZLE_OBJECT_FAMILIES.md:107-108`
> "with JPEG-style ringing at the cell edges (`#01FE00` ×166, `#F00F00` ×166, `#0FF000` ×164,
> `#FB0400` ×100 …) — **the swatches were JPEG-encoded before tiling**."

**Truth.** The pixel counts are exactly right (I reproduce `#01FE00`×166, `#F00F00`×166,
`#0FF000`×164, `#FB0400`×100 in `s10/…/008.png`), but the *ordering* is wrong. I measured where the
ringing actually is:

* In `008.png` all 596 ringing pixels lie on a cell seam, and **none** lies on a seam where the two
  sides have the *same* fill. The horizontal seam at y=50 carries ringing in exactly 166 of its 250
  columns — which is precisely the 83+83 columns where the row-0 and row-1 fills differ
  (green|red on the left, red|red in the middle, red|green on the right).
* The same holds for `011.png` (1836 ringing px) and `012.png` (1102 ringing px): **100 %** of the
  non-swatch pixels are on a colour-change seam, **0 %** on a same-colour seam.

If the swatches had been JPEG-encoded *individually* and then tiled, **every** swatch edge would
ring, including the red|red edges. It does not. The **grid** was JPEG-encoded as one image, i.e.
**after** tiling — which is what `dataset/generator_ru/dev/captcha/gens/ObjectCaptcha.java:107-110`
implements ("the swatch **grid** is JPEG-encoded before it is handed on"). The generator is right;
the report sentence is wrong.

### F6 — `MapPalette.colors` is 144 entries, not 128

*Document:* `research/RU_CAPTCHA_SOURCES.md:128-129`
> "`MapPalette.colors` is the standard **128-entry** Minecraft map palette (indices 0-3 are the four
> black shades used for transparency, 4-127 the real colours)"

**Truth.** The upstream array has **144** entries: 4 blacks + 35 rows of 4. I extracted the array
from the live `MapPalette.java` and compared it entry-by-entry with the generator's `MAP_PALETTE`
(`BotFilter.java:97-134`): **144 vs 144, 0 mismatching entries — the palettes are identical.**
The document's own quoted formula `byte index = (byte) ( i < 128 ? i : -129 + ( i - 127 ) )` is
meaningless for a 128-entry array, which is the tell. `BotFilter.java:59-63` states "144 entries"
correctly. The "128-entry" sentence is the wrong one and should be corrected (or the two
documents reconciled).

### F7 — the SmartCaptcha `config.yml` block is not a verbatim quote, and swaps real/fake

*Document:* `reports/RU_PLUGINS_CAPTCHA_VERIFYZ_SMARTCAPTCHA.md:248-273` (introduced at 231-232 as
"The upstream README — recovered in full from the base64 `description` field of the Spiget API —
**states verbatim**").

I decoded that base64 field myself (Spiget `GET /v2/resources/70935` → `description`, 6160 chars
base64). The upstream config is:

```yaml
fail-kick-msg: "&cYou've been kicked from the server because you failed the captcha. Please try again."
captcha-real-item: "&aClick here!"
captcha-fake-item: "&cDon't click here!"
authentication-msg: "&aYou've been successfully authenticated after passing the captcha test!"
no-permissions-msg: "&cYou haven't &ecaptcha.* &cpermission, so you can't perform this command."
```

Differences from the document:

| document | upstream | problem |
|---|---|---|
| `captcha-real-item: 0 0 "&cDon't click here!"` (line 262) | `captcha-real-item: "&aClick here!"` | **the real and fake item names are swapped** |
| `captcha-fake-item: ... "&aClick here!"` (line 263) | `captcha-fake-item: "&cDon't click here!"` | ditto |
| `0 0` and `...` prefixes | — | **invented**; the upstream values are plain strings |
| bare string, no key (line 256) | `fail-kick-msg:` | key dropped |
| `"&c9o've been kicked…"` (line 256) | `"&cYou've been kicked…"` | garbled |
| bare string, no key (line 266) | `authentication-msg:` | key dropped |
| `"&yYow'fR been successfully authenticated…"` (line 266) | `"&aYou've been successfully authenticated…"` | garbled |
| `"&cYou've haven't &ecaptcha.* &permission…"` (line 272) | `"&cYou haven't &ecaptcha.* &cpermission…"` | garbled |
| "…only after your authmentication." (line 238) | "…only after your authme authentication." | mis-transcribed in a block labelled *verbatim* |

The **narrative** in `reports/SITE_CAPTCHAS.md:253-258` is nonetheless correct: the upstream README's
"CAPTCHA EXAMPLE — By clicking on the item displayed at the top, you will be authenticated." plus
"Disclaimer: The ice block can be another random block, the same for the arrow" do support
"the real item is the arrow, the decoys are ice". Only the quoted YAML is wrong. The same swapped
pair does **not** appear in `dataset/out_ru/SmartCaptcha/README.txt`, which only names the keys.

### F8 — "byte-identical across versions" is false as written

*Document:* `reports/SITE_CAPTCHAS.md:248-249`
> "The renderer is byte-identical across versions 1.0, 1.2, 1.3 and 1.4, so one reimplementation
> covers every release."

*Document:* `reports/RU_PLUGINS_CAPTCHA_VERIFYZ_SMARTCAPTCHA.md:135-136`
> "The `CaptchaMapRenderer` body is **byte-identical in every published version** checked: 1.0, 1.2,
> 1.3, 1.4 (1.2 differs only by an added `@Override` annotation and a shaded fat-jar)."

**Truth.** I downloaded all six published jars from Modrinth and hashed
`com/Mateitaa1/CaptchaVerifyZ/CaptchaVerifyZ$CaptchaMapRenderer.class`:

| version | Modrinth id | class bytes | SHA-256 | jar entries / classes |
|---|---|---|---|---|
| 1.0 | `WCkVoozh` | 2107 | `11a65377…` | 4978 / 4669 |
| 1.1 | `SAOTcyc0` | 2107 | `77eb453f…` | 4978 / 4669 |
| 1.2 | `zAd3D2fe` | 2107 | `06c8d237…` | 4978 / 4669 |
| 1.3 | `SqWTH117` | 2107 | `68e6792e…` | 15 / 3 |
| 1.4 | `2vquPhCa` | 2107 | `b915d20d…` | 15 / 3 |
| 1.4-2 | `dHdoDcmQ` | 2107 | `ed746a2a…` | 15 / 3 |

The class files are **not** byte-identical in any pair. The difference is confined to the
`LineNumberTable`: `javap -v` diffs of 1.0/1.1/1.2/1.3/1.4/1.4-2 show **only** `line NNN: X` entries
differing, and `javap -p -c` output is **identical for all six**. So the accurate statement is
*"the renderer's **bytecode** is identical across every published version (1.0, 1.1, 1.2, 1.3, 1.4,
1.4-2); only the source line-number table differs."*

Two sub-claims also need fixing:
* **"1.2 differs … by … a shaded fat-jar"** — 1.0, 1.1 **and** 1.2 are all shaded fat jars
  (4978 entries / 4669 classes); 1.3, 1.4 and 1.4-2 are the slim ones (15 entries / 3 classes).
  Fat-jar-ness is not what distinguishes 1.2.
* **"an added `@Override` annotation"** — `javap -v` shows no annotation difference between 1.2 and
  1.4 either; the only delta is the line-number table.
* `reports/SITE_CAPTCHAS.md:226` ("the jar is 3 classes plus `config.yml` and `plugin.yml`") is
  true of 1.3/1.4/1.4-2 and false of 1.0/1.1/1.2 (4669 classes). It is fine as a statement about
  the current release, but should say which release.

### F9 — "No generator has been written for BotFilter yet" is false

*Document:* `reports/SITE_CAPTCHAS.md:348-350`
> "**No generator has been written for BotFilter yet** — the algorithm above is fully specified, so it
> can be implemented directly…"

**Truth.** `dataset/generator_ru/dev/captcha/gens/BotFilter.java` (467 lines) exists, and
`dataset/out_ru/BotFilter/map/` holds 100 generated samples with `labels.jsonl` whose `source` is
`ru.leymooo.botfilter.captcha.generator.CaptchaPainter#draw`. The statement is stale — it also
contradicts `AGENTS.md` §6. (The generator itself is good: see §5.)

### F10 — "`dataset/out_ru/` (800 images, 8 captcha types x 100)" is stale

*Document:* `reports/SITE_CAPTCHAS.md:410` and the 8-row table at 412-421.

**Truth.** There are **10** captcha types and **1000** generated PNGs (excluding `real_shots/`):
`GalleryCaptcha/{ru-numberword, ru-numberword-caption, ru-object-swatch, ru-puzzle2x2, ru-puzzle3x3,
ru-symbols, ru-web}` + `BotFilter/map` + `CaptchaGUI/clickblock` + `CaptchaVerifyZ/map`. The table
is missing the `ru-object-swatch` and `BotFilter/map` rows. (`AGENTS.md` already says 10 × 100.)

> **Since then (2026-10-21, later the same day): the correction is stale too.** The tree now holds
> **12 types x 100 = 1200** PNGs: the two `ru-puzzle*` types were deleted (the model behind them was
> wrong) and the plugin's own `LimboFilter/{map,symbols,framed3x3,framed2x2}` took their place.

### F11 — "Each folder holds `real_shots/`" is not true of three of the six

*Document:* `reports/SITE_CAPTCHAS.md:195-198`

**Truth** (state as of 18:21):

| folder | `real_shots/` | contents |
|---|---|---|
| `GalleryCaptcha/real_shots/` | present | 722 PNGs in 8 sub-dirs, **no README** |
| `BotFilter/real_shots/` | **created 18:19:11, during this audit** | 510 PNGs, **no README** |
| `Captcha/real_shots/` | present but **empty** (0 files) | — |
| `CaptchaGUI/real_shots/` | **does not exist** | — |
| `CaptchaVerifyZ/real_shots/` | present | 5 PNGs, **no README** |
| `SmartCaptcha/real_shots/` | present but **empty** (0 files) | — |
| `WeatherActionCaptcha/real_shots/` | present | 2 PNGs + `README.txt` ✓ |

The only README-ish files under `dataset/out_ru/` are `SmartCaptcha/README.txt` and
`WeatherActionCaptcha/real_shots/README.txt`. In particular
**`reports/SITE_CAPTCHAS.md:347` — "(see the `README.md` there)" — points at a file that does not
exist** in `dataset/out_ru/BotFilter/real_shots/`. Either add it or drop the cross-reference.

### F12 — the V4 "Goku" description does not match the image

*Document:* `reports/PUZZLE_OBJECT_FAMILIES.md:49-51`
> "The Goku cutout on a flat green field has the sprite's pieces in the middle column and the flat
> field in the outer columns"

**Truth.** In `site/captchas/s04_API_V4_Пазл_капчи/005.png` the sprite fragments (hair, an eye and
face, hands, a blue/white body) are in **all nine cells**; the flat `#146032` field is in the outer
columns *and* in parts of the middle column. The "middle column vs outer columns" reading is not
supported by the picture. (The adjacent claim — "a 150×90 downscale of `s04/027.png` shows a
rectangular block that does not belong to its surroundings" — **is** correct; I rendered the
downscale and the discontinuity is obvious.)

### F13 — minor: the socket is in the cell, the *photo* is what spills over

*Document:* `reports/PUZZLE_OBJECT_FAMILIES.md:95-96`
> "`s10/004.png` cell (1,1) is a high-key photo of a pale wall with a white socket; the socket
> continues into cell (2,1) — one photo spanning two rows."

**Truth.** The pale-wall photo does span (1,1) and (2,1) ✓, but the white socket itself sits in
(1,1); it is the photo, not the socket, that continues. One clause to reword. (Note the documents use
(row, column) ordering for cells while `tools/crop_grid.py` labels them (col,row) — worth stating
the convention once.)

### F14 — the "no generator" labels for `ru-puzzle*` do not match the generator's own claim

`dataset/generator_ru/dev/captcha/gens/WebCaptcha.java:37-39` says "the tiles are permuted"; the
rotation was added later (lines 279-296) with the comment
> "Each tile is also rotated by a random multiple of 90 degrees. This is proven by the reference
> samples: one 3x3 tile holds the Minecraft logo upside down and three adjacent tiles of another
> sample carry text at 180, 90 and 0 degrees."

I **confirmed** both of those proofs (§5, §5.3). But `reports/SITE_CAPTCHAS.md:70` and `:375-376`
still describe the puzzle as *only* permuted, and `reports/PUZZLE_OBJECT_FAMILIES.md:143-145`
lists the rotation as a *recommendation for the future* ("add the two facts the reference images
prove … (1) tiles are **rotated** by a random multiple of 90°") although the generator already does
it. The two documents are out of step with each other and with the code.

---

## 2. Contradictions between documents, or between a document and the code

### C1 — **what is the puzzle family's base image? (the biggest one)**

| source | claim |
|---|---|
| `reports/PUZZLE_OBJECT_FAMILIES.md:14-16` | "The **puzzle** family (V4, V5, V52, V53) is a **composite of the generic 150×90 web captcha** that is already in the catalogue as section V6" |
| `reports/PUZZLE_OBJECT_FAMILIES.md:36-41` | "### 2.2 The base is a 150×90 web captcha … 150 → 250 is exactly 5/3, i.e. a plain scale of the base render." |
| `reports/SITE_CAPTCHAS.md:74-75` | "**V5 / V53**: the *web-captcha* art from V6, scaled to 250×150, then tiled. So V5 is literally 'V6 image, cut into 3×3'…" |
| `reports/SITE_CAPTCHAS.md:178, 180` | V5 / V53 → "composite of the V6 renderer" · "**composite, certain**" |
| `reports/SITE_CAPTCHAS.md:133-136` (new §3.5) | "One question is still open … whether the base art is a 150×90 captcha scaled up by 5/3 … or natively 250×150 art, and whether any tile matches one of the 70 V6 samples specifically — **it does not** (mean absolute error never drops below ~30)" |
| `research/WEB_CAPTCHA_V6_FINDINGS.md:89-97` | "The V5/V53 source pictures are **250×150 web-captcha art** … *not* the 150×90 V6 samples — no V5 or V53 tile matches any of the 70 V6 images … the base image is a 250×150 web captcha, **not one of the 150×90 V6 samples**" |
| `dataset/generator_ru/dev/captcha/gens/WebCaptcha.java:241-246` | renders a **150×90** base and upscales it 5/3 to 250×150 — i.e. implements the model the research doc refutes |

**What I measured.** I re-ran `research/puzzle_check.py` (which cuts each puzzle on exact thirds and
looks for a tile-by-tile match against the 70 V6 samples):

```
V5 3x3 : 13 puzzles → 001..013  <- NO MATCH in s08   (all 13)
V53 2x2:  7 puzzles → 001 <- 008.png meanAbsErr=32.02 ; 002 <- 025.png 78.37 ;
                           003 <- NO MATCH ; 004 <- 026.png 74.22 ;
                           005 <- 060.png 31.00 ; 006 <- 009.png 47.48 ;
                           007 <- 060.png 36.21
```

The V5 rows are unambiguous ("NO MATCH"). The V53 rows are the *best available* candidates, printed
because the cell mapping is distinct, but their errors (31–78) are far above the tool's own 12
threshold and 8–10× the "match" error of a true match — i.e. **no V53 tile matches a V6 sample
either**. I also opened `research/reassembled/V53_007.png`: it is a **250×150** teal/flame artwork
with the text "31", exactly as `WEB_CAPTCHA_V6_FINDINGS.md:85-87` describes — a 250×150 base, not a
150×90 one upscaled.

And the 5/3 lattice test: in `s05/002.png`, **99.72 %** of pixels differ from the value at the
origin of their 150→250 block (same for 001/004; 90.6 % for the V4 artwork sample, 52.5 % for the
V53 sample). A nearest-neighbour 5/3 upscale would be *piecewise constant* on that lattice. (The
per-tile rotation is a confound — it destroys the lattice inside rotated tiles — but the reassembly
evidence is independent and points the same way.)

**Verdict.** "V5/V53 = the 150×90 V6 samples scaled up" is **not supported**; the base is a
250×150 web-captcha sub-family. The new §3.5 of `SITE_CAPTCHAS.md` already hedges this correctly;
§3.2, §5 and `PUZZLE_OBJECT_FAMILIES.md` §1/§2.2 and the generator still assert the old model.
"composite, certain" (§5) is too strong either way — the correct confidence is "composite of *some*
web-captcha renderer, base not identified".

### C2 — `SUPL1N` generator label vs. the report's label

* `reports/SITE_CAPTCHAS.md:421` — `CaptchaGUI/clickblock` … "**clean-room**"
* `dataset/generator_ru/dev/captcha/gens/Supl1nCaptchaGui.java:13` — "**Faithful** reimplementation
  of Supl1n/CaptchaGUI"

`AGENTS.md` §5 defines *faithful* as a line-by-line re-implementation and *clean-room* as an
independent rewrite; the repo has **no licence** for `Supl1n/CaptchaGUI` (LICENSE, LICENSE.md,
LICENSE.txt, COPYING, README all 404; no licence badge on the GitHub page), so the house rule
requires clean-room. The code *is* an independent rewrite (no upstream identifiers, no `okay` list,
`getRandomNumberInRange(1,7)` re-implemented as `1 + r.nextInt(7)`), so the **report's** label is
the correct one and the javadoc is mislabelled. Change the javadoc, not the report.

### C3 — two of the "no image" plugins' evidence is weaker than the report's summary

`reports/SITE_CAPTCHAS.md:209` says WeatherActionCaptcha's GitHub repo "is **404 - account deleted**".
The GitHub API confirms the **account** is gone (`/users/verylovemetal` → 404, no redirect), and the
spigotmc.ru page still links to the old URL, so "deleted" is the best-supported reading — but a
renamed account is formally indistinguishable from a deleted one and I could not rule it out
(§6). The doc's phrasing is fine as long as the *evidence* is what is quoted: "the user no longer
exists and the repo 404s".

### C4 — `tools/glyphs.py` picks the wrong ink mask for the V53 section

`tools/glyphs.py` selects the mask with

```python
red if "V5" in rel or "3x3" in rel else pink
```

`"V5" in "s07_API_V53_Латинские_Цифры_2x2_пазлы"` is **True** (substring!), so the V53 section is
analysed with the *red* mask, not the pink one. That is why `reports/PUZZLE_OBJECT_FAMILIES.md:64`
reports **1029** ink px for `s07/001.png` — with the *pink* mask the same image gives **1651**, and
the exact `#D06D8E` count is 571. The reported number is therefore reproducible **only** through the
buggy path. I reproduced 1029 exactly by running the red mask, so the number in the report is not
fabricated — but the tool is misleading and the report should say which mask produced it.

### C5 — `WebCaptcha.java`'s rotation comment contradicts its own code, and the output does not match the references

`dataset/generator_ru/dev/captcha/gens/WebCaptcha.java:279-296`:

```java
int quarter = r.nextInt(4);
if (quarter == 0) { …normal blit… }
else {
    BufferedImage cell = Img.rgb(dw, dh);       // <- black-filled
    cg.setClip(0, 0, dw, dh);                    // <- clips
    cg.rotate(quarter * Math.PI / 2);
    cg.drawImage(base, -sw/2, -sh/2, sw/2, sh/2, sx, sy, sx + sw, sy + sh, null);
}
```

The comment says "A quarter turn is drawn into the cell and clipped, so a turned tile **overflows**
its cell exactly as a real jigsaw piece would" — but `setClip` means it is *cut off*, not
overflowing. Worse, the destination rectangle is `sw×sh` (83×50); rotated by 90° it occupies
50×83 inside an 83×50 cell, so a quarter-turned tile keeps only ~50×50 of its content and the
remaining ~40 % of the cell is **black padding** (`Img.rgb` gives a black fill).

The reference samples show the opposite: in `s05/002.png` the bottom row is three full tiles at
0°, 90° and 180°, with **no black bars**; in `s04/003.png` cell (2,2) is a complete upside-down
Minecraft logo. I rendered the project's own `ru-puzzle3x3` output and the black bands are plainly
visible in the quarter-turned cells. **The generated puzzles do not look like the references.**
This is a generator defect, not a report defect — but the report's §2.3 presents the rotation as a
proved fact and the dataset does not implement it faithfully.

### C6 — `ObjectCaptcha.java` produces 12/100 samples whose answer colour is not in the image

`dataset/generator_ru/dev/captcha/gens/ObjectCaptcha.java:90-102` draws the target index and the
per-cell fill indices independently from the same `Random`, so the target colour is absent from the
grid with probability 1 − (4/5)⁹ ≈ 12.6 %. Measured over the published
`dataset/out_ru/GalleryCaptcha/ru-object-swatch/`: **12 of 100** samples have an answer colour that does
not appear in the image (e.g. a prompt of "Нажмите на клетку цвета жёлтый" over an image with no
yellow cell at all). The count is stable — I measured it twice, on two different regenerations of
the set — but the *file names* differ each time, because `Gen` re-randomises every sample. The
prompt then names a colour the player cannot find. This directly contradicts `AGENTS.md` §6 ("its
ground truth is fully determined") and `reports/PUZZLE_OBJECT_FAMILIES.md:103-108`.

Two related fidelity gaps: every reference flat sample uses exactly **two** colours (target +
distractor) and has 14–30 distinct colours after JPEG, whereas the generator emits a median of
~**710–730** distinct colours (range 324–950) because it draws from 5 colours independently and
JPEG-encodes the whole grid at ImageIO's default quality. The reference samples' *target* is a
single cell among eight of one distractor colour.

### C7 — `AGENTS.md`'s BotFilter distribution figures (context, not in scope)

`AGENTS.md` §6 says the generator "matches the 510 real upstream renders in distribution (median
distinct colours 13 vs 13, ink coverage 41.0 % vs 41.6 %, ink bbox 120x111 vs 121x110)". I measured
(ink = everything that is not near-white):

| | distinct colours (median) | ink coverage (median) | ink bbox (median) |
|---|---|---|---|
| 510 real | **13.0** ✓ | **41.6 %** ✓ | **121×110** ✓ |
| 100 generated | 13.5 | 41.3 % (doc 41.0) | 120×108 (doc 120×111) |

The *real* side reproduces exactly; the *generated* side differs in the last digit of two figures and
is definition-sensitive. Not a defect, but the numbers are not exactly reproducible as stated.

> **Since then (2026-10-21, later the same day): fixed.** `AGENTS.md` §6 now quotes the measured
> numbers - median distinct colours **13.0 (real) vs 13.5 (generated)**, ink coverage **41.6 % vs
> 41.3 %**, ink bbox **121x110 vs 120x108** - and the caveat about the reference set being the
> pre-quantisation render is written down in the same place.

---

## 3. Broken or dead URLs

I extracted all **75** unique URLs from the six audited documents and fetched every one
(`build/audit/check_urls.py`, results in `build/audit/url_status.json`).

**Dead / broken (not already documented as down):**

| URL | status | used in |
|---|---|---|
| `https://github.com/Nicbo/Captcha` | **404** | `SITE_CAPTCHAS.md:362`, `RU_CAPTCHA_SOURCES.md:229, 350` |
| `https://github.com/max11-dev/Captcha` | **404** | `SITE_CAPTCHAS.md:363`, `RU_CAPTCHA_SOURCES.md:230, 350` |
| `https://source.unsplash.com/random/400x400` | **503** | `PUZZLE_OBJECT_FAMILIES.md:165` (inside a code snippet quoting `GiovanniEliasDaRosa/Image-Puzzle`) |

For the two GitHub repos I checked the GitHub API with redirects disabled: both return a plain
**404 with no `Location` header**, so they are *not* renames (a renamed repo 301s to the new path).
They are cited as the source repos of SpigotMC resources 77939 and 84509, which is what the
(Wayback-captured) SpigotMC pages said at the time — the report is faithful to its source, but the
links are now dead and should be marked as such.

The unsplash URL is quoted from another project's README, so it is illustrative, but the Unsplash
"source" endpoint no longer works.

**Down, and already documented as such (so: not findings, but they remain down):**

* every `https://www.spigotmc.org/...` URL — **HTTP 503 "We'll Be Back!"**, site-wide, including
  `/resources/70935`, `/resources/125355`, `/resources/captcha.75891/`, `/resources/319579/….jar`
  and the bare `/resources/`. The documents say this; I confirm it.
* `https://www.spigotunlocked.com/` — **403** (Cloudflare), as documented.

**Malformed (would not work even if SpigotMC were up):**

* `https://www.spigotmc.org/threads/⚑-smartcaptcha-⚑-gui-based-captcha-system-⚑.393547/`
  (`RU_PLUGINS_...:214`) and
  `https://www.spigotmc.org/resources/⚑-smartcaptcha-⚑-gui-based-captcha-system-⚑.70935/`
  (`RU_CAPTCHA_SOURCES.md:314, 357`) — the `⚑` is not percent-encoded, so a strict HTTP client
  rejects the URL (`UnicodeEncodeError` on my side). Percent-encode it (`%E2%9A%91`).

**Everything else resolves 200**, including `modrinth.com/plugin/captchaverifyz`,
the Modrinth jar, `github.com/Supl1n/CaptchaGUI`, `github.com/Leymooo/BungeeCord`,
`spigotmc.ru/resources/…3275/`, `github.com/ServerSideProject/botfilter_captcha_dataset`,
`github.com/UCRAFTS/CaptchaPlugin` and `/CaptchaService`, `github.com/eidonjoe/gm-captcha`,
`api.modrinth.com/v2/project/LbnXX4g9`, `api.spiget.org/v2/resources/{70935,125355}`,
`api.spiget.org/v2/authors/317151{,/resources}`, `cdn.spiget.org/file/spiget-resources/70935.jar`,
`mcreference.com/plugins/{captchaverifyz,smartcaptcha-gui-based-captcha-system}`,
`mcmodshub.com/mod/33953`, `raw.githubusercontent.com/...` (all five BotFilter sources),
`spigotmc.ru/{sitemap.xml,tags/kapcha/,tags/captcha/}`, `GalleryCaptcha/captchas` (302 → cookie
challenge, as documented), `mcbase.ru`, `sourcegraph.com/.api/search/stream`,
`api.modrinth.com/v2/project/e015SVoM`, `yadi.sk/d/QrSeJWeU3LAq4p`, `rubukkit.org/threads/137038/`,
`repo1.maven.org/.../cfr-0.152.jar`, and all three BotFilter forks.

**`research/SITE_CAPTCHAS.md` does not exist** — there is no second copy of the catalogue analysis
and therefore no duplication or drift to reconcile. The only other research markdown is
`research/WEB_CAPTCHA_V6_FINDINGS.md` (see C1) and `research/RU_CAPTCHA_SOURCES.md`.

---

## 4. The "no image" claims

### SmartCaptcha — the claim is honest, and the evidence is exactly as stated

`reports/RU_PLUGINS_...:290-298` ("Outstanding gap") states that the jar was never byte-inspected.
**Confirmed and I can be precise about it:**

* `https://cdn.spiget.org/file/spiget-resources/70935.jar` → **HTTP 200, `Content-Length: 0`**,
  `x-bz-content-sha1: da39a3ee5e6b4b0d3255bfef95601890afd80709` — which is exactly the SHA-1 of the
  empty string, i.e. the document's "SHA-1 of the empty string" is literally correct.
* `https://www.spigotmc.org/resources/319579/smartcaptcha-gui-based-captcha-system-1.0.jar` → 503.
* The local copy `research/jars/SmartCaptcha-70935.jar` is **0 bytes** — so it was never obtained.
* Spiget resource 70935's `file.size` is 0, `file.url` is the versioned download route, and the
  version list confirms **id 319579** is the 1.0 release (released 2020-03-22; the earliest entry
  is 2019-08-31) — the document's "319579 = Spigot file/version id" is right.

So: **the "SmartCaptcha renders no image" claim rests on the README/config evidence only.** The
README (decoded from the Spiget base64 `description`) contains no image/texture/skull/canvas/font/
charset key — the config has only `kick-after`, `fail-kick`, `fail-kick-msg`, `captcha-gui-name`,
`captcha-real-item`, `captcha-fake-item`, `authentication-msg`, `config-reload-msg`,
`no-permissions-msg`. The plugin icon is the generic Minecraft "hand" (`data/resource_icons/70/70935.jpg`
— I fetched it: a white hand on a teal square ✓). The document says this; **the claim is properly
qualified and should stay qualified.** (The only error is the swapped config values, F7.)

### WeatherActionCaptcha — same, but the report states it more loosely

`reports/SITE_CAPTCHAS.md:274-289` and
`dataset/out_ru/WeatherActionCaptcha/real_shots/README.txt`. I fetched the spigotmc.ru page live:
title "💎 WeatherActionCaptcha … **1.3**", author **Любитель Метала** (`ljubitel-metala`, id
**31915**), created **14 Mar 2025**, supported 1.16–1.21, Paper only, Java 16, "Исходный код →
`https://github.com/verylovemetal/WeatherActionCaptcha`", and the sentence *"ДАЛЬНЕЙШАЯ ПОДДЕРЖКА
ОТСУТСТВУЕТ. В МОЁМ ПРОФИЛЕ ВЫ НАЙДЁТЕ ЯДРО С КАПЧЕЙ…"* — **verbatim as quoted**.

The claim "it renders no image" rests on (a) the page text, (b) the author's own statement
(*"Так как боты научились уже обходить капчу в виде картинок перед ними и так же в руках, я решил
сделать капчу, где нужно выполнить какое то действие"* — quoted accurately), and (c) two video
frames. The jar is unobtainable (spigotmc.ru requires an account) and the source repo is 404. So the
claim **also rests on README/config/description evidence only** — the report should say so as
explicitly as it does for SmartCaptcha. Two details of the frames should be described accurately:
`yt_62jp1hEeSFk.png` is a **promo title card**, and `yt_a3_VRVRGuEc.png` is a **bot-client
(NeoWare 2.3.0) debug overlay** showing the boss bar — the attacker, not a player completing the
task. Also, the "6 coal blocks" detail is unsupported (F1).

### The puzzle / object families — the report is right that they are not plugins

`reports/PUZZLE_OBJECT_FAMILIES.md:3` ("upstream **not identified**. Both families are *web*
captchas, not Minecraft plugins") and §4's exclusion table. I did not re-run the whole search, but
every URL the table cites resolves 200 and the two candidates it names as *not* the renderer are
correct on inspection (`LofiWebCaptcha-site/index.php` does embed a Google reCAPTCHA `data-sitekey`;
`Elytrium/LimboFilter` paints onto a map). The claims that the *puzzle* family is "a web service"
and that it renders no image *itself* are consistent with everything I measured.

---

## 5. Claims I confirmed, and how

**Upstream algorithm claims (re-derived from the live sources, not from the reports):**

1. **CaptchaVerifyZ renderer** — the decompiled snippet in
   `RU_PLUGINS_...:47-80` matches the real class. I downloaded all six Modrinth jars and compared
   `javap -p -c` output of the renderer class: **identical bytecode in all six versions**; the
   128×128 `TYPE_INT_RGB` canvas, `DARK_GRAY` fill, Arial BOLD 12 header at (5,20), Arial BOLD 24
   code at `(128-width)/2, 70`, Arial PLAIN 10 footer at (15,100), no rendering hints, no assets —
   all confirmed.
2. **CaptchaVerifyZ pixel-identity** — I re-rendered the five reference codes with the project's own
   `dev.captcha.gens.CaptchaVerifyZ.Map` and pixel-diffed them against `research/refout/`:
   **0 differing pixels out of 16384 for all five**. The MD5s in
   `RU_PLUGINS_...:196-200` also match `research/refout/*.png` and `research/myout/*.png` exactly
   (`7BFE088A…`, `AB5BC8B8…`, `D3E86331…`, `9BBB8C11…`, `FEC4A267…`).
3. **CaptchaVerifyZ config** — `research/jars/cvy_x/config.yml` (2 454 bytes, i.e. the 1.4-2
   config) contains `captcha.length: 5`, `captcha.characters: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"`,
   and the `messages.welcome` / `messages.kick` / `messages.incorrect-attempt` blocks quoted at
   `RU_PLUGINS_...:146-186` **verbatim** — including `"&a&l➤ &f&l{captcha}"` and the repeated
   `messages.incorrect-attempt`. The generator `CaptchaVerifyZ.java` matches upstream on every
   parameter (canvas size, `TYPE_INT_RGB`, the three colours, the three fonts, the three
   positions, the charset literal, the length 5) and sets **no** rendering hints, like upstream.
4. **Modrinth metadata** — `api.modrinth.com/v2/project/LbnXX4g9` confirms id `LbnXX4g9`, slug
   `captchaverifyz`, `license.id = LicenseRef-All-Rights-Reserved`, `source_url = null`,
   `discord_url = discord.gg/jFvq2fdUXB`, and the version list with `dHdoDcmQ` = **1.4-2** whose
   file is `CaptchaVerifyZ-1.4.jar` — the exact URL in the reports. The jar is 15 818 bytes.
5. **BotFilter** — I fetched the four live `raw.githubusercontent.com/Leymooo/BungeeCord/master/…`
   sources and checked every numeric claim in `RU_CAPTCHA_SOURCES.md:60-199` and
   `SITE_CAPTCHAS.md:321-334` against the code: 128×128 `TYPE_3BYTE_BGR`; solid `Color.WHITE`
   background via `clearRect`; `randomAnswer()` exactly as quoted (4 digits 1000–9999 / 5 digits
   10000–99999, 50/50); the three fonts `SANS_SERIF/PLAIN/50`, `SERIF/PLAIN/50`, `MONOSPACED/BOLD/50`;
   the eight rendering hints; `randomNotWhiteColor()` rejecting exactly the six near-white entries
   listed; `rotateCur = (rnd.nextDouble()-0.5)*PI/8` (±π/16); `rotateStep = signum·(rnd.nextDouble()
   ·3·PI/8/glyphNum)` (≤3π/8) with the p = 0.25 sign flip; the spacing squeeze `rnd.nextDouble()/20
   + 0.27` (0.27–0.32); the scale `width/bw·(rnd.nextFloat()/20 + 0.89f)` and `height/bh·(… + 0.68f)`
   (89–94 % / 68–73 %); the outline offset `±width/200` (≤0.64 px) and `±height/70` (≤1.83 px);
   `outlineEnabled`/`rotateEnabled` hard-coded `true` (so the 0.92f/0.75f/0.1 branches are dead);
   the ripple amplitudes `height/10` and `width/100`; `Rippler.filter`'s
   `ny = (y + verticalDelta[x] + height) % height; nx = (x + horizontalDelta[ny] + width) % width`;
   the 3×3 `ConvolveOp` with nine `rnd.nextFloat()` weights normalised to 1 and `EDGE_NO_OP`;
   `MapPalette.getDistance`'s `weightR = 2 + rmean/256`, `weightG = 4`,
   `weightB = 2 + (255-rmean)/256` with the scan starting at index 4; `prepareColors()`'s
   `i < 128 ? i : -129 + (i-127)`; and the start-up loop `for (int i = 100; i <= 999; i++)` with
   the log line "[BotFilter] Генерирую капчу [{0}/900]" — i.e. **900** captchas.
   The method names listed at `RU_CAPTCHA_SOURCES.md:34-51` and `SITE_CAPTCHAS.md:311-319` are all
   real and correctly signed.
6. **BotFilter licence** — `https://raw.githubusercontent.com/Leymooo/BungeeCord/master/LICENSE` is the
   md_5 BSD 2-clause **plus** the exact extra clause *"You may not use the software for commercial
   software hosting services without written permission from the author."*; the GitHub API reports
   `NOASSERTION`. The repository is a fork of `SpigotMC/BungeeCord`, default branch `master`,
   `pushed_at 2026-09-29`, description "BungeeCord with built in AntiBot protection (RUS lang)".
   `github.com/Leymooo`'s profile title is "**Leymooo (Vjatšeslav Maspanov)**" — the real name in
   the reports is right. The three forks exist and their READMEs credit "Leymooo (BotFilter 开发者 /
   BotFilter developer)"; the *exact* phrase "Original BotFilter developer" quoted at
   `RU_CAPTCHA_SOURCES.md:16` is **not** in the current fork READMEs (they say "BotFilter developer")
   — a one-word difference, worth a glance.
7. **BotFilter generator vs upstream** — the generator's `MAP_PALETTE` is **byte-for-byte the same
   144 colours** as upstream's `MapPalette.colors` (144 vs 144, 0 mismatches), and its pipeline
   (hints, glyph transform, scale, outline, ripple, blur, palette match) mirrors the upstream code.
8. **BotFilter dataset** — `https://raw.githubusercontent.com/ServerSideProject/botfilter_captcha_dataset/main/LICENSE`
   is the **MIT License, Copyright (c) 2022 ServerSide** ✓; `research/jars/botfilter_captcha_dataset.rar`
   is a real RAR (magic `Rar!`); the extracted `research/jars/bf_dataset/` holds **510** PNGs, all
   **128×128**, every file name numeric (= the answer) ✓; the 510 copies in
   `dataset/out_ru/BotFilter/real_shots/` are byte-identical to the research copies (20-file MD5
   spot check, 0 mismatches).
9. **gm-captcha / uCrafts** — `github.com/eidonjoe/gm-captcha`'s `index.js` confirms every claim:
   `drawText` loops `for (i = 0; i < text.length; i++)` and does
   `.stroke(colour, randomBetween(1, maxTextWidth))` → `.drawText(i*wordSpacing, fontSize, char)` →
   `.font(file).fontSize(size).swirl(symbol + randomBetween(0, maxSwirl)).shear(...)`, i.e. **the
   `.font()` call is queued after `.drawText()`** so the first character uses the default
   GraphicsMagick font ✓; `drawLine`/`drawPoint` loop `i < lineCount` / `i < pointCount`, so
   `lineCount = -1` and `pointCount = -1` draw **nothing** ✓; `generator()` runs
   `['line','text','line','point']` and ends with `resize(width, height, "!")` ✓; default
   `maxTextWidth 3`, `colorCount 20`, `textColorCount 20` ✓; bundled `font/DroidSansFallback.ttf` ✓.
   `UCRAFTS/CaptchaService`'s `.env.example` is **exactly** the block quoted at
   `SITE_CAPTCHAS.md:372-382` / `RU_CAPTCHA_SOURCES.md:248-258` ✓; `app/utils/text.js` has
   `for (let i = 0; i <= length; i++)` → **length+1 = 6** characters ✓ and
   `if ((Math.random() * 2) > 1) item = item.toUpperCase()` → p = 0.5 ✓; `app/service/captcha.js`
   passes `lineCount: -1, lineWidth: -1, pointCount: -1` and `wordSpacing: CAPTCHA_WORLD_SPACING`
   ✓ and writes JPEG base64 into Redis ✓.
10. **CaptchaGUI** — the live
    `https://raw.githubusercontent.com/Supl1n/CaptchaGUI/main/CaptchaGUI/src/me/supl1na/captcha/CaptchaListener.java`
    confirms: `Bukkit.createInventory(null, 9, "Captcha")`; `Material.EMERALD_BLOCK` with
    `ChatColor.GREEN + "¡Click here!"`; `inv.setItem(getRandomNumberInRange(1, 7), captcha)` (a
    20-tick = 1 s delay after join); `kickPlayer("¡Nope!")` on a wrong click **and on closing the
    inventory** (`onInventoryClose`). Every claim in `SITE_CAPTCHAS.md:269-272` is correct, and the
    generator `Supl1nCaptchaGui.java` reproduces the slot range (`1 + r.nextInt(7)`), the title, the
    item name and the kick message. (`Supl1n` has exactly two repos — `CaptchaGUI` and
    `CubecoreStatistics` — confirmed from the profile page, matching `RU_PLUGINS_...:311-312`.)
11. **SmartCaptcha metadata** — Spiget confirms the name "⚑ SmartCaptcha ⚑ GUI-BASED CAPTCHA SYSTEM ⚑",
    author id 317151 = **elapsed0**, whose only two resources are `iReports` (69907) and
    `SmartCaptcha` (70935); rating **9 ratings, average 3.6** ✓; 4 118 downloads ("4.1k" ✓);
    tested versions 1.7–1.14 ✓; the Spiget search for `smartcaptcha` returns **exactly one**
    resource ✓ (so "no ambiguity" is right); premium/price 0 ✓.

**Measurements re-derived from the reference images** (`build/audit/*.py`):

12. **Section inventory** — the §2 table is exact: 343 / 24 / 14 / 11 / 28 / 13 / 1 / 7 / 70 / 0 / 14
    = **525** PNGs in 11 sections, and `site/captchas/manifest.json` has 525 entries.
13. **3×3 grid boundaries x {0, 83, 167, 250}, y {0, 50, 100, 150}** — confirmed twice over:
    (a) per-column/per-row seam analysis (`tools/analyze_grid.py`'s method) puts the two strongest
    column seams at 83/167 and the two strongest row seams at 50/100 in most V4/V5 samples; (b) the
    **flat-colour V8 samples are decisive** — every cell of `008.png`–`014.png` is 91–100 % one
    colour and the blocks land exactly on x = 0/83/167/250 and y = 0/50/100/150.
    `WebCaptcha.boundaries()` (lines 306-313) and `ObjectCaptcha.boundaries()` (150-157) reproduce
    the same numbers via `Math.round(span*i/grid)`.
14. **2×2 geometry x {0, 125, 250}, y {0, 75, 150}** — the generator computes exactly these.
15. **V8 flat-colour variant is 7 of 14** ✓ (`008.png`–`014.png` are flat, `001`–`007` are photos).
16. **V8 exact fills** `#FF0000, #00FF00, #FFF200, #000000, #FFFFFF` ✓, and the JPEG-ringing
    counts `#01FE00`×166, `#F00F00`×166, `#0FF000`×164, `#FB0400`×100 ✓ (in `008.png`).
17. **Ink counts** — `s05/001.png` = **3998** red-mask px with `#B40000` the dominant ink colour ✓;
    `s07/001.png` = **1029** with `#D06D8E` dominant ✓ (via the tool's red mask — see C4);
    `s07/001.png` artwork `#5CDBD5` = **6996** px ✓ exactly.
18. **`s04/005.png` flat fill `#146032` = 12181 px = 32.48 %** ✓ exactly as reported.
19. **Per-tile rotation is real** — `s05/002.png`'s bottom row holds three full tiles at 0°, 90°
    and 180° (I rendered the grid overlay: the left cell reads upright, the middle cell is vertical
    text, the right cell is upside-down), and `s04/003.png`'s cell (2,2) is the Minecraft logo
    **upside down** — rotating it 180° makes it read "…ecraft" upright ✓ (matches
    `PUZZLE_OBJECT_FAMILIES.md:45-48` and the `tools/tile.py` crop).
20. **The jigsaw solver claim** — I ran `tools/jigsaw3.py` on `s04/003.png`: it evaluates all
    9! arrangements for rot 0 and rot 180, best cost **381.86** / **381.98** with per-seam costs
    of 14–50 (a coherent picture would score far lower). The claim "finds **no** arrangement that
    restores a coherent picture for `s04/003.png`" ✓.
21. **V8 photo-gallery layout and the category mix** — `s10/005.png` shows exactly the eight
    categories the report lists (tabby cat, silver car, grey cat face, traffic light, orange
    Pomeranian, white car, brown puppy, parrot), and the traffic light occupies two stacked cells
    of the left column ✓. `s10/004.png` is the pale-wall photo spanning two rows ✓ (F13).
22. **`GalleryCaptcha/real_shots` inventory** — 722 PNGs: `catalogue/` 525 (= the whole catalogue, exactly
    as §8 says) + 26 (ru-numberword) + 25 (ru-numberword-caption) + 14 (ru-symbols) + 70 (ru-web)
    + 41 (ru-puzzle3x3 = V4's 28 + V5's 13) + 7 (ru-puzzle2x2 = V53) + 14 (ru-object-swatch). The
    grouping matches `tools/restore_real_shots.py` and `SITE_CAPTCHAS.md:428-430` ✓.
23. **WeatherActionCaptcha frames are traceable** — `research/yt_62jp1hEeSFk.png`,
    `research/yt_a3_VRVRGuEc.png` (and `.jpg` twins) exist, 1280×720, and
    `tools/restore_real_shots.py:91-98` copies exactly those into the dataset ✓. (But nothing in the
    repo records **which YouTube videos** they came from — the file names carry the IDs only. See §6.)
24. **The `ru-object-swatch` geometry** — `ObjectCaptcha.java` uses the same
    `Math.round(span*i/grid)` boundaries and the same five fills as the references, and does a
    JPEG round-trip ✓ (the *ordering* of the JPEG step is what the report gets wrong — F5).

**Helper scripts (`tools/`) — do they do what their names say?**

| script | verdict |
|---|---|
| `analyze_grid.py` | yes — per-column/row seam detection; `peaks()` min-separation logic is sound |
| `analyze_cells.py`, `colors.py`, `alpha.py`, `png_meta.py`, `zoom.py`, `strip_html.py`, `urls.py`, `links.py`, `man.py`, `sg.ps1` | yes — small, single-purpose inspection helpers |
| `down150.py` | yes — LANCZOS downscale to 150×90 then NEAREST upscale for inspection; note it is a *rendering* of the downscale, not a proof that the original was 150×90 (see C1) |
| `crop_grid.py` | yes — 3×3 overlay; it labels cells **(col,row)**, the reports use **(row,col)** (F13) |
| `tile.py` | yes — crops `s04/003.png` cell (167,100,250,150) and rotates 180/90 |
| `glyphs.py` | **buggy**: `"V5" in "…V53…"` is True, so V53 is analysed with the red mask (C4) |
| `jigsaw2.py` / `jigsaw3.py` | yes — genuine brute force over all 9! permutations scored by seam continuity; `jigsaw2.py` has a harmless leftover line that recomputes `idcost` identically |

---

## 6. Claims I could not check, and why

1. **Any `spigotmc.org` page** — the whole site returns **HTTP 503** for the entire audit window.
   Resource 70935, 125355, 75891, 103993, 120533, 77939, 84509, 86350, captchagui.89583,
   botfilterplus.109765 and the direct jar route are all unreadable directly. I substituted the
   **Spiget API** (which mirrors the same metadata), `mcreference.com`, and the live
   `spigotmc.ru` page. I could not independently confirm the *page rendering* of any SpigotMC
   resource page (only the metadata behind it).
2. **The SmartCaptcha jar** — unobtainable (0-byte CDN object, 503 upstream, Spigot file size 0).
   The "no image" claim therefore rests on the README/config only; nothing in the jar was inspected.
3. **The WeatherActionCaptcha jar** — spigotmc.ru requires an account; the GitHub source is 404.
   The "no image" claim rests on the page text, the author's own statement and two video frames.
4. **`verylovemetal/WeatherActionCaptcha` — "account deleted".** The repo 404s ✓ and the *account*
   404s via the GitHub API (`/users/verylovemetal` → 404, no redirect) ✓, and the spigotmc.ru page
   still points at the old URL ✓. But a **renamed** account would look identical, and I could not
   rule it out (GitHub does not publish rename history, and the Wayback API was rate-limiting me
   during the run). The strong claim "deleted together with the author's account" is therefore
   *consistent with* the evidence, not proven by it. Suggest the softer wording: "the repository
   404s and the account no longer exists".
5. **Software Heritage / Wayback for the deleted repo** — I could not re-run those queries (the
   Wayback availability API returned 429 for me). The documents' claim that no copy exists
   anywhere is plausible but I did not re-verify it.
6. **The two `yt_*.png` frames** — the frames exist and are what the README says they are
   (gameplay/promotional frames of the plugin), but the repo records **no video URL or title** for
   them; the file names carry only the YouTube IDs. The provenance is therefore incomplete.
7. **`BotFilterPlus` (SpigotMC 109765)** — page unreadable (503); the quoted description
   ("a regular botfilter but with a custom captcha", "a 128 x 128 background picture") and the
   "not in the Wayback Machine" claim could not be re-checked.
8. **The `Captcha` ambiguity list** (`SITE_CAPTCHAS.md:357-364`) — the *SpigotMC resource ids* are
   unreadable (503); I confirmed the GitHub sides (`InstantlyMoist/Captcha`, `reidjJava/Captcha`,
   `DevSakio/Captcha` → 200; `Nicbo/Captcha`, `max11-dev/Captcha` → 404) but not the mapping of
   each id to its GitHub repository from a live SpigotMC page.
9. **`mcreference.com`** pages — reachable (200) but not used as a primary source; the reports cite
   them as a fallback mirror, which is consistent with what the site is.
10. **The claim that the 18 plugins in `dataset/out/` are "the whole open-source population"**
    (`PUZZLE_OBJECT_FAMILIES.md:129`) — a negative claim about the whole ecosystem; I did not
    re-run the search. I note that the same table's line 123 identifies
    `Modrinth "Captcha" (e015SVoM)` as "= Mrbysco/Captcha" — the Modrinth API for `e015SVoM` is
    reachable (200) but I did not open it in this pass.

---

## 7. What I did not touch

No file in `dataset/`, `research/`, `reports/` (other than this new file), `site/` or `tools/` was
modified. Scratch artefacts live in `build/audit/` only:

* `build/audit/cvz/` — the six CaptchaVerifyZ jars and the extracted renderer classes
* `build/audit/classes_ru_audit/` — a throw-away compile of the generator (used to render
  reference samples and the pixel diff)
* `build/audit/puz/`, `build/audit/gen/` — image crops and a 3-sample generation
* `build/audit/*.py` — the measurement scripts behind every number quoted above
* `build/audit/url_status.json` — the status of all 75 URLs

`research/refout/` and `research/myout/` were read only; the independent re-render wrote to
`build/audit/` instead.
