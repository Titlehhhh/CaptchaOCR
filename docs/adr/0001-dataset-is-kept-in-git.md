# REVIEW — `dataset/generator_ru/dev/captcha/gens/` (the `out_ru` generators)

> **Superseded by 0004** — the generated dataset no longer lives in git; it is published as a
> Hugging Face dataset repository. See `docs/adr/0004-dataset-lives-on-huggingface.md`.

---

> **ADR 0001 — Датасет остаётся в git, а генераторы переписываются заново.**
>
> - **Дата:** 2026-10-22 · **Статус:** принято · **Решение автора проекта:** владелец
> - **Контекст:** этот документ — ревью генераторов `dataset/generator_ru/…/gens/` и общего ядра
>   `dataset/generator/dev/captcha/`. Ревью нашло 7 блокирующих (B1-B7) и 16 неблокирующих (N1-N16)
>   замечаний к состоянию генераторов на 2026-10-21; часть из них позже исправлена, часть — нет.
> - **Решение:** сгенерированный датасет (46 типов x 100 картинок + 1240 эталонных скриншотов)
>   **остаётся в git** — без него модель не обучаема, а 34 МБ — приемлемая цена. Генераторы
>   переписываются **faithful** там, где лицензия это позволяет, **clean-room** — где не позволяет,
>   и помечаются **reconstructed** там, где апстрим не найден.
> - **Последствия:** `docs/adr/0001-…` (этот файл) — источник истины по состоянию генераторов
>   `out_ru`; открытые находки N4, N5, N8, N12, N13, N14, N15 перечислены в нём и часть из них
>   ещё не закрыта. Дефекты апстрима **не чинятся** — они воспроизводятся и документируются.

Reviewer: automated review agent. Date: 2026-10-21.
Target tree: `dataset/generator_ru/dev/captcha/gens/` (BotFilter, CaptchaVerifyZ, ObjectCaptcha,
PuzzleCaptcha, RussianCaptcha, Supl1nCaptchaGui, WebCaptcha) plus the shared core
`dataset/generator/dev/captcha/{Cg,Img,McUi,Gen,Validate,Stats}.java`.

**Revisions reviewed.** The tree was being edited *while* this review ran, so every finding below is
tied to a file revision:

| file | size | mtime | state |
|---|---|---|---|
| `BotFilter.java` | 19233 | 17:46:39 | as reviewed |
| `CaptchaVerifyZ.java` | 5159 | 17:30:11 | as reviewed |
| `ObjectCaptcha.java` | 6315 | 17:49:33 | as reviewed |
| `RussianCaptcha.java` | 21642 | 17:24:21 | as reviewed |
| `Supl1nCaptchaGui.java` | 3945 | 17:23:16 | as reviewed |
| `WebCaptcha.java` | 15139 → 10044 | 18:10:11 | reviewed in both revisions (the puzzle variants moved out to the new `PuzzleCaptcha.java`) |
| `PuzzleCaptcha.java` | 11303 | 18:16:38 | new file, reviewed after creation |

Scratch scripts, images and measurements live in `build/review/` (nothing outside that directory and
`docs/adr/0001-dataset-is-kept-in-git.md` was written; the one exception is the fix to
`tools/restore_real_shots.py`, see **B7**).

---

## Status of this review (added later, the findings above are unchanged)

This review describes the generator tree as it stood on 2026-10-21, ~18:00. The tree has moved on since;
the findings are kept exactly as they were written, and each one is annotated below with what has
happened to it. The short version:

| finding | state |
|---|---|
| **B1** `spell()` off-by-one | **fixed** - 1-based units table + a separate teens table; `tools/check_labels_and_roi.py` re-derives every spelling independently of the generator and the shipped tree measures **0 mismatches** |
| **B2** swatch asks for a colour that is not in the image | **fixed** - the fills are drawn first and the target is the **minority** colour that is actually in the grid; the shipped tree has 0 such samples |
| **B3** `blobBase()` never positions the letters | **obsolete** - `PuzzleCaptcha.java` and the `ru-puzzle*` types are gone; the puzzle family is now LimboFilter's `FRAMED_CAPTCHA` |
| **B4** rotated puzzle tiles leave black bands | **obsolete** - same reason; the framed types are generated from the plugin's own algorithm |
| **B5** `Puzzle3x3` inherits the B1 bug | **obsolete** - same reason |
| **B6** `ru-symbols` is a misreading of its reference | **fixed, differently** - the symbol family turned out to be LimboFilter's `PATTERN` mode (section V3), so `ru-symbols` is now the gallery's composite of `LimboFilter/symbols` |
| **B7** the `real_shots` contract is broken for BotFilter | **fixed** - `dataset/out_ru/BotFilter/real_shots/` holds the 510 renders and carries a `README.md` |
| **N2** `Symbols.source()` points at the number-word section | **fixed** - the symbol family cites the V3 section |
| **N6** the swatch colour model does not match the reference | **fixed** - the generator now uses two colours with a majority/minority split, like the references |
| **N7** `Supl1nCaptchaGui` labelled "Faithful" | **fixed** - the javadoc now says *clean-room* and says why (the upstream has no licence file) |
| **N11** the trailing-space spelling creates an empty text row | **fixed** together with B1 |
| **N1**, **N10**, **N5** (puzzle-specific) | **obsolete** for N1/N10; N5 still stands |
| **N4**, **N8**, **N12**, **N13**, **N14**, **N15** | **still open** - see the notes under each finding |

The dataset also grew and changed shape since: `dataset/out_ru/` now holds **12 types x 100 = 1200
images** (not 10 x 100 = 1000), the two `ru-puzzle*` types are gone, and `labels.jsonl` carries two
new fields, `text` (the string that is drawn) and `roi` (the bounding box of the text band that
carries the answer, `null` when there is no single band).

---

## Blocking issues

### B1. `RussianCaptcha.spell()` spells the units digit one too high — 910 of 999 numbers are wrong

**File:** `dataset/generator_ru/dev/captcha/gens/RussianCaptcha.java:68-72` and `:111`

