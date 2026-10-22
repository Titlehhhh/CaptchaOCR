# Identification of the Russian number-word captcha family (catalogue V2 / V3 / V52)

**Result: the generator is the anti-bot plugin _LimboFilter_ by Elytrium**
(<https://github.com/Elytrium/LimboFilter>), a Velocity-proxy plugin, AGPL-3.0.
The renderer lives in `net.elytrium.limbofilter.captcha.CaptchaGenerator` and
`net.elytrium.limbofilter.captcha.painter.CaptchaPainter`.

> **Status (2026-10-21, later the same day).** The identification was acted on: the project now
> ships a **clean-room reimplementation** of the renderer as
> `dataset/generator_ru/dev/captcha/gens/LimboFilter.java`, and it generates four types -
> `dataset/out_ru/LimboFilter/{map,symbols,framed3x3,framed2x2}`. The gallery's own 250×150
> presentation of the same map (with and without the caption) is generated as
> `dataset/out_ru/GalleryCaptcha/ru-numberword`, `ru-numberword-caption` and `ru-symbols`. The framed
> captcha of §2.6 is what the old `GalleryCaptcha/ru-puzzle*` types were supposed to be; those two types
> and `PuzzleCaptcha.java` are gone, because the model behind them was wrong.
>
> One thing this document could not know yet: the catalogue was shot on **two servers with two
> different configurations**, so the reimplementation carries **two measured type profiles** - see
> the new **§2.8**.

---

## 1. The plugin

| | |
|---|---|
| Name | **LimboFilter** (Velocity) — part of the *LimboAPI / LimboAuth / LimboFilter* family |
| Author | **Elytrium** (elytrium.net). The Russian-facing SpigotMC.RU resource is posted by the same author under the alias **hevav** |
| Upstream | <https://github.com/Elytrium/LimboFilter> (branch `master`, last push 2026-09-16) |
| Licence | **AGPL-3.0** (`LICENSE` = 34 523 bytes, the AGPL text; GitHub API reports `AGPL-3.0`). `HEADER.txt` carries the per-file copyright header |
| Marketplace | SpigotMC.RU: <https://spigotmc.ru/resources/limboapi-limboauth-limbofilter-virtualnye-servera-dlja-velocity.715/> (resource id **715**, author *hevav*, 1 574 downloads, 38 698 views, first release 26 Jul 2021, updated 13 Jan 2023) |
| Modrinth | <https://modrinth.com/plugin/limbofilter> (project id `6zIy0zBK`) |
| Jar | Modrinth / SpigotMC.RU downloads. The GitHub Releases API has no attached jar in the public tree |
| Documentation | <https://github.com/Elytrium/LimboFilter#readme>, <https://elytrium.net/> |

**Not a library**: the captcha generator is inside the plugin itself. `LimboAPI`
(`Elytrium/LimboAPI`) is only the map/limbo plumbing; `LimboAuth` is the auth half.

---

## 2. The fingerprint — why this is the match

### 2.1 The decisive artefacts: one word per line, and the clipped overflow

`CaptchaPainter.drawText()` walks the string glyph by glyph and breaks the line in **two**
ways:

```java
x += spacingX + width;
if (x > this.width - offsetX || (eachWordOnSeparateLine && c == ' ')) {
  x = offsetX;
  y += spacingY + (height / 2);
}
```

* a break happens **at every space** when `EACH_WORD_ON_SEPARATE_LINE` is on (upstream
  default `true`) → **one word of the spelled number per row**;
* a word is **never split** — it keeps running until the next space, and the glyphs that
  fall outside the canvas are simply **clipped** by
  `if (localX >= 0 && localY >= y && localX < this.width && localY < this.height)`.

The catalogue shows exactly that, and the numbers decode cleanly:

| catalogue image | number | rows on the map |
|---|---|---|
| `s02…/001.png` (dot-matrix TTF) | 243 | `двести` / `сорок` / `три` |
| `s02…/002.png` | 350 | `триста` / `пятьдесят` |
| `s02…/003.png` | 333 | `триста` / `тридцать` / `три` |
| `s02…/004.png` | 298 | `двести` / `девяносто` / `восемь` |
| `s02…/005.png` | 358 | `триста` / `пятьдесят` / `восемь` |
| `s02…/010.png` | 186 | `сто` / `восемьдесят` / `шесть` |
| `s02…/013.png` | 182 | `сто` / `восемьдесят` / `два` — **«восемьдесят» runs off the right edge and its last glyph «т» is cut in half** (measured: the row profile y=71…89 has ink on both sides of x=120, and the glyph reaches x=250) |
| `s02…/014.png` | 471 | `четыреста` / `семьдесят` / `один` |
| `s06…/001.png` (V52) | 823 | `восемьсот` / `двадцать` / `три` |

The half-cut «т» of «восемьдесят» in `s02…/013.png` is the single most diagnostic detail of
the whole family: it is a direct consequence of LimboFilter's clip-without-wrap behaviour.

Only LimboFilter has the `NUMBER_SPELLING` + `EACH_WORD_ON_SEPARATE_LINE` pair, and only
LimboFilter draws a *spelled-out number*, one word per row, in a captcha.

**The 250×150 catalogue canvas** is the 128×128 map scaled by `getScaledInstance(250,150)`
(1.95× horizontally, 1.17× vertically) and then composited with the chat/title overlay:
the lowercase «о» of «сто» measures 19×9 px in the catalogue file, i.e. 1.27 : 1 before the
stretch — a normal font proportion, which is what makes the stretch measurable.

### 2.2 The number-in-words feature is LimboFilter-only

`Settings.MAIN.CAPTCHA_GENERATOR.NUMBER_SPELLING` (default `false`) switches
`CaptchaGenerator.randomAnswer()` from a random `PATTERN` string to a **number spelled out
in words**, and `spellNumber(int)` builds it from two config lists:

* `NUMBER_SPELLING_WORDS` — `List<List<String>>`, one list per digit position
  (upstream default = English: `one/two/…`, `ten/twenty/…`, `one hundred/…`);
  a Russian server overwrites it with `сто/двести/…`, `десять/двадцать/…`, `сто/двести/…`.
* `NUMBER_SPELLING_EXCEPTIONS` — `Map<String,String>`, e.g. `"11" → "eleven"`.
  **A Russian config must override this map**, otherwise 11…19 come out as «один один»,
  «один два» … (the English exception strings are shipped in the default config).

`randomAnswer()` returns `Pair.of(spellNumber(value), String.valueOf(value))`:
**the map shows the words, the player has to type the digits.** That is exactly the
catalogue's `ВВЕДИТЕ ТОЛЬКО ЦИФРЫ` / `НАПИШИ ЦИФРАМИ` / `ВВЕДИТЕ ЦИФРЫ С КАРТИНКИ В ЧАТ`
captions, and exactly the the gallery docs' *«API V2 - Капчи русским текстом (Например: двести
сорок три)»*.