```java
private static final String[] ONES = { "один", "два", ... "двадцать" };   // index 0 == "one"
...
int o = n % 10;
...
sb.append(ONES[o]);        // line 111  <-- off by one
```

`ONES` is 1-based (`ONES[0] == "один"` is *one*, `ONES[19] == "двадцать"` is *twenty*), but it is
indexed with `o = n % 10` (0-based). Consequences:

* unit 1 → `"два"`, unit 2 → `"три"`, … unit 9 → `"десять"` (always one too high);
* the teens 11–19 are **never** produced (for `t == 1` the tens table is empty and the code falls
  through to the broken ones lookup), so 11 → `"два"`, 15 → `"шесть"`;
* multiples of ten with `t == 1` (10, 110, 210, …) get a stray `"один"` or a **trailing space**
  (`"сто "`), which `render()` then splits into an extra empty row;
* `ONES[9] … ONES[19]` (the teens and "двадцать") are dead entries.

**Measured** (`build/review/spell2.txt`, exhaustive 1…999 against a correct Russian reference):

```
wrong spellings in 1..999: 910 / 999          (91.1 % of a uniform n in 1..999)
spellings with a trailing space: 9
shipped labels whose drawn word disagrees with the answer: 183 / 200
```

The last line is the killer: **183 of the 200 shipped samples in
`dataset/out_ru/GalleryCaptcha/ru-numberword/` and `.../ru-numberword-caption/` carry a ground truth that
does not match the word drawn in the image.** A human reading the image would answer with different
digits. This is 18 % of the whole `out_ru` dataset poisoned, and it is exactly the kind of error a
model trained on it would absorb.

Visual proof: `build/review/numberword_sheet.png` (answer=678 is drawn as `шестьсот семьдесят
десять`, answer=522 as `пятьсот двадцать три`, …).

**Fix:** index the ones table 1-based and add a separate teens table, e.g.

```java
private static final String[] UNITS = { "", "один", "два", ..., "девять" };      // 1-based
private static final String[] TEENS = { "десять", "одиннадцать", ..., "девятнадцать" };
...
int r = n % 100;
if (r >= 10 && r <= 19) { sb.append(TEENS[r - 10]); }
else { if (t > 0) sb.append(TENS[t]); if (o > 0) { sep(); sb.append(UNITS[o]); } }
```
and drop the `sb.length() == 0 → ONES[0]` fallback (it is what produces `"один"` for 10). A
regression test that walks 1…999 and compares against a table is worth adding; `dev.captcha.Validate`
cannot catch this class of bug (see **N12**). After the fix the 200 affected samples must be
regenerated.

> **Fixed since (2026-10-21, later the same day).** The spelling now uses a 1-based `UNIT_WORDS`
> table plus a separate teens table, and the generator's own words are cross-checked by
> `tools/check_labels_and_roi.py`, which re-derives every number's spelling from a table written
> **independently of the generator** and also parses the words back into a number. Measured on the
> shipped tree: **0 mismatches** in `dataset/out_ru`, and the same checker reports **0** in
> `dataset/out` as well apart from the three arithmetic types, where `text` (the expression) and
> `answer` (the result) are supposed to differ.

### B2. `ObjectCaptcha.Swatch` asks for a colour that is not in the image 12 % of the time

**File:** `dataset/generator_ru/dev/captcha/gens/ObjectCaptcha.java:89-111`

```java
target = r.nextInt(SWATCHES.length());      // line 90  - the target is chosen FIRST
answer = SWATCH_NAMES[target];
...
for (int row = 0; row < GRID; row++)
    for (int col = 0; col < GRID; col++) {
        int idx = r.nextInt(SWATCHES.length());   // line 100 - the grid is drawn independently
```

The target colour is drawn independently of the nine cells, so with probability `(4/5)^9 ≈ 13 %`
**no cell has the requested colour** and the challenge is impossible.

**Measured:** 34/300 fresh samples (11.3 %) and **12/100 shipped samples**
(`021.png` "зелёный", `026.png` "чёрный", `031.png` "жёлтый", `043.png` "зелёный",
`046.png` "жёлтый", …) have no cell of the requested colour — see
`build/review/shipped_check.py`. A further 59/100 have **more than one** such cell, so even the
surviving 88 % are ambiguous ("click the cell of colour X" — which one?).

**Fix:** draw the grid first, then pick the target from the colours that are actually present
(e.g. `target = distinct[rnd.nextInt(distinct.length)]`), and — to match the reference (see **N6**)
— pick a minority colour so the task is well posed.

> **Fixed since (2026-10-21, later the same day).** Exactly as recommended: the generator now draws
> a majority colour and a **minority** colour (2–4 cells) and makes the minority the target, so the
> requested colour is always in the image and the task is well posed. The shipped tree measures
> **0** samples with a missing answer colour.

### B3. The new `PuzzleCaptcha.blobBase()` never positions the letters — the 2x2 samples contain no letters at all

**File:** `dataset/generator_ru/dev/captcha/gens/PuzzleCaptcha.java:220-238`

```java
int x = -10 + r.nextInt(20);
int y = 50 + r.nextInt(50);
for (int i = 0; i < letters.length(); i++) {
    ...
    g.draw(vector.getOutline(0f, 0f));     // line 232  <-- x and y are never used
    x += 26 + r.nextInt(16);
    ...
}
```

`GlyphVector.getOutline(0f, 0f)` returns the glyph in the vector's own space, whose baseline sits
at y = 0. The letter is therefore drawn **above the top edge of the canvas** and the bookkeeping
variables `x`/`y` are dead. The rendered 2x2 base is a white field with teal blobs and *no text at
all* (`build/review/blobbase.png`), while `answer()` returns 4–5 letters.

**Measured:** every 2x2 sample rendered by the current code shows blobs only; the answer is not
recoverable from the image at all (`build/review/puzzle_sheet.png`).