### 2.3 The interference curves

`CaptchaPainter.addCurve(Graphics2D)` builds a **`CubicCurve2D.Double`** (a cubic bezier) whose
control points are random, flattens it with `PathIterator(flatness 0.1)` and draws it as
`drawLine` segments with `new BasicStroke(CURVE_SIZE)`.

* `CURVES_AMOUNT` (default **3**) — how many curves
* `CURVE_SIZE` (default **2**) — stroke width → the catalogue's **thick black** curves
* `CURVES_COLORS` (default **`["000000"]`** = black) → the catalogue's **thin blue**
  (`s02…/011.png`, `CURVE_SIZE=1`, colour ≈ `#0000FF`) and **thin magenta**
  (`s02…/012.png`) variants are the same feature with a different config.

### 2.4 The multi-coloured words = LimboFilter's GRADIENT mode

Upstream `RGB_COLOR_LIST` default =
`["000000", "AA0000", "00AA00", "0000AA", "AAAA00", "AA00AA", "00AAAA"]`.
With `GRADIENT.GRADIENT_ENABLED=true` the plugin builds `GRADIENTS_COUNT` (32) random
`LinearGradientPaint`s from that colour list (random start/end X/Y, `FRACTIONS`), and the
**text is filled with the gradient pixel at the text pixel**:

```java
image[localY * this.width + localX] = colors[(localY * this.width + localX) % colors.length];
```

Because the gradient axis is a *random diagonal* vector, the colour of the words changes with
position — which is why the catalogue shows green words next to blue ones and red ones at the
bottom. Measured on `s02…/013.png` (row-by-row dominant colour):

```
y=44-50  #007C00  (green)        y=71-87  #436C0D → #624613 → #703919 (olive → brown)
y=53-60  #436C0D  (olive green)  y=98-117 #842C2C → #B40000 (red)
```

and on `s02…/011.png` the words are green / blue / black / olive at different positions —
exactly a diagonal gradient, and exactly the upstream default palette (black, red, green,
blue, olive, magenta, cyan).

### 2.5 The backgrounds, the fonts, the per-glyph rotation

* `BACKPLATE_PATHS` — list of **image files** drawn as the captcha background and stretched
  to the canvas (`CaptchaGenerator.resizeIfNeeded` → `SCALE_SMOOTH`).
  The catalogue's Shrek / beach / sunset photographs and the moiré “psychedelic blob”
  backgrounds are **server-owner-supplied backplates**, not plugin assets.
* `USE_STANDARD_FONTS` (default `true`) → `SansSerif`, `Serif`, `Monospaced` at
  `RENDER_FONT_SIZE` (default **78**); `FONTS_PATH` adds TTFs
  (`Font.createFont(TRUETYPE_FONT)` + `GraphicsEnvironment.registerFont`).
  The catalogue's marker/handwriting face is such a TTF; the **rotating typeface from image
  to image** in the V3 section is the `fontIterator` cycling over these fonts.
* `RenderedFont` rasterises each glyph into a `width × height` bit set
  (`FONT_LETTER_WIDTH` 44, `FONT_LETTER_HEIGHT` 128) and applies
  * **per-glyph rotation** `FONT_ROTATE`: `AffineTransform.getRotateInstance((rnd-0.5) * PI/8)`
    → **±11.25°**, independently per character;
  * an **outline** second rasterisation: `BasicStroke(FONT_OUTLINE_RATE=1.25)` at offset
    `FONT_OUTLINE_OFFSET_X=-4 / Y=+4` (`FONT_OUTLINE=true`);
  * `OutlineEffect` (radius `FONT_OUTLINE_OVERRIDE_RADIUS`, default 1) clears the two low
    bits of every edge pixel → a darker rim around the glyph;
  * `RippleEffect` (`FONT_RIPPLE`, default true; amplitudes
    `FONT_RIPPLE_AMPLITUDE_WIDTH=100 / HEIGHT=10`) displaces the bitmap along two sine axes.
* `PATTERN` (default `abcdefghijklmnopqrstuvwxyz1234567890`) is the alphabet for the
  non-number mode — the V3 section is the same plugin with a Cyrillic `PATTERN`
  (`чхЩ, рРп` in the the gallery docs) and `NUMBER_SPELLING=false`.

### 2.8 The two type configurations the catalogue was shot with (measured after the fact)

The defaults above are the **upstream's**. They are not what the captured servers ran, and the
difference is large enough to decide whether the answer is readable at all. Measured pixel by pixel
off the reference samples (not derived from a formula):