**Fix:** position the glyph, e.g. build the vector at the wanted origin
(`font.createGlyphVector(frc, text)` then `vector.setGlyphPosition(i, new Point2D.Double(x, y))`),
or use `g.drawGlyphVector(vector, x, y)` with a vector created for the whole string; then draw the
outline as `g.draw(vector.getOutline(x, y))` — note `getOutline(x, y)` *translates* the outline, so
`getOutline(0f, 0f)` + `setGlyphPosition` is the cleaner route. Also make the per-letter advance
follow the glyph width (`fm.charWidth(c)`), not a fixed 26–42 px, otherwise 62–88 pt letters overlap
each other.

> **Obsolete since (2026-10-21, later the same day).** `PuzzleCaptcha.java` no longer exists and
> neither do the `GalleryCaptcha/ru-puzzle2x2` / `ru-puzzle3x3` types: the model behind them was wrong.
> The puzzle family is LimboFilter's `FRAMED_CAPTCHA` - one picture of the Russian number-word body
> cut into `WIDTH x HEIGHT` maps of 128x128, each turned on its own - and it is generated as
> `dataset/out_ru/LimboFilter/framed3x3` (384x384) and `LimboFilter/framed2x2` (256x256). The
> lettering problem this finding describes no longer exists: the plugin's own renderer lays the
> words out, one per line, and clips a word that does not fit.

### B4. Rotated puzzle tiles leave black bands — 23 % of the generated 2x2 pixels are pure black, the references have 0 %

**File:** `dataset/generator_ru/dev/captcha/gens/PuzzleCaptcha.java:281-292`
(the same code was in the previous revision of `WebCaptcha.java:286-296`)

```java
BufferedImage cell = Img.rgb(dw, dh);              // TYPE_INT_RGB -> initialised to BLACK
cg.setClip(0, 0, dw, dh);
cg.translate(dw / 2.0, dh / 2.0);
cg.rotate(quarter * Math.PI / 2);
cg.drawImage(base, -sw / 2, -sh / 2, sw / 2, sh / 2, sx, sy, sx + sw, sy + sh, null);
```

The source tile (125×75 for the 2x2) is drawn into a 124×74 rectangle and then rotated by 90°, so
the content becomes 74×124 inside a 125×75 cell: the cell is **not covered** and the uncovered area
stays the black that `Img.rgb()` initialises the buffer to. The result is a black band of
(125−74)/2 ≈ 25 px on each side of every quarter-turned tile. The same happens in the 3x3 (83×50 cell
→ 50×83 content → ~16 px bands).

**Measured** (`build/review/black_bands.py`):

```
reference V53 (2x2), 7 samples : pure-black pixels  0.00 %   (min row-sum 38)
generated 2x2 (new code)       : pure-black pixels 23.06 %
```

The reference tiles are contiguous — the turned tile is scaled to fill its cell (which is also what
`research/reassemble.py` assumed: *"the tile is scaled to fill the cell, as the reference shows"*).

**Fix:** rotate the tile in its own square (swap the tile's own width/height) and then draw it into
the cell scaled to `dw × dh`, e.g. draw the source tile into a `sh × sw` image, rotate that by
`quarter * 90°` (its dimensions then match the cell's swapped pair), and finally
`g.drawImage(rotated, dx, dy, dx + dw, dy + dh, 0, 0, rotated.getWidth(), rotated.getHeight(), null)`
so the cell is completely covered and only the *content* is clipped, not the cell.

> **Obsolete since (2026-10-21, later the same day).** The `PuzzleCaptcha` tile code is gone (see
> **B3**). The framed captcha is now rendered the way the plugin renders it: the picture is cut
> into maps of 128x128 - the size of a map - and **each map is turned on its own**, so a turned
> frame is still a full 128x128 image and there is no uncovered cell. The black bands cannot occur.

### B5. `PuzzleCaptcha.Puzzle3x3` inherits the B1 bug — 100 more mislabelled samples

**File:** `dataset/generator_ru/dev/captcha/gens/PuzzleCaptcha.java:100-106`

```java
int n = 1 + r.nextInt(999);
answer = String.valueOf(n);
BufferedImage base = RussianCaptcha.render(r, RussianCaptcha.spell(n), null);
```

The 3x3 puzzle body is the number-word spelling, so the same off-by-one applies: the drawn word
disagrees with `answer` for ~91 % of the samples. Fixing B1 fixes this too, but the 100 already
generated `ru-puzzle3x3` samples have to be regenerated.

> **Obsolete since (2026-10-21, later the same day).** The `ru-puzzle3x3` type is gone; the same
> body is now generated as `dataset/out_ru/LimboFilter/framed3x3`, which draws the words with the
> plugin's own renderer, and the spelling is the fixed one of **B1**.

### B6. `ru-symbols` is a misreading of its reference: the ground truth matches no reference sample

**File:** `dataset/generator_ru/dev/captcha/gens/RussianCaptcha.java:252-292` (class `Symbols`)

The javadoc claims:

> *"One of the reference samples is exactly this - three rows of six characters in a monospace
> face, nothing else on the canvas."* — referring to `<gallery-refs>/s02_API_V2_Русские_капчи/001.png`

**Measured** on that exact file (`build/review/v8_geom.py`, ink projection per text row):

```
text row y 30..49   x 31..146   glyph clusters = 6
text row y 55..75   x 31..124   glyph clusters = 5
text row y 80..100  x 31..81    glyph clusters = 3
```

Six, **five** and **three** glyphs — the rows are the *words* "двести / сорок / три", i.e. the
number 243, set in a monospace face. There is no 3×6 grid of random characters anywhere in the
reference; the whole V2 section (14 samples) is the number-word family. `Symbols` therefore invents a
family that does not exist and ships 100 samples whose 18-character ground truth is unrelated to any
catalogue image. `restore_real_shots.py` maps `ru-symbols ← s02` (14 images), which is the number-word
section — the mapping itself is the tell.

**Fix:** either drop the `Symbols` type (the reference has no such family) or re-purpose it: the
V2 reference *does* contain a "symbols" variant — the samples captioned **«ВВЕДИТЕ СИМВОЛЫ С
КАРТИНКИ В ЧАТ»** (s02/011, s02/012) — whose body is a short random character string. If that is the
intended family, the generator must copy the reference layout (1–2 rows of a few characters, the
handwriting/hollow face, the caption at the bottom) and the answer must be exactly the drawn
characters; the `source()` must then point at the section the samples actually come from.

> **Fixed since (2026-10-21, later the same day) - but not the way the finding proposed.** The
> symbol family of the catalogue is not a 3x6 grid at all: it is **LimboFilter in its `PATTERN`
> mode**, i.e. three characters of the plugin's alphabet on a 128x128 map, presented by the gallery
> as a 250x150 composite (section V3, "Русские капчи", the one captioned `ВВЕДИТЕ СИМВОЛЫ`). The
> family is therefore generated twice: `dataset/out_ru/LimboFilter/symbols` is the **renderer's own
> output** (128x128, clean-room) and `dataset/out_ru/GalleryCaptcha/ru-symbols` is the **gallery's
> composite** of it at 250x150 with the caption. The ground truth is that symbol string, and the
> `source()` cites the V3 section. The 18-character answers this finding complained about are gone.

### B7. The `real_shots` contract is broken for BotFilter: the 510 upstream renders are gone and the restore tool could not bring them back

`dataset/out_ru/BotFilter/real_shots/` **does not exist** in the tree, although:

* `AGENTS.md` §6 and the BotFilter javadoc claim the comparison is against "the 510 real upstream
  renders";
* the repo's own analysis scripts point at that path
  (`build/bfstats.py:5`, `build/bffinal.py:5`, `build/bfcontact.py:5`, `build/bffont.py:6`,
  `build/bfzoom.py:5`, `build/bfanalyze*.py:4`) — all of them are now dead;
* the renders themselves are still in `research/jars/bf_dataset/<answer>.png` (510 files, names are
  4 or 5 digits: 237 four-digit, 273 five-digit, min 1024, max 99899 — consistent with the upstream
  `randomAnswer()`), but `tools/restore_real_shots.py` never copied them.

**I fixed this one thing** (the only file I changed): `tools/restore_real_shots.py` now also copies
`research/jars/bf_dataset/*.png` into `dataset/out_ru/BotFilter/real_shots/`, and the docstring
mentions the source. Verified in a scratch destination (`build/review/test_restore.py`): the run
count goes from 729 to **1239** images, the two runs are byte-identical (**idempotent**), and the
`BotFilter/real_shots` folder now appears. The dataset copy itself was *not* created, because I was
asked not to write under `dataset/` — run `python tools/restore_real_shots.py` to populate it.

> **Fixed since (2026-10-21, later the same day).** The restore was run: `dataset/out_ru/BotFilter/real_shots/`
> holds the **510** renders and carries a `README.md` that says where they come from and that the file
> name is the answer. The whole reference inventory is now **1240** images (it was 1239 when this
> review ran; the extra one is the V52 sample, which is now filed under
> `dataset/out_ru/LimboFilter/real_shots/framed3x3/` together with V4 and V5).

---

## Non-blocking issues

**N1 — `source()` names the wrong section for the puzzle types.** `PuzzleCaptcha.java:61` uses one
constant for both types: `...#API_V52_Русские_3х3_пазлы, #API_V53_Латинские_Цифры_2x2_пазлы...`.
The `ru-puzzle3x3` rows therefore cite V53 (whose samples are 2x2) and the `ru-puzzle2x2` rows cite
V52. Give each type its own `SRC`.

> **Obsolete since (2026-10-21, later the same day).** `PuzzleCaptcha.java` and the `ru-puzzle*` types
> are gone. The framed captcha is now `LimboFilter/framed3x3` and `LimboFilter/framed2x2`, and both
> cite the upstream renderer (`net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha`),
> not a catalogue section - the gallery composite is a different type again (`GalleryCaptcha/ru-numberword*`).

**N2 — `RussianCaptcha.Symbols.source()` points at the number-word section** (`RussianCaptcha.java:59`
is shared by all three `RussianCaptcha` variants). The `ru-symbols` rows claim to come from
`API_V2_Русские_капчи`, which is the number-word family — see B6.

> **Fixed since (2026-10-21, later the same day).** The number family and the symbol family now have
> their own `source()` constants: the number family cites `API_V2_Русские_капчи`, the symbol family
> `API_V3_Русские_капчи`.

**N3 — a caption the javadoc advertises is never drawn.** `RussianCaptcha.java:35-37` lists
`НАПИШИ ЦИФРАМИ (red, top)`; the `CAPTIONS` array at `:199-202` does not contain it (it is in the
reference, s02/014 and s06/001). Either add it (red, top) or drop it from the prose.

> **Fixed since (2026-10-21, later the same day).** `НАПИШИ ЦИФРАМИ` is the plugin's
> `CHECKING_CAPTCHA_TITLE`, and it is now the prompt of the framed types - `LimboFilter/framed3x3` and
> `LimboFilter/framed2x2` carry it, which is where the V52 sample's red title belongs. It is still
> not drawn *into* the picture of the gallery composites, because it is a title string and not
> renderer output.

**N4 — `WebCaptcha`'s javadoc claims the character count is taken from the samples; it is fixed.**
`WebCaptcha.java:50-51` says *"the canvas size, the character count, the character set … are taken
from the samples"*, but `LENGTH = 5` (`:75`). The 70 V6 references show strings of 3, 4, 5 and 6
characters (measured over `<gallery-refs>/s08_API_V6_Веб_капчи`: e.g. `8X8`=3, `LНОМ`=4, `12824`=5,
`K243KK`=6, `e068fe`=6) and the charset even contains a hyphen (`N-9K`, `O-5K`) that the generator's
`CHARSET` lacks. Draw the length from the same distribution as the references and extend the charset,
or state the fixed length in the javadoc.

> **Still open (checked 2026-10-21, later the same day).** `WebCaptcha.java` still uses a fixed
> `LENGTH = 5` and a charset without the hyphen, and its javadoc still says the character count is
> "taken from the samples". The `source()` now says "reconstructed from reference screenshots", which
> is the honest label for the type as a whole, but the sentence about the character count is still
> wrong.

**N5 — the face list cannot reproduce the family's dominant look.** The V6 references are mostly set
in a *handwriting / script* face (`c3b6y7`, `mXpp`, `gppus`, `1D3B8J` …) with a few typewriter faces;
`WebCaptcha.FACES` (`:78-80`) is Times/Georgia/Bookman/Arial/SansSerif/Monospaced/Courier/Dialog.
The generated samples are typographic where the references are hand-written.

> **Still open (checked 2026-10-21, later the same day).** The face list is unchanged.

**N6 — the swatch colour model does not match the reference.** The seven colour samples of the V8
section use **exactly two** colours each, with a clear majority/minority split
(`build/review/v8_cells.py`):

```
008  green 2 / red 7      009  black 5 / white 4    010  black 3 / white 6
011  red 4 / yellow 5     012  green 5 / white 4    013  red 7 / black 2
014  yellow 3 / green 6
```

The generator draws nine cells independently and uniformly from five colours (`ObjectCaptcha.java:
100`), which produces 4–5 distinct colours per sample. The 3×3 geometry (83×50 cells, boundaries at
x = 0/83/167/250, y = 0/50/100/150) **is** confirmed correct against the references.

> **Fixed since (2026-10-21, later the same day).** The generator now draws exactly **two** colours
> with a majority/minority split, 2–4 cells carrying the minority, and the target is the minority -
> i.e. the reference's own model.

**N7 — `Supl1nCaptchaGui` is labelled "Faithful" but the plugin renders no image, and no licence
was found.** The header says *"Faithful reimplementation of Supl1n/CaptchaGUI"*, but the upstream
`CaptchaListener` only opens a 9-slot inventory (`Bukkit.createInventory(null, 9, "Captcha")`); the
pixels are this repository's invention (`McUi.inventory` chrome). `AGENTS.md` §5 house rules say a
plugin that renders no image *"gets **no generator**"* — and the same rule is not applied to the
`XProtect` GUI types in `dataset/out/`. In addition, `Supl1n/CaptchaGUI` contains **no LICENSE file**
(the GitHub tree has only `CaptchaGUI.zip`, the sources and `out/`), so "Faithful (licence permits)"
cannot be asserted. Recommend renaming the mode to something like "Faithful logic / synthetic GUI
render" and stating the licence situation, or dropping the type per the house rule.

> **Fixed since (2026-10-21, later the same day).** The javadoc now says **"Mode: clean-room"** and
> gives the reason: the upstream repository has no LICENSE file, so there is no licence permitting a
> line-by-line copy. The second half of the finding - the house rule that a plugin rendering no image
> gets no generator - is a policy question and is still open; the `CaptchaGUI/clickblock` type
> survives, with the pixels labelled as this repository's own GUI chrome.

**N8 — `CaptchaVerifyZ.source()` drops the outer class.** `CaptchaVerifyZ.java:52` says
`com.Mateitaa1.CaptchaVerifyZ$CaptchaMapRenderer#render`; the real binary name is
`com.Mateitaa1.CaptchaVerifyZ.CaptchaVerifyZ$CaptchaMapRenderer` (the javadoc at `:36-37` has it
right). Cosmetic, but the string is the audit trail.

> **Still open (checked 2026-10-21, later the same day).** `CaptchaVerifyZ.java:52` still reads
> `com.Mateitaa1.CaptchaVerifyZ$CaptchaMapRenderer#render`.

**N9 — the BotFilter statistical comparison is apples to oranges and the docs do not say so.**
The generator quantises to the map palette (`toMapColours`), which is what the player finally sees
(upstream `CraftMapCanvas.drawImage` → `MapPalette.imageToBytes` → `tryFastMatchColor`). The 510
reference PNGs are the *pre-quantisation* painter output, so they contain anti-aliased blends:

```
REAL  (510): off-palette pixels  median  3.745 %   max 37.335 %
GENERATED:   off-palette pixels  median  0.000 %   max  0.000 %
```

The headline numbers still match (see **V4**), but the report/README should state that the reference
set is the un-quantised render while the generator emits the map data.

> **Fixed since (2026-10-21, later the same day).** The caveat is now written down: `README.md`'s
> `real_shots` note, `reports/SITE_CAPTCHAS.md` §7.5 and `dataset/out_ru/BotFilter/real_shots/README.md`
> all say that the 510 references are the pre-quantisation painter output while the generator emits
> the palette-quantised map data.

**N10 — the rotated-tile draw squishes the source by one pixel.** `PuzzleCaptcha.java:289` uses
integer division: `-sw/2 … sw/2` is 124 px wide for a 125 px tile (and 82 for 83), so the tile is
squeezed by 1 px. Use `sw / 2.0` / `sh / 2.0` (doubles) or the fill-the-cell approach of B4.

> **Obsolete since (2026-10-21, later the same day).** The file and the code are gone (see **B3**/**B4**).

**N11 — the trailing-space spelling also creates an empty text row.** For `n ≡ 10 (mod 100)`
`spell()` returns e.g. `"сто "`; `render()` does `text.split(" ")` (`RussianCaptcha.java:341`), which
yields a trailing empty string, so the layout reserves a row for an empty word and the fit maths
(`plan.size()`) counts 2 rows instead of 1. Fixed together with B1.

> **Fixed since (2026-10-21, later the same day).** Fixed with **B1** - the spelling no longer emits a
> trailing space, and the layout is now the plugin's own (one word per line, a word that does not fit
> is clipped, never wrapped).

**N12 — `Validate` cannot catch any of the label bugs.** `Validate.java:66` only checks blanks,
duplicate images and the *number* of label lines; it never compares a label with the image. B1, B2
and B6 all pass validation silently. A cheap extra check would be a per-type "answer is derivable
from the image" assertion (e.g. the swatch colour must be present, the number-word spelling must
round-trip to the answer).

> **The `Validate` half is still open** - `dev.captcha.Validate` still only counts labels. What the
> finding asks for now exists, but as two separate tools outside the Java build:
> `tools/check_labels_and_roi.py` re-derives the number words and checks that every band is inside
> the canvas and is not a flat colour, and `tools/check_band_vs_answer.py` reports per type whether
> the band carries the answer, the text, or does not exist at all. A colour-level rule (the band must
> contain the answer's ink and none of the other text's ink) is still only a scratch script,
> `build/scratch/roilabel.py`.

**N13 — `build.ps1` never calls `tools/restore_real_shots.py`.** The AGENTS.md workflow says the
script exists "because a clean rebuild of the plugin folder would wipe" the references, but a
`.\build.ps1` run leaves the tree without them. `Gen` itself does not delete anything, so this only
bites after a manual clean — but the missing BotFilter folder (B7) shows it does happen. Add the call
to `build.ps1`.

> **Still open (checked 2026-10-21, later the same day).** `build.ps1` still does not call the
> restore script.

**N14 — the reconstruction depends on this machine's font mapping.** `BotFilter` uses the *logical*
families `SansSerif`/`Serif`/`Monospaced` (as upstream does) and `RussianCaptcha`/`WebCaptcha` use
named faces. Java resolves logical families through the platform font configuration, so the
generated pixels are **not reproducible on another machine or JDK**. Worth a note in the dataset
README (and a pinned font list would make the dataset reproducible).

> **Still open (checked 2026-10-21, later the same day).** Unchanged - and it now applies to
> `LimboFilter` as well, which cycles through the same three logical faces.

**N15 — the number-word body font is far from the reference.** The V2/V3 bodies are set in a thin
*hollow/outline* typeface (s02/002, s02/003, s02/013); `RussianCaptcha.FACES` (`:135-137`) contains
no outline face, so the generated bodies are bold serifs. The javadoc does say the face list is a
reconstruction, but the visual gap is the single most obvious difference between the generated and
the reference samples.

> **Still open (checked 2026-10-21, later the same day).** The captured servers' marker/handwriting
> TTF was not recovered; `LimboFilter` uses the three standard AWT faces, exactly as upstream does
> when `FONTS_PATH` is not set. The generator's javadoc says so.

**N16 — disclosure:** running `research/DiffCaptchaVerifyZ.java` (which writes `research/myout/`
relative to the CWD) regenerated five PNGs in `research/myout/`. I verified afterwards that they are
**byte-identical** to the committed ones (MD5 equal to `research/refout/*.png`), so the tree is
unchanged in content.

---

## Verified claims

Every item below was measured, not read off a comment.

**V1 — `CaptchaVerifyZ` matches the upstream renderer exactly.** Cross-checked against the CFR
decompilation (`research/decompiled/CaptchaVerifyZ-1.4-decompiled.java:447-469`) *and* the raw
bytecode (`research/cvz14/javap_renderer.txt`): 128×128 `TYPE_INT_RGB` (`iconst_1`), `Color.DARK_GRAY`
fill, `new Font("Arial", BOLD, 12)` + `"SECURITY VERIFICATION"` at (5, 20), `Color.YELLOW` +
`new Font("Arial", BOLD, 24)`, `x = (128 - fm.stringWidth(code)) / 2`, baseline y = 70,
`Color.LIGHT_GRAY` + `new Font("Arial", PLAIN, 10)` + `"Type the code in chat"` at (15, 100), no
rendering hints, no noise, `canvas.drawImage(0, 0, image)`. The generator
(`CaptchaVerifyZ.java:99-121`) reproduces all of it, including the charset
`ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789` and length 5, which match the upstream default config
(`research/cvz14/config.yml`: `length: 5`, `characters: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"`).

**V2 — the upstream defects are preserved, as claimed.**
* *Clipped header:* measured `"SECURITY VERIFICATION"` in Arial BOLD 12 = **137 px**; drawn at x = 5
  the right edge is **142 > 128**, so 14 px are cut off. The generator inherits it.
* *The answer is printed in chat:* the upstream config really contains
  `welcome: ... "&a&l➤ &f&l{captcha}"` and
  `incorrect-attempt: "&c&lIncorrect! &7Try again: &e&l{captcha}"`
  (`research/cvz14/config.yml:54,74`, `research/decompiled/CaptchaVerifyZ-1.4-config.yml:54,74`),
  and `startVerificationProcess` substitutes `{captcha}` into the welcome message. The javadoc's
  wording is exact.

**V3 — the pixel-identity harness really is pixel-identical.** I recompiled and re-ran
`research/DiffCaptchaVerifyZ.java` and `research/RefRender.java` into `build/review/research/`: the
MD5 of `mine-<code>.png` equals the MD5 of `ref-<code>.png` for all five codes
(`00000, A7K2X, M3P9L, QWERT, ZZZZZ`) — and the committed `research/myout/*.png` are the same bytes.
*Caveat:* `research/refout/*.png` is produced by `research/RefRender.java`, i.e. by a hand
transcription of the decompiled upstream, not by upstream bytecode. The chain
bytecode → CFR → `RefRender` → generator is consistent (I checked `RefRender` against `javap`), but
the wording "verified pixel-identical to the **upstream algorithm**" is one link stronger than what
was measured; "pixel-identical to a transcription of the decompiled upstream, itself checked against
the bytecode" is the accurate claim.

**V4 — the BotFilter statistical claim holds (measured independently, 510 real vs 100 generated).**

| metric | real upstream (n=510) | generated (n=100) | repo's claim |
|---|---|---|---|
| distinct colours (median) | **13.0** | **13.5** | 13 vs 13 |
| ink coverage (median) | **41.57 %** | **41.31 %** | 41.0 % vs 41.6 % |
| ink bounding box (median) | **121 × 110** | **120 × 108** | 120×111 vs 121×110 |
| background is white | 510/510 | 100/100 | — |
| image size | 128×128 | 128×128 | — |
| ink colour saturation (median) | 0.597 | 0.596 | — |
| distinct colour range | 4 … 32 | 4 … 32 | — |

The repo's numbers reproduce within a pixel / a fraction of a percent; the only systematic difference
is the off-palette fraction (N9). Source: `build/review/bf_stats.py`.

**V5 — `BotFilter` is a faithful clean-room of the upstream algorithm.** Checked line by line
against `Leymooo/BungeeCord`:
`proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/CaptchaPainter.java`,
`.../generator/Rippler.java`, `.../generator/map/MapPalette.java`,
`.../generator/map/CraftMapCanvas.java` and `.../captcha/CaptchaGeneration.java`:

* **palette:** the upstream `MapPalette.colors` has **4 blacks + 35×4 = 144 entries**; the generator's
  `MAP_PALETTE` has **144** entries with identical values (parsed programmatically from
  `BotFilter.java:97-134`, cross-checked entry by entry against the upstream array). The upstream
  `prepareColors()` and `matchColor()` both start at index **4**, and the generator's
  `FIRST_MATCHABLE = 4` matches. The repo's claim "slots 4..143 of a 144-entry array" is **correct**.
* **distance function:** upstream `getDistance` uses `rmean`, `weightR = 2 + rmean/256`,
  `weightG = 4`, `weightB = 2 + (255-rmean)/256`, first minimum wins — identical to
  `nearestMapColour` (`BotFilter.java:438-466`). The upstream `tryFastMatchColor` fast path
  (exact hash lookup) cannot change the result because the palette has no duplicate colours in
  slots 4…143.
* **glyph layout:** `rotateCur = (rnd.nextDouble()-0.5)*PI/8`, `rotateStep = signum(rotateCur) *
  (rnd.nextDouble()*3*PI/8/glyphNum)`, per glyph `if (rnd.nextDouble() < 0.25) rotateStep *= -1`,
  and the neighbour gap `min(prevWidth, width) * (rnd.nextDouble()/20 + 0.27)` — all reproduced
  (`BotFilter.java:307-339`), **including the order in which the `Random` is consumed**, which is
  what makes the output distribution match.
* **scaling / outline:** `wr = width/bw * (rnd.nextFloat()/20 + 0.89f)`,
  `hr = height/bh * (rnd.nextFloat()/20 + 0.68f)`, translate, scale, then
  `draw(getOutline(signum(rnd.nextFloat()-0.5f)*width/200 - bx, signum(...)*height/70 + height - by))`
  and `drawGlyphVector(vector, -bx, height - by)` — reproduced exactly.
* **ripple:** amplitudes `height/10.0` and `width/100.0`, `normalize(a, 2)` / `normalize(a, 4)`,
  `(int) Math.round(amplitude * sin(start + i*period))` — reproduced; the repo's
  `Math.floorMod` is equivalent to the upstream `%` for a positive divisor.
* **blur:** nine uniform random weights normalised to sum 1, `ConvolveOp` with `EDGE_NO_OP` —
  reproduced.
* **answer / fonts / colour:** `randomAnswer()` = 4 or 5 digits with equal probability ✓,
  the three logical faces at size 50 ✓, `randomNotWhiteColor()` picks from the **whole** palette
  (so black is possible) and rejects exactly the six near-white entries
  `(255,255,255) (220,220,220) (199,199,199) (255,252,245) (220,217,211) (247,233,163)` ✓ —
  the generator's `isNearWhite` matches value for value.
* **no upstream identifiers, comments or copyright headers** are carried over; the code is
  independently written, as the javadoc claims. The licence note (md_5 BSD-2-Clause plus a
  non-commercial-hosting clause) is consistent with the upstream repository.

**V6 — the 9-argument `drawImage` rectangle convention is right everywhere.** The Java signature is
`drawImage(img, dx1, dy1, dx2, dy2, sx1, sy1, sx2, sy2, obs)` — two *corners*, not origin+extent.
Both call sites in the puzzle code use it correctly:
`g.drawImage(base, dx, dy, dx+dw, dy+dh, sx, sy, sx+sw, sy+sh, null)` (destination corners
`dx,dy → dx+dw,dy+dh`, source corners `sx,sy → sx+sw,sy+sh`) and the rotated branch
`cg.drawImage(base, -sw/2, -sh/2, sw/2, sh/2, sx, sy, sx+sw, sy+sh, null)`. The old origin+extent
bug is really fixed. (The black-band problem of B4 is a different bug: the cell is not covered, not a
misplaced rectangle.)

**V7 — no colour overflow.** Every `new Color(...)` channel stays ≤ 255: the gradient lift
`200 + getRed()/5` ≤ 251 (`RussianCaptcha.java:482-483`, and the code comment saying 251 is right),
the texture `base + nextInt(50)` ≤ 249 (`:490`), the blob colours ≤ 0xFF, the `nextInt(256)` uses
are exclusive of 256, and `new Color(SWATCHES[idx])` takes a 24-bit int. The `Math.round` casts in
`boundaries()` (`ObjectCaptcha.java:153`, `PuzzleCaptcha.java:305`) and in `waveOffsets`
(`BotFilter.java:383`) are widening-safe.

**V8 — the puzzle cut geometry matches the references.** `boundaries(250, 3)` → `0, 83, 167, 250`,
`boundaries(150, 3)` → `0, 50, 100, 150`, `boundaries(250, 2)` → `0, 125, 250` (measured with
`build/review/probe_src/.../Probe5.java`). The V8 colour samples were re-analysed on exactly those
boundaries and the cells come out as clean single colours, which confirms the cut points.

**V9 — the old "150×90 base scaled up 5/3" model was wrong; the new `PuzzleCaptcha` model is right.**
A nearest-neighbour 150→250 upscale can only change colour on a 5/3 lattice (3 of every 5 column
residues). The metric "fraction of colour-change positions on that lattice, maximised over phase"
gives:

```
CONTROL: V6 150x90 scaled to 250x150 NEAREST   1.000
CONTROL: V6 scaled to 250x150 BICUBIC           0.611   (chance level)
reference V4 / V5 / V52 / V53, whole image      0.604-0.606
reference V4 / V5 / V52 / V53, per cell         0.611-0.643   (0 % of cells > 0.9)
repo's generated ru-puzzle3x3 (old model)      0.922-1.000
```

No reference puzzle family carries the lattice, so the base art is **not** a 150×90 image blown up
5/3; it is natively 250×150 art. Visually confirmed in `build/review/zoom_v53_vs_gen2x2.png` (the
reference outlines are smooth 250-space strokes, the old generator's were staircase-blocky) and
`build/review/zoom_v5_vs_gen3x3.png`. `PuzzleCaptcha.java` now renders the base at 250×150 with no
upscale, which is the right model. (Residual defects in that new file: B3, B4, B5.)

**V10 — the base art of the two puzzle families is not the V6 web captcha.** From the contact sheet
`build/review/sheet_puzzles.png` and Agent B's reassembly (`research/reassembled/`, which holds up:
`V53_001/003/005` reassemble into one coherent cloud-and-outline-digit picture):
* V53 (2×2) = a white field with big cyan blobs and large **thin-outlined Latin digits**, natively
  250×150;
* V52 (3×3) = the Russian number-word body on black with the red caption «НАПИШИ ЦИФРАМИ»;
* V4 / V5 (3×3) = jigsaws of photographic / anime / meme artwork, most of them with no text at all
  — so no ground truth can be read from them. `PuzzleCaptcha.java:42-46` correctly excludes V4/V5
  instead of inventing an answer for them.

**V11 — `CaptchaGUI.ClickBlock` matches the upstream slot range.** Upstream
`CaptchaListener.getRandomNumberInRange(1, 7)` is `r.nextInt((max-min)+1) + min` = `nextInt(7)+1`,
i.e. slots 1…7, so inventory slots 0 and 8 are never used. The generator's `1 + r.nextInt(7)`
(`Supl1nCaptchaGui.java:61`) is the same distribution; 5000 generated samples gave a range of
exactly **1…7**. The window title `"Captcha"`, the 9 slots, `Material.EMERALD_BLOCK`, the display name
`ChatColor.GREEN + "¡Click here!"` and the kick message `"¡Nope!"` all match the upstream source
(`Supl1n/CaptchaGUI/CaptchaGUI/src/me/supl1na/captcha/CaptchaListener.java`), and
`source() = me.supl1na.captcha.CaptchaListener#onPlayerJoin` names a method that really exists
(the javadoc also lists `#onClick`, which exists too).

**V12 — the `real_shots` folders contain what their names claim.** `tools/restore_real_shots.py`
maps the catalogue sections correctly: `ru-numberword ← s02(14)+s03(11)+s06(1) = 26`,
`ru-numberword-caption ← s02+s03 = 25`, `ru-symbols ← s02 = 14`,
`ru-object-swatch ← s10 = 14`, `ru-puzzle3x3 ← s04(28)+s05(13) = 41`, `ru-puzzle2x2 ← s07 = 7`,
`ru-web ← s08 = 70`, plus the whole catalogue (525). The counts match the folders on disk, and the
script is **idempotent** (two runs produce byte-identical trees).

> **Updated (2026-10-21, later the same day).** The mapping changed with the puzzle family: the
> rotatable-frame sections are now filed under the plugin, not under the catalogue -
> `LimboFilter/real_shots/framed3x3 ← s06(1)+s04(28)+s05(13) = 42` and
> `framed2x2 ← s07 = 7` - while `GalleryCaptcha/real_shots/` keeps the six gallery families
> (`ru-numberword` 26, `ru-numberword-caption` 25, `ru-symbols` 14, `ru-object-swatch` 14,
> `ru-web` 70) plus the whole catalogue (525). The whole reference inventory is **1240** images.

**V13 — the shared core is sound for this tree.** `Gen` discovers every public concrete `Cg` with a
public no-arg constructor and instantiates a **fresh** generator per sample (so every sample has its
own `Random`); `Validate` excludes `real_shots/` from the type scan; `Img.normalize()` keeps
`TYPE_3BYTE_BGR` renders pixel-exact; `Img.font()` is `synchronized` around its cache.

---

## What I could not check, and why

1. **Whether the catalogue PNGs are the vendor's original bytes.** They are what the gallery served
   (19 RGB / 41 RGBA / 10 palette PNGs by the parent's own count); the V8 samples carry JPEG ringing,
   so some of them are re-encoded. Every "measured from the reference" statement in the javadocs
   inherits that uncertainty.
2. **The identity of the GalleryCaptcha type families.** No upstream renderer was found, so "Reconstructed" can
   only be checked against the screenshots. Whether the V6 family really has "no single generator"
   (as the new `WebCaptcha` javadoc now claims) is a research question I did not re-run.

   > **Since then:** the number-word and symbol families *were* identified - they are LimboFilter
   > (§7.8 of `reports/SITE_CAPTCHAS.md`) - and are therefore **clean-room**, not reconstructed; the
   > two families that really have no plugin behind them (`ru-web` of V6 and `ru-object-swatch` of
   > V8) are still reconstructed.
3. **The upstream identity of the BotFilter / CaptchaVerifyZ / CaptchaGUI licences.** I confirmed the
   BungeeCord-derived terms and the absence of a LICENSE file in `Supl1n/CaptchaGUI`; I did not obtain
   legal advice on whether the BotFilter clause restricts the dataset's use.
4. **Cross-machine reproducibility.** I could only measure on this machine; see N14.
5. **A full `Gen`/`Validate` run over the whole tree.** I generated only into `build/review/` and
   `dataset/out_ru` was left untouched, so I did not re-render the 1000 shipped samples with the
   current (still buggy) code; the shipped-sample numbers above come from reading the images and
   labels already on disk.

   > **Since then:** the tree has been regenerated and grown - `dataset/out_ru/` holds **12 types ×
   > 100 = 1200** samples now - and `dev.captcha.Validate` reports **0** remarks on both trees.
6. **`reports/PUZZLE_OBJECT_FAMILIES.md` and `research/WEB_CAPTCHA_V6_FINDINGS.md`** (the two
   conflicting write-ups) were not line-reviewed; I settled the disagreement by measurement (V9, V10)
   and left the documents alone.

   > **Since then:** the disagreement is settled in the same direction (the base art is natively
   > 250×150, not a 150×90 image scaled up), and the puzzle family has been rewritten from the
   > LimboFilter side.