| | number family (V2 / V52) | symbol family (V3) |
|---|---|---|
| face size | **36 pt** | **78 pt** (the upstream's default) |
| glyph cell | **20 × 32** map px | **44 × 128** map px (the upstream's default) |
| advance / line advance | **12 / 23** map px | **30 / 64** map px |
| glyph height | x-height **14–15** map px | cap height **~55** map px |
| characters per line / lines | about 11 / 3 | 3 / 1 |

With the upstream's own defaults a three-word number does not fit on a 128-pixel map at all: the
third word falls off the bottom and the long words are cut after four letters, so **the answer could
not be read off the picture in 73 % of the samples**. With the measured configuration the words are
visible in **100 %** of the samples, and the text band is a real band instead of the whole canvas.

The **drawing algorithm is the upstream's and is the same for both** — the same per-glyph rotation,
the same outline stamp, the same ripple, the same curves, the same gradient fill and the same
quantisation to the map palette. Only the numbers of the type differ, and they are the numbers a
server of that kind would have had in its configuration file. The outline offset and the ripple
amplitude are absolute map pixels upstream, so they are scaled with the type as well: with the
upstream's values the outline would sit four pixels away from a ten-pixel letter, and the reference
samples show neither.

The reimplementation carries exactly these two profiles:
`dataset/generator_ru/dev/captcha/gens/LimboFilter.java`, the `Type` record and the two constants
`TYPE_SMALL` (the number family) and `TYPE_DEFAULT` (the symbol family).

### 2.6 The 3×3 / 2×2 “puzzle” sections are LimboFilter's FRAMED_CAPTCHA

`Settings.MAIN.FRAMED_CAPTCHA`: `WIDTH` × `HEIGHT` maps (upstream default **3 × 3**),
canvas `128·WIDTH × 128·HEIGHT`, and

```java
if (FRAMED_CAPTCHA_ENABLED && random.nextDouble() <= FRAME_ROTATION_CHANCE) {
  for (int j = 0; j < random.nextInt(4); ++j) this.rotate(mapData);
}
```

→ each frame is rotated by a multiple of 90°. That is the «V4 - Капчи-Пазлы» family of the GalleryCaptcha type group *“API V4 - Капчи-Пазлы,
для того чтобы бот крутил рамки”* and *“API V52 - Капчи с русским текстом формата 3x3, где
нужно вращение”* — the puzzle sections of the catalogue are LimboFilter framed captchas.

### 2.7 The Russian chat strings (the plugin's own messages, in Russian)

Upstream ships English defaults in `Settings.MAIN.STRINGS`; Russian servers overwrite them.
The **community LimboFilter config on SpigotMC.RU**
(<https://spigotmc.ru/resources/samyj-xoroshij-konfig-na-limbofilter.3240/>, author *g4vrk*)
publishes the Russian set verbatim, and its screenshots show the two chat lines:

```
Анти-Бот » Начата проверка, пожалуйста, подождите и не двигайтесь..
Анти-Бот » Пожалуйста, решите капчу, у вас есть 5 попытки
```

which map 1:1 onto upstream `CHECKING_CHAT`
(`"{PRFX} Bot-Filter check was started, please wait and don't move.."`) and
`CHECKING_CAPTCHA_CHAT` (`"{PRFX} &aPlease, solve the captcha, you have &6{0} &aattempts."`),
with `PREFIX = "Анти-Бот"`.

The captions that the catalogue bakes into the pictures are the **same class of string**,
i.e. `CHECKING_CAPTCHA_CHAT` / `CHECKING_CAPTCHA_TITLE` of a Russian server:

| catalogue caption | where | upstream key it replaces |
|---|---|---|
| `ВВЕДИТЕ ТОЛЬКО ЦИФРЫ` (orange, bottom) | `s02…/004`, `s02…/013` | `CHECKING_CAPTCHA_CHAT` |
| `ВВЕДИТЕ ЦИФРЫ С КАРТИНКИ В ЧАТ` (black, bottom) | `s02…/011`, `s02…/012` | `CHECKING_CAPTCHA_CHAT` |
| `НАПИШИ ЦИФРАМИ` (red, **top** = a *title*) | `s02…/014`, `s06…/001` | `CHECKING_CAPTCHA_TITLE` |
| `ВВЕДИТЕ СИМВОЛЫ` (white, bottom) | `s03…/009` | `CHECKING_CAPTCHA_CHAT` |

**The captions are NOT drawn by the renderer** — upstream `drawText()` only ever draws the
answer. They are chat/title strings that the the reference gallery operator composited onto the
picture (the catalogue images are 250×150 composites of the map + the chat line; two of them
carry the operator's own credit `сделано для галереи`, and the LEAKED-MINECRAFT.PRO ones are
screenshots of a leaked server).

---

## 3. Rendering algorithm (upstream, for re-implementation)

### 3.1 Pipeline (`CaptchaGenerator.genNewPacket`)

1. `randomAnswer()` → `Pair(spelledWords, digits)` (number mode) or `Pair(pattern, pattern)`.
2. Background: the backplate image (or an empty canvas) → `CraftMapCanvas`.
3. Text: `painter.drawCaptcha(font, colourBytes, spelledWords)`
   * `drawText()` walks the string, rasterising each glyph from `RenderedFont`,
     writing `colors[(y*w+x) % colors.length]` into a transparent `byte[]` buffer;
     breaks the line at a space and whenever `x > width - LETTER_OFFSET_X`;
     the next line starts at `y += FONT_LETTER_SPACING_Y + glyphHeight/2`.
   * then the effects: `RippleEffect` (if `FONT_RIPPLE`) → `OutlineEffect`.
4. Curves: `painter.drawCurves()` → a `BufferedImage(TYPE_INT_ARGB)` of the same size,
   `BasicStroke(CURVE_SIZE)`, `CURVES_AMOUNT` cubic beziers, one colour from
   `CURVES_COLORS` (rotating iterator) — drawn **over** the text.
5. `CraftMapCanvas.drawImageCraft(...)` blits the text layer over the backplate and
   `drawImage(curves)` blits the curves on top.
6. The canvas is split into `WIDTH × HEIGHT` maps of `128 × 128`; each map may be rotated by
   `k·90°` (`FRAME_ROTATION_CHANCE`).
7. Everything is quantised to the **Minecraft map palette**
   (`MapPalette.imageToBytes` / `tryFastMatchColor`) — the player sees the palette colours.

### 3.2 Canvas

* the captcha is a **Minecraft map**: `MapData.MAP_DIM_SIZE` = **128 × 128** px per map;
* framed captcha: `128·WIDTH × 128·HEIGHT` (upstream default 3×3 → 384×384);
* the **catalogue's 250 × 150** PNGs are the gallery's presentation composites
  (map + chat/title overlay), *not* the renderer canvas. The original per-map canvas
  (128×128) is what a re-implementation must produce.

### 3.3 Answer / verification

* `CachedCaptcha.addCaptchaPacket(answer.value(), …)` stores the **digits**;
  `BotFilterSessionHandler.onChat(String)` → `equalsCaptchaAnswer(message)`:
  `message.equalsIgnoreCase(captchaAnswer)` when `IGNORE_CASE=true` (default), else
  `message.equals(...)`.
* **The answer is *not* printed in chat.** Upstream sends
  `CHECKING_CAPTCHA_CHAT` (“Please, solve the captcha, you have N attempts.”),
  `CHECKING_WRONG_CAPTCHA_CHAT`, `SUCCESSFUL_CRACKED`, `CAPTCHA_FAILED_KICK`.
  There is no leak of the digits.

### 3.4 Upstream quirks worth preserving in a re-implementation

1. **The clipped overflow** (see §2.1) — a spelled-out word that is too long for the canvas
   is cut off at the right edge instead of being wrapped. The single most recognisable
   artefact («восемьдесят» with a half-cut «т» in `s02…/013.png`).
2. **`NUMBER_SPELLING_EXCEPTIONS` ships in English** — a Russian config that forgets to
   override it spells 11…19 as «один один», «один два», … (defect inherited from upstream).
3. **`spellNumber` has no zero word and no thousands handling** beyond the length of
   `NUMBER_SPELLING_WORDS`; `LENGTH` must equal the number of word lists, otherwise
   `words.get(idx)` throws.
4. **A message starting with `/` is accepted** — `onChat` strips a leading `/` before
   comparing, so `/298` passes the check.
5. **The whole text is one colour unless `GRADIENT_ENABLED`** — the multi-coloured words in
   the catalogue come from the gradient fill, not from a per-word colour list.
6. **The map is quantised to the Minecraft map palette**; the black ink in the catalogue
   (`#130B08`) and the muted palette colours are the palette/render values, not pure CSS
   colours.
7. **`drawText` advances `x` by `spacingX + glyphWidth` and the break test is
   `x > width - LETTER_OFFSET_X`**, i.e. the *next* glyph always starts a new row once the
   current one has overflowed — a re-implementation must not “fix” this by re-wrapping.

---

## 4. Mapping of the catalogue sections to the plugin

| GalleryCaptcha type section | content | LimboFilter configuration |
|---|---|---|
| **API V2 — Русские капчи** | number spelled out in words, one word per line, coloured, curves, captions | `NUMBER_SPELLING=true`, Russian `NUMBER_SPELLING_WORDS` + `NUMBER_SPELLING_EXCEPTIONS`, `EACH_WORD_ON_SEPARATE_LINE=true` |
| **API V3 — Русские капчи** | random Cyrillic symbols, rotating typefaces, photos | `NUMBER_SPELLING=false`, Cyrillic `PATTERN`, `USE_STANDARD_FONTS`/`FONTS_PATH`, `BACKPLATE_PATHS` |
| **API V52 — Русские 3×3 пазлы** | Russian number words in a 3×3 rotatable frame | `FRAMED_CAPTCHA.ENABLED=true`, `WIDTH=3`, `HEIGHT=3`, `FRAME_ROTATION_CHANCE` |
| **API V4 / V5 / V53 — пазлы** | 3×3 / 2×2 rotatable frames | `FRAMED_CAPTCHA` 3×3 / 2×2, various backplates |
| **API V1.1 / V6 / B1** | web captchas / square-font captchas | not this plugin |

---

## 5. What could **not** be recovered

* **The backplate images** (Shrek, beach, sunset, moiré) and the **marker/handwriting TTF**
  are supplied by the server owner through `BACKPLATE_PATHS` / `FONTS_PATH`; upstream ships
  **no** bundled assets, so there are no asset filenames to list. A re-implementation must
  substitute its own backgrounds/fonts and say so.
* **The exact per-image configuration** of the captured servers is not recoverable; the
  catalogue is a mixture of several servers' configs (different curves, colours, captions).
* The **chat/title overlays** in the catalogue PNGs are gallery composites, not renderer
  output; a faithful generator should emit the bare captcha and (optionally) the caption as a
  separate layer.

---

## 6. Search log (what was tried and ruled out)

* **Exact Russian strings** in public code (grep.app + Sourcegraph): `"введите цифры с
  картинки в чат"` (0 hits), `"напиши цифрами"` (1 unrelated hit),
  `"введите только цифры"` (only Parsley.js i18n), `"введите символы"` (unrelated).
  → the strings are **not** in upstream source, they are per-server config.
* **GitHub code search** (unauthenticated API → 401) — replaced by grep.app / Sourcegraph.
* **Maven Central** (`search.maven.org`): candidates `com.anji-plus:captcha`,
  `com.begcode:captcha`, `com.pig4cloud.plugin:easy-captcha`, `com.google.code.kaptcha` —
  all rejected: none has a Cyrillic number-word list, a “one word per line” mode or captions.
* **Search engines**: `ddgs` (all backends return “No results found” on this host),
  Google (JS-only HTML), Yandex/Baidu/Sogou (Cyrillic queries mangled) — worked around with
  `spigotmc.ru`’s XenForo search, `mcreference.com` (SpigotMC mirror) and the SpigotMC.RU
  resource catalogue.
* **Ruled out on the way** (all examined, all *not* it): `BICaptcha` (title text, no image),
  `AltronCaptcha` (click a chat message), `NormalAntiBot` / `nwAntiBot` (GUI), `BIBCRAFTCAPTCHA`
  (crafting action), `Katze-AntiBot`, `SMobVelocity` / `SBlockVelocity` (block captchas),
  `WinShield` (Cloudflare/reCAPTCHA), `UCRAFTS/CaptchaPlugin` (gm-captcha, 512×256),
  `InstantlyMoist/Captcha`, `Leymooo/BungeeCord` BotFilter, `Mateitaa1/CaptchaVerifyZ`,
  `Supl1n/CaptchaGUI`, `elapsed0/SmartCaptcha`, `verylovemetal/WeatherActionCaptcha`.
* **The decisive step** was the SpigotMC.RU community config
  *«Самый хороший конфиг на LimboFilter»* (g4vrk), whose screenshots show the identical
  rendering style (procedural colour background, marker-style TTF, thick black cubic-bezier
  curves) **and** the plugin’s Russian chat strings, and the *«Кривая капча в LimboFilter»*
  forum thread.

### Artefacts left in the repo

* `research/tools/websearch.py`, `websearch2.py`, `codesearch.py`, `codesearch2.py`,
  `spigotru*.py`, `mcref*.py`, `respages*.py`, `palette.py`, `wordcolors.py`, `rowmap.py`,
  `crops*.py`, `gridcheck.py` — the search/analysis helpers used above.
* `research/candidates/` — the LimboFilter community-config screenshots and the plugin
  screenshot pack (`samyj_xoroshij_konfig_na_limbofilter_3240__*.png`).
* `research/crops/` — upscaled crops of the catalogue samples used for the font/colour
  analysis.
