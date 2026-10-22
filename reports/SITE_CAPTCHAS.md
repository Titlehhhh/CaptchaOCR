# GalleryCaptcha/captchas — catalogue analysis and version → plugin mapping

**Source:** архивная страница демо-витрины (снимок в веб-архиве).
**Fetched:** 2026-10-21
**Local copy:** `<gallery-refs>/` — 525 PNGs + `manifest.json` (image → source URL → section).
**The directory was removed from the public repository on 2026-10-22**; `<gallery-refs>/` is the
placeholder used in the reports for that catalogue, `<atlas>/` for the atlas site.
**Montages:** `<gallery-refs>/MONTAGE_<section>.png` — one contact sheet per section


---

## 1. What the page is

The archived page was a demo gallery: every captcha the service claimed to
solve, grouped by **API version**. The version is what a customer prefixes to their API key
(`V2_`, `V3_`, …), so each version is a *product line*, not a software version of one plugin.

The images are therefore **not** a plugin catalogue. They are a catalogue of *captcha styles in the wild*,
collected from many sources — real Minecraft servers (several carry the `LEAKED-MINECRAFT.PRO` watermark or a
`сделано для галереи` credit, i.e. screenshots scraped from live servers) and generic web captcha corpora.

That distinction drives everything below: for most sections the honest answer to "which plugin serves this?"
is "a plugin we could not identify", and the value is in the *style* — which is what a solver has to cope with.
Since the first pass, one plugin has been identified and it turns out to account for **six of the eleven
sections**: the Russian number-word family (V2, V3, V52) and the framed "puzzle" sections (V4, V5, V52,
V53) are all **LimboFilter**, a Velocity anti-bot plugin (§3.1, §3.2, §7.8).

## 2. Section inventory

| # | Section | Images | Size | Family |
|---|---|---|---|---|
| 0 | Стандартные капчи (V1) | 343 | 250×150 / 150×90 | mixed grab-bag: web captchas, Minecraft text captchas, photo backgrounds |
| 1 | API V1.1 — ChatGPT | 24 | 250×150 / 150×90 | same corpus, solved by ChatGPT instead of the model |
| 2 | API V2 — Русские капчи | 14 | 250×150 | **Russian text captchas** |
| 3 | API V3 — Русские капчи | 11 | 250×150 | **Russian text captchas** (different renderer set) |
| 4 | API V4 — Пазл капчи | 28 | 250×150 | **3×3 framed captcha** (LimboFilter `FRAMED_CAPTCHA`) over artwork/photos |
| 5 | API V5 — Латинские/Цифры 3×3 пазлы | 13 | 250×150 | **3×3 framed captcha** over web-captcha art |
| 6 | API V52 — Русские 3×3 пазлы | 1 | 250×150 | the Russian number-word captcha in a 3×3 frame |
| 7 | API V53 — Латинские/Цифры 2×2 пазлы | 7 | 250×150 | **2×2 framed captcha** over web-captcha art |
| 8 | API V6 — Веб капчи | 70 | 150×90 | **generic web captchas** (ASCII-art style, many backgrounds/fonts) |
| 9 | API V7 — Пазл капчи | 0 | — | empty section |
| 10 | API V8 — Объект капчи | 14 | 250×150 | **object captcha** — a grid of small photos, "click all the cats" |

## 3. The renderer families, in detail

### 3.1 Russian text captcha (V2, V3 — and the body of V52)

Canvas is **250×150**. Three ingredients, all present in every sample of the family:

1. **A background.** Either a solid/gradient field, a photographic image, or a procedural pattern
   (moiré, psychedelic blobs, a cartoon character).
2. **Cyrillic text**, usually a *number spelled in words* — `сто`, `восемь`, `девять`, `триста тридцать три`,
   `четыреста семьдесят один`, `осень` — rendered in a colour that sometimes differs per word.
3. **Black interference curves** (smooth bezier-like strokes) drawn *over* the text.

Optional extras, which split the family into sub-groups:

| Marker | Meaning |
|---|---|
| `ВВЕДИТЕ ТОЛЬКО ЦИФРЫ` (orange, bottom) | "enter only the digits" — the answer is digits of the spelled number |
| `ВВЕДИТЕ ЦИФРЫ С КАРТИНКИ В ЧАТ` (black, bottom) | "enter the digits from the picture in chat" |
| `НАПИШИ ЦИФРАМИ` (red, top) + the number in words | "write it in digits" |
| `ВВЕДИТЕ СИМВОЛЫ` (white, bottom) | "enter the characters" — the answer is the letters, not a number |
| `LEAKED-MINECRAFT.PRO` (vertical) | watermark of the screenshot source, not of the plugin |
| `сделано для галереи` (bottom) | credit added by the service operator |

One sample (V2 #1) breaks the pattern entirely: plain white background, black **dot-matrix** Cyrillic in
three rows of six characters, no noise at all. It is a different renderer inside the same product line.

**The producer of this family is now identified: it is the Velocity anti-bot plugin _LimboFilter_ by
Elytrium** (<https://github.com/Elytrium/LimboFilter>, AGPL-3.0), whose `FRAMED_CAPTCHA` also produces
the "puzzle" sections V4 / V5 / V52 / V53. The full identification, with the evidence, is in
`reports/LIMBOFILTER_IDENTIFICATION.md`; §7.8 records what that means for the reserved plugin folders.
In short: the number is spelled out in words one word per line, the picture is the **map** the player
receives (a 128×128 `MapCanvas`), the 250×150 catalogue PNG is the gallery's own composite of that map
with a chat/title overlay, and the black interference curves are LimboFilter's `CubicCurve2D` curves.

### 3.2 Framed captcha — the "puzzle" sections (V4, V5, V52, V53)

These sections are **LimboFilter's `FRAMED_CAPTCHA`**, not a separate renderer. Upstream renders the
captcha onto a canvas of `128·WIDTH × 128·HEIGHT` pixels, splits it into **`WIDTH × HEIGHT` separate
128×128 map items** and hands them to the player one by one; with probability
`FRAMED_CAPTCHA.FRAME_ROTATION_CHANCE` each of those frames is **rotated by a random multiple of
90°** before it is sent:

```java
if (FRAMED_CAPTCHA_ENABLED && random.nextDouble() <= FRAME_ROTATION_CHANCE) {
  for (int j = 0; j < random.nextInt(4); ++j) this.rotate(mapData);
}
```

The catalogue operator composites the frames into one picture for the gallery, which is why the
catalogue images *look* like a picture cut into tiles - but the frames keep their positions, and
what the player actually gets is a **set of separate map frames to be rotated**. That is exactly
what the vendor's own description of the section says: *"API V4 - Капчи-Пазлы, для того чтобы бот
крутил рамки"* ("puzzle captchas, so that the bot has to turn the frames").

What is measured from the samples, and stays:

| | canvas | frames | frame size | boundaries in the composite |
|---|---|---|---|---|
| V4, V5 | 250×150 | 3×3 | 83×50 | x {0, 83, 167, 250}, y {0, 50, 100, 150} |
| V53 | 250×150 | 2×2 | 125×75 | x {0, 125, 250}, y {0, 75, 150} |

**Cell convention.** The cells are quoted as **(row, column)**, 1-based from the top left - so
"(2,2)" is the middle cell of a 3×3 grid. `tools/crop_grid.py` labels the same cells
**(column, row)** (it prints the column number along the top edge and the row number down the
left edge), so a cell quoted here has to be transposed before it is looked up in that tool's
output.

* **Per-frame rotation (proven).** `s04/003.png` frame (2,2) holds the Minecraft logo upside down;
  rotating that frame 180° makes it read "…ecraft" upright. `s05/002.png` shows three text fragments
  at 180°, 90° and 0° in three adjacent frames — per-frame rotation, not one global rotation.
  That is `FRAME_ROTATION_CHANCE` at work, and it is why a solver has to un-rotate each frame
  before it can read anything.
* **The frames are not the V6 web captchas.** Re-running `research/puzzle_check.py` (which cuts each
  puzzle on exact thirds and looks for a frame-by-frame match against the 70 V6 samples) gives
  **NO MATCH for all 13 V5 samples**; the best candidates for the V53 samples have a mean absolute
  error of 31–78 against the tool's own match threshold of 12, i.e. 8–10× the error of a true match.
  The V5/V53 base art is a 250×150 web-captcha sub-family of its own — "big decorated text on a
  white/graphic field" — not one of the 150×90 V6 samples.
* **The base art is natively 250×150, not a 150×90 image blown up 5/3.** A nearest-neighbour
  150→250 upscale can only change colour on the 5/3 lattice; measured as "the fraction of
  colour-change positions on that lattice, maximised over phase", a genuine 150×90 → 250×150
  nearest-neighbour upscale scores **1.000** and a bicubic one **0.611** (chance level), while the
  V4 / V5 / V52 / V53 samples score **0.604–0.606** over the whole image and 0.611–0.643 per frame
  (no frame above 0.9) — `docs/adr/0001-dataset-is-kept-in-git.md` §V9. The reassembled sources say the same thing:
  `research/reassembled/V53_007.png` is a natively 250×150 teal/flame artwork with the text "31".
* **The frames are not shuffled.** The upstream splits one canvas into frames *in order* and
  rotates each of them; it has no permutation step. Putting `s04/003.png` back together without
  moving a cell and turning each cell back the way it was turned gives a coherent picture again
  (a Minecraft scene with the word "legacy" in the corner), so the catalogue's grid is the
  gallery's composite of the frames in their original order. The brute-force jigsaw solver
  (`tools/jigsaw3.py`) cannot show this - it tries only one *global* rotation for the whole
  picture, so with a turn per frame every arrangement scores badly (best 381.9 for `s04/003.png`).
  That is a property of the solver, not evidence of a permutation.

Two source-image flavours are visible in the catalogue: **V4** is photographs and anime/game artwork,
**V5 / V53** is web-captcha-style art. A solver for these sections needs the base solver plus
per-frame rotation handling, not tile-order reasoning.

**What the dataset does with this family.** The puzzle types are now generated as
`dataset/out_ru/LimboFilter/framed3x3` (384×384) and `LimboFilter/framed2x2` (256×256): the plugin's
**own** framed captcha - the Russian number spelled out in words on one canvas, cut into `WIDTH × HEIGHT`
maps of 128×128, each turned by a multiple of 90°. The old `GalleryCaptcha/ru-puzzle3x3` / `ru-puzzle2x2`
types, which cut a *picture* into a grid, have been **deleted**: the model behind them was wrong, and
the base art of the V4 / V5 / V53 sections is not the plugin's number body anyway - it is a
server owner's backplate (§2.6 of `reports/PUZZLE_OBJECT_FAMILIES.md`). The V52 sample is the one
catalogue section that *is* the plugin's own framed captcha, and it is the direct reference for
`framed3x3`.

### 3.3 Object captcha (V8)

A grid of small photos (mostly cats) filling the frame; the player must click every image of one
category - the classic "select all the cats" challenge. The photos are laid out as a justified
gallery: each is scaled to the 83-px cell width with its aspect ratio kept and anchored at the
cell's top-left, so a photo taller than the cell **overflows into the cell below**
(`s10/004.png` cell (1,1) is a pale wall with a white socket, and the photo - not the socket -
continues into (2,1)).

Seven of the fourteen samples are instead **flat colour blocks** (red/green/yellow/black/white in
the same 3×3 grid), i.e. the same *logic* rendered without photographs, which suggests two
different back-ends behind one product line. The swatch grid is **JPEG-encoded after the cells are
drawn**: every non-fill pixel that lies on a cell seam is on a seam where the fill changes across
it, and none is on a same-colour seam - per-swatch encoding would ring the red|red edges too. The
cell convention is **(row, column)**, as in §3.2; `tools/crop_grid.py` labels the same cells
(column, row).

### 3.4 Generic web captcha (V6)

70 images at **150×90**, in the classic web-captcha idiom: a short alphanum string, a random display font,
a random background (flat colour, gradient, noise, geometric pattern, photo), 3–5 coloured interference
lines, sometimes with a grid overlay. These are **not** Minecraft plugin output — they are what a website's
"are you human" widget produces. No plugin is responsible for these.

**There is no single generator for this section, and that is a measured result, not a guess.** The vendor's own
FAQ says the service handles "more than 6000 kinds of captchas from all over the internet", so the gallery is a
sample of a **corpus of real-world web captchas**, not the output of one renderer. The 70 samples betray it:

| property | measured |
|---|---|
| PNG colour model | 19 RGB, 41 RGBA, 10 palette (P) |
| distinct colours per image | 2 … 12 728 |
| string length | 3, 4, 5 **and** 6 |
| charset | digits-only, letters-only, mixed, and **Cyrillic** (`К243ЖК`) |
| per-character colours | present in several samples |
| backgrounds | white, flat, gradient, diagonal hatch, dots, graph paper, **photographs** |

A single renderer cannot produce that spread: hard-edged 2-colour dot-matrix samples coexist with fully
anti-aliased photo-background ones. Every neighbouring section (V2, V3, V4, V8) is uniform — V6 is the only
grab-bag in the catalogue. Measured borders: `059` is a 2 px **white rounded** frame, `012` a 2 px **black
square** frame over 16 px graph paper in `(208,208,208)`.

The candidate libraries were each measured from their source and each defaults to a different size —
Gregwar/Captcha 150×40, S1SYPHOS/php-simple-captcha 150×40, walijoy/captcha-generator 200×80,
akiraly/cage 200×70, captcha4j 200×50, easy-captcha 200×100, kaptcha 200×50, Securimage 250×75,
miraculx/captcha 190×90, base64Captcha 240×80, BotDetect 175×50, kuszaj/claptcha 100×30 — so none of them
produced this corpus either. The closest *algorithmic* match is walijoy/captcha-generator (same charset
literal, random length, per-character contrast colour, `lines()` + `writeNoise()` + `writeCurve()`, background
folder), which is the idiomatic shape of the corpus rather than its origin.

**Consequence for the dataset:** `GalleryCaptcha/ru-web` is a reconstruction of the **idiom**, not of a library, and
is labelled as such. If per-style fidelity is wanted later, the corpus splits into roughly eight style
families; the only global constants are the 150×90 canvas, the 3-6 character length range and the mixed-case
alphanumeric alphabet. Full measurements: `research/WEB_CAPTCHA_V6_FINDINGS.md`.

### 3.5 What the puzzle sections are actually built from

The reassembly work (`research/reassemble.py`, brute force over 60 000 frame permutations scored by seam
continuity) recovers coherent source pictures from the puzzle samples — the best permutation beats the
median random one by 2×-40×. The recovered sources are single web-captcha-style images, which confirms
the frames are **pieces of one base captcha**, not a separate renderer.

The question this section used to leave open is now closed, and the answer is not the one the older
write-ups assumed:

* **The base art is natively 250×150, not a 150×90 captcha scaled up by 5/3.** The lattice test
  (a nearest-neighbour 150→250 upscale can only change colour on the 5/3 lattice) scores 1.000 for a
  genuine nearest-neighbour upscale and 0.611 for a bicubic one, against 0.604–0.606 for the V4 / V5 /
  V52 / V53 samples themselves — `docs/adr/0001-dataset-is-kept-in-git.md` §V9. A 150×90 origin is refuted.
* **No frame matches any of the 70 V6 samples.** `research/puzzle_check.py` prints **NO MATCH** for all
  13 V5 puzzles; the best V53 candidates have a mean absolute error of 31–78 against the tool's own
  threshold of 12. The V5 / V53 base is a 250×150 web-captcha sub-family of its own — and, per §3.2,
  the whole family is LimboFilter's `FRAMED_CAPTCHA`.
* **The frames are separate 128×128 map items**, each rotated by a multiple of 90° with probability
  `FRAME_ROTATION_CHANCE` — not tiles of a picture shuffled around.

So the honest one-line description of the family is: **composite of some web-captcha renderer; the base
art is 250×150 and has not been identified.** The renderer *around* the base is identified (LimboFilter);
the base art's own renderer is not.

## 4. Do the site's styles overlap the dataset we already have?

**No — essentially not.** This was measured, not assumed.

`tools/match_site_to_dataset.py` downsamples every site image and every one of the 3400 generated
`dataset/out` images to 16×16 grayscale and takes the nearest neighbour, per site image, over the whole
dataset (`<gallery-refs>/site_matches.json`).

| Section | best-match distance (min / median) |
|---|---|
| V1 | 0.0228 / 0.1230 |
| V1.1 | 0.0231 / 0.0854 |
| V2 | 0.0231 / 0.0980 |
| V3 | 0.0303 / 0.0977 |
| V4 | 0.0781 / 0.1502 |
| V5 | 0.0332 / 0.1332 |
| V52 | 0.0562 / 0.0562 |
| V53 | 0.0900 / 0.1089 |
| V6 | 0.0304 / 0.0919 |
| V8 | 0.1042 / 0.1920 |

A distance of ~0.02 on a 16×16 grayscale vector is a 2 % mean per-pixel difference, i.e. a near-duplicate.
Exactly **three** of the 525 site images reach ≤ 0.025, and **every one of them was checked by eye and is
a false positive** — a white background with sparse dark text matches almost any other
white-background-with-text image at 16×16:

| section | file | nearest neighbour | distance |
|---|---|---|---|
| V1 | `136.png` | `Mrbysco/Captcha/math` | 0.0228 |
| V1.1 | `015.png` | `irootdev/AnBot/captcha` | 0.0231 |
| V2 | `001.png` | `irootdev/AnBot/captcha` | 0.0231 |

Example: site V1 #275 is Cyrillic `ЬЯШНИ` in a blackletter face on cream; its nearest neighbour is
`jonesdevelopment/sonar/complex` at **0.0282**, followed by `InstantlyMoist/Captcha/textcaptcha` at 0.0297
and 0.0307. (The `irootdev/AnBot` pairing at 0.0231 belongs to V1.1 #015 and V2 #001, not to V1 #275.)

**Conclusion: the site catalogue and the 18 plugins already in `dataset/out/` are disjoint.** The site is
therefore a source of *new* captcha families, not a validation set for the existing ones. That is the whole
reason to work through it.

## 5. Version → plugin mapping

| Version | Family | Responsible plugin | Confidence |
|---|---|---|---|
| V1, V1.1 | mixed grab-bag | no single plugin; a mix of web-captcha generators and assorted Minecraft plugins | — |
| V2 | Russian number-word captcha | **LimboFilter** (Elytrium) — `NUMBER_SPELLING` | identified, see §7.8 |
| V3 | Russian captcha, random Cyrillic | **LimboFilter** (Elytrium) — `NUMBER_SPELLING=false`, Cyrillic `PATTERN` | identified, see §7.8 |
| V4 | 3×3 framed captcha over artwork | **LimboFilter** `FRAMED_CAPTCHA` (3×3); the base art's own renderer is not identified | identified, base reconstructed |
| V5 | 3×3 framed captcha over web-captcha art | **LimboFilter** `FRAMED_CAPTCHA` (3×3); the base art is 250×150 and **not** the V6 samples | identified, base reconstructed |
| V52 | Russian number-word captcha in a 3×3 frame | **LimboFilter** `FRAMED_CAPTCHA` (3×3) over the V2 body | identified, see §7.8 |
| V53 | 2×2 framed captcha over web-captcha art | **LimboFilter** `FRAMED_CAPTCHA` (2×2); the base art is 250×150 and **not** the V6 samples | identified, base reconstructed |
| V6 | generic web captcha | **no plugin** — a website widget, not Minecraft | certain |
| V7 | — | section is empty on the site | — |
| V8 | object captcha | the object-captcha product line of the site operator, not identified upstream | reconstructed |

## 6. The reserved plugin folders

`dataset/out_ru/` reserves one folder per plugin name:

```
dataset/out_ru/
  BotFilter/  Captcha/  CaptchaGUI/  CaptchaVerifyZ/  LimboFilter/  SmartCaptcha/  WeatherActionCaptcha/
  GalleryCaptcha/                    <- the catalogue families reconstructed from the samples
```

Each folder holds a `real_shots/` directory - the real screenshots of that plugin, used as the
reference for the reconstruction - and the generated `<type>/` samples. The `GalleryCaptcha` type group is not a plugin -
it is the catalogue itself; its sub-folders are the captcha families the catalogue is built from,
each with the site's own samples in `real_shots/` as the reconstruction reference. `LimboFilter/` was
added when the plugin behind the Russian family and the framed sections was identified; it holds the
**renderer's own output** (the map, the symbols, the framed captchas) next to the catalogue's
rotatable-frame sections.

The reference inventory, measured (1 240 images in all):

| folder | `real_shots/` | contents |
|---|---|---|
| `GalleryCaptcha/real_shots/` | 674 PNGs in 6 sub-dirs | the catalogue, grouped per family, plus the whole 525-image catalogue under `catalogue/` |
| `LimboFilter/real_shots/` | 49 PNGs in 2 sub-dirs | the catalogue's rotatable-frame sections: `framed3x3/` (42 = V52 1 + V4 28 + V5 13) and `framed2x2/` (7 = V53) |
| `BotFilter/real_shots/` | 510 PNGs | the real upstream BotFilter renders (file name = the answer) |
| `CaptchaVerifyZ/real_shots/` | 5 PNGs | the reference renders of the upstream CaptchaVerifyZ algorithm |
| `WeatherActionCaptcha/real_shots/` | 2 PNGs | two video frames of the plugin (evidence, not captcha samples) |
| `Captcha/real_shots/` | **empty** | the reserved name is still ambiguous - there is nothing to keep yet |
| `CaptchaGUI/real_shots/` | **empty** | the plugin renders no image, so there is nothing to photograph |
| `SmartCaptcha/real_shots/` | **empty** | the plugin renders no image, so there is nothing to photograph |

Every `real_shots/` folder carries a `README.md` (a `README.txt` for the WeatherActionCaptcha one)
that says what the folder is for and where the images come from. The images are put back by
`python tools/restore_real_shots.py` after a regeneration; the notes are re-created by the same
script when they are missing.

## 7. Plugin identification results

| Reserved name | Found? | What it is | Image captcha? |
|---|---|---|---|
| `CaptchaVerifyZ` | **yes** | [Modrinth](https://modrinth.com/plugin/captchaverifyz) / [Spigot](https://www.spigotmc.org/resources/captchaverifyz-1-21-x-26-x.125355/), author `mateita254` (`Mateitaa1`), package `com.Mateitaa1.CaptchaVerifyZ` | **yes** - a 128x128 *map* captcha |
| `CaptchaGUI` | **yes** | [github.com/Supl1n/CaptchaGUI](https://github.com/Supl1n/CaptchaGUI), package `me.supl1na.captcha` | no - an inventory GUI captcha (click the emerald block) |
| `SmartCaptcha` | **yes** | [Spigot 70935](https://www.spigotmc.org/resources/70935), author `CommandSender` (`elapsed0`) | **no** - a chest-GUI captcha, there is no image at all |
| `BotFilter` | **yes** | [github.com/Leymooo/BungeeCord](https://github.com/Leymooo/BungeeCord) ("BungeeCord with built in AntiBot protection. (RUS lang)"), author *Leymooo* (Vjatšeslav Maspanov), package `ru.leymooo.botfilter` | **yes** - a 128x128 *map* captcha with a 4-5 digit answer |
| `Captcha` | **ambiguous** | SpigotMC alone has a dozen resources called *Captcha*; the Russian one that actually renders an image is [UCRAFTS/CaptchaPlugin](https://github.com/UCRAFTS/CaptchaPlugin) (author *oDD1 / Alexander Repin*), whose renderer is the npm package `gm-captcha` | **yes** - 512x256 JPEG on a map (Cyrillic charset) |
| `WeatherActionCaptcha` | **yes** | [SpigotMC.RU 3275](https://spigotmc.ru/resources/weatheractioncaptcha-luchshaja-kapcha-dlja-zaschity-servera-vypolni-dejstvie-i-projdi-na-server.3275/), author "Любитель Метала" (`verylovemetal`); the advertised GitHub repo **404s and the account no longer exists** | **no** - an *action* captcha, it renders no image at all |

### 7.1 CaptchaVerifyZ - fully specified, and verified pixel-identical

The upstream renderer is `com/Mateitaa1/CaptchaVerifyZ/CaptchaVerifyZ.java`, inner class
`CaptchaMapRenderer`, method `render(MapView, MapCanvas, Player)`. It draws the Minecraft
map the player receives as a filled-map item:

| | |
|---|---|
| Canvas | 128x128, `TYPE_INT_RGB` |
| Background | solid `Color.DARK_GRAY` (64,64,64) |
| Header | `Color.WHITE`, Arial **BOLD 12**, `"SECURITY VERIFICATION"`, x=5, baseline y=20 |
| Code | `Color.YELLOW`, Arial **BOLD 24**, x = `(128 - stringWidth(code)) / 2`, baseline y=70 |
| Footer | `Color.LIGHT_GRAY`, Arial **PLAIN 10**, `"Type the code in chat"`, x=15, baseline y=100 |
| Charset | `ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789`, length 5 |
| Noise | **none** - no lines, no curves, no rotation, no jitter, no anti-aliasing hints |
| Assets | **none** - the current release (1.4-2) ships 3 classes plus `config.yml` and `plugin.yml`; the earlier 1.0 / 1.1 / 1.2 releases are shaded fat jars (4 669 classes) and carry no assets either |

**Licence:** `LicenseRef-All-Rights-Reserved` on Modrinth, so the project's generator is a
**clean-room** reimplementation - the algorithm was read from the decompiled renderer and
rewritten, and no upstream code is carried over.

**Two upstream defects, reproduced on purpose:**

1. **The header is clipped.** The header measures 137 px and is drawn at x=5 on a 128 px
   canvas, so it runs to x=142 and the last characters are cut off. The reference renders
   read `SECURITY VERIFICATIO...`. The project's generator clips it the same way.
2. **The answer is also printed in chat** - the default `messages.welcome` contains
   `"&a&l➤ &f&l{captcha}"`, and `messages.incorrect-attempt` repeats it. The image
   challenge is therefore bypassable by reading the chat window. Verification itself is
   `message.equalsIgnoreCase(correctCaptcha)` - case-insensitive but an exact match.

**Verification.** The upstream algorithm was re-rendered five times by
`research/RefRender.java` (`research/refout/`), and the project's generator
(`dataset/generator_ru/dev/captcha/gens/CaptchaVerifyZ.java`) was re-rendered with the
same five codes by `research/DiffCaptchaVerifyZ.java`. All five are **pixel-identical**:
0 differing pixels out of 16384, and the MD5 of the PNG matches in every case.

The renderer's **bytecode** is identical across every published version, so one reimplementation
covers every release. Measured over all **twelve** versions on Modrinth (1.0.0 - two builds - 1.1,
1.2, 1.2-1, 1.3, 1.3-1, 1.3-2, 1.3-3, 1.4, 1.4-1, 1.4-2): the renderer class is 2 107 bytes in
every one of them and `javap -p -c` output is **identical** (one single hash). "Byte-identical"
would be too strong - the class files differ, because the source line-number table differs
(`javap -v` diffs show only `line NNN: X` entries changing). The packaging did change, and it is
worth getting the attribution right: **1.0, 1.1, 1.2 and 1.2-1 are shaded fat jars** (4 669
classes) and **1.3, 1.4 and 1.4-2 are slim** (3 classes). The fat-jar-ness is therefore not what
distinguishes 1.2.

### 7.2 SmartCaptcha - a GUI captcha with no image

`SmartCaptcha` opens a chest inventory on join, titled from the config key
`captcha-gui-name` (e.g. `Click the %block%`). The top slot holds the real item (the
arrow by default) and the other slots hold random decoy blocks (ice by default); clicking
the right one authenticates the player. Its config has **no** image, texture, skull,
canvas, font or charset key - only `kick-after`, `fail-kick`, `captcha-gui-name`,
`captcha-real-item`, `captcha-fake-item` and message keys. The plugin icon is the generic
Minecraft "hand" icon.

There is therefore **no canvas, charset, font, noise pass or caption to reimplement**.
Writing a "SmartCaptcha image generator" would be an invention rather than a
reimplementation, so this plugin is documented here instead of being generated. The
threat it targets is console clients, which cannot click a GUI slot - an image captcha
would be the wrong tool by construction.

**What this claim rests on: the README / config evidence only.** The plugin's jar was never
byte-inspected - the Spiget CDN serves a **0-byte** object
(`https://cdn.spiget.org/file/spiget-resources/70935.jar`, `x-bz-content-sha1` =
`da39a3ee5e6b4b0d3255bfef95601890afd80709`, the SHA-1 of the empty string), the local copy
`research/jars/SmartCaptcha-70935.jar` is 0 bytes, and `spigotmc.org` answers **HTTP 503
site-wide**. What the README does say is enough: the decoded upstream description contains no
image / texture / skull / canvas / font / charset key, and the config has only
`kick-after`, `fail-kick`, `fail-kick-msg`, `captcha-gui-name`, `captcha-real-item`,
`captcha-fake-item`, `authentication-msg`, `config-reload-msg` and `no-permissions-msg`.
The plugin icon is the generic Minecraft "hand" icon
(`data/resource_icons/70/70935.jpg`), i.e. no captcha artwork to fingerprint either.

### 7.3 CaptchaGUI - an inventory GUI captcha

`Supl1n/CaptchaGUI` opens a 9-slot inventory titled `Captcha` one second after join and
puts a single emerald block, named `§a¡Click here!`, in a random slot between 1 and 7
inclusive. Clicking it clears the check; clicking anything else kicks the player with
`¡Nope!`. The project's generator renders that GUI and its answer is the slot index.

### 7.4 WeatherActionCaptcha - an action captcha, not an image captcha

The author says it outright: *"Так как боты научились уже обходить капчу в виде картинок
перед ними… я решил сделать капчу, где нужно выполнить какое то действие"* - "because bots
had already learned to bypass captchas in the form of pictures, I decided to make a
captcha where you have to perform an action". The player is dropped into a prepared world
and has to perform a task - the upstream page names only the blocks that will be there,
*"в котором будут нужные блоки, по типу верстака для крафта или стола зачарования"* ("a
crafting table, an enchanting table") - within a time limit shown on a boss bar
(`У вас есть N секунд, чтобы войти.`).

**No count of blocks, and no coal, is claimed here.** The upstream page does not name a
number and does not mention coal, and a repo-wide search for "coal" / "уголь" finds only
the sentence that is being corrected now. The two frames kept as evidence show no coal
either. What *is* confirmed is the boss-bar text, by the second frame.

There is no canvas, no charset, no font, no noise pass and no caption: there is nothing to
reimplement. The upstream GitHub repository `verylovemetal/WeatherActionCaptcha` **404s and
the account no longer exists** (the GitHub API answers 404 for `/users/verylovemetal`, with
no redirect - which is consistent with a deletion but is formally indistinguishable from a
rename), and the Wayback Machine, Software Heritage, authenticated GitHub code search and
every mirror tried hold no copy of it. **No generator is provided for this plugin** -
inventing one would be an invention, not a reimplementation.

**What this claim rests on: the page text, the author's own statement and two video frames
- not on the jar.** spigotmc.ru only serves the download to a logged-in account, so the jar
was never obtained, and the source repository is gone. The two frames in
`dataset/out_ru/WeatherActionCaptcha/real_shots/` are:

| frame | what it actually is | source |
|---|---|---|
| `yt_62jp1hEeSFk.png` | a **promo title card** - a small floating world with a crafting table, an enchanting table, a chest and a furnace, under the plugin's own banner. Marketing material, not gameplay. | <https://www.youtube.com/watch?v=62jp1hEeSFk> - *"ПРОВЕРКА НА БОТА / ЗАЩИТА СЕРВЕРА / WEATHERACTIONCAPTCHA ОБЗОР ПЛАГИНОВ #1"*, channel *IlyosYT* (<https://www.youtube.com/@faynerYT>) |
| `yt_a3_VRVRGuEc.png` | a **bot-client debug overlay** (NeoWare 2.3.0) on `play.reserv.fun` - the *attacker* side, not a player doing the task. It is the frame that confirms the boss bar reads `У вас есть 48 секунд, чтобы войти.` | <https://www.youtube.com/watch?v=a3_VRVRGuEc> - *"WeatherActionCaptcha passing \| NeoWare Client"*, channel *KrytickYT* (<https://www.youtube.com/@krytickyt>) |

The video titles and channels were recovered from YouTube's oEmbed endpoint
(`https://www.youtube.com/oembed?url=…&format=json`) on 2026-10-21, so the frames are attributed
rather than anonymous.

### 7.5 BotFilter - located: the Russian BungeeCord antbot with a 128x128 map captcha

`BotFilter` is the only one of the six that is *both* Russian-language *and* renders an
image. The authoritative upstream is

* **<https://github.com/Leymooo/BungeeCord>** - "BungeeCord with built in AntiBot
  protection. (RUS lang)", author *Leymooo* (Vjatšeslav Maspanov), package
  `ru.leymooo.botfilter`, branch `master`, last push 2026-09-29. It is a **BungeeCord proxy**
  plugin (a fork of `SpigotMC/BungeeCord`), not a Bukkit/Spigot plugin. Licence: the
  md_5/BungeeCord **BSD 2-clause** plus the clause *"You may not use the software for
  commercial software hosting services without written permission from the author."*
  (GitHub therefore reports `NOASSERTION`).
* The same code is in three forks — the captcha **sources** are identical (`research/RU_CAPTCHA_SOURCES.md`
  §"Raw sources"): `Ymxer/BotFilter` (Chinese), `Loyisa/BungeeCord-BotFilter-ZHCN` (Chinese),
  `DionaMC/BungeeCord-BotFilter-ENG` (English). Update checks point at the ZHCN fork. The claim is
  about the sources, not about the compiled class files, which — as with every Java build — differ in
  their line-number table.
* Distribution links in the README: RuBukkit thread <http://www.rubukkit.org/threads/137038/>
  and a Yandex Disk jar.

The renderer:

* `proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/CaptchaPainter.java`
  - `draw(Font, Color, String)`, `createImage()`, `configureGraphics()`,
    `draw(Graphics2D, String)`, `transform()`, `postProcess()`
* `proxy/src/main/java/ru/leymooo/botfilter/captcha/CaptchaGeneration.java`
  - `generateImages()`, `randomNotWhiteColor()`, `randomAnswer()`
* `.../captcha/generator/Rippler.java` - `filter(src, dest)`
* `.../captcha/generator/map/CraftMapCanvas.java` - `drawImage(x, y, image)`
* `.../captcha/generator/map/MapPalette.java` - `colors[]`, `prepareColors()`,
  `imageToBytes()`, `matchColor()`

Algorithm: 128x128 `TYPE_3BYTE_BGR` canvas on a **solid white** background (no background
asset); the answer is a random 4- or 5-digit number (1000-9999 or 10000-99999, 50/50); the
font is one of `SANS_SERIF/PLAIN/50`, `SERIF/PLAIN/50`, `MONOSPACED/BOLD/50`; the whole text
gets one colour taken from the Minecraft map palette with six near-white entries re-rolled;
per-glyph rotation starts at +-pi/16 and steps by up to 3pi/8 with a p=0.25 direction flip, and
the spacing between glyphs is squeezed by 0.27-0.32 of the narrower glyph; the glyphs are
scaled to ~89-94 % of the width and ~68-73 % of the height and get one outline stroke offset
by at most 0.64 px horizontally and 1.83 px vertically; then a **ripple** (vertical wave
amplitude `height/10`, horizontal `width/100`) and a **3x3 random blur kernel** (nine
`rnd.nextFloat()` weights normalised to 1, `EDGE_NO_OP`); finally the image is quantised to
the Minecraft map palette, which is what the player actually sees. **No caption is drawn on
the image** - the instruction is a chat message.

900 captchas are pre-generated at proxy start-up and cached as map packets.

One caveat worth recording: a separate, *paid* SpigotMC resource,
[BotFilterPlus](https://www.spigotmc.org/resources/botfilterplus.109765/) (May 2023), is
described as *"a regular botfilter but with a custom captcha"* and asks the server owner to
supply *"a 128 x 128 background picture"* - i.e. it is a fork of this BotFilter with a
configurable background image instead of the solid white one. Its jar was never published to
GitHub and the resource page is not in the Wayback Machine, so the variant could not be
diffed; the upstream algorithm above is the one documented in Leymooo's own repository.

**510 real upstream renders** were recovered from
<https://github.com/ServerSideProject/botfilter_captcha_dataset> (MIT, 2022) - a `.rar` with
128x128 PNGs whose **file name is the answer** (`1024.png` -> `1024`). They are now in
`dataset/out_ru/BotFilter/real_shots/` (see the `README.md` there) and the archive is kept in
`research/jars/`.

**The generator exists.** `dataset/generator_ru/dev/captcha/gens/BotFilter.java` is a clean-room
rewrite of the algorithm above (the licence is BSD-with-an-extra-clause, so a clean-room rewrite
is the house style) and it produces `dataset/out_ru/BotFilter/map/` - 100 samples whose
`labels.jsonl` names `ru.leymooo.botfilter.captcha.generator.CaptchaPainter#draw` as the source.
The distribution check against the 510 real renders is in `docs/adr/0001-dataset-is-kept-in-git.md` §V4:
median distinct colours 13.0 (real) vs 13.5 (generated), ink coverage 41.6 % vs 41.3 %, ink
bounding box 121x110 vs 120x108. Note that the reference set is the *pre-quantisation* painter
output (anti-aliased blends) while the generator emits the palette-quantised map data, which is
what the player sees.

### 7.6 "Captcha" - which one? (ambiguous, and the only Russian one that draws an image)

There is no single "the Russian Captcha plugin"; SpigotMC has a dozen resources named
*Captcha* and they are mostly GUI plugins with no image at all:

| SpigotMC | Source | Renders an image? |
|---|---|---|
| [captcha.75891](https://www.spigotmc.org/resources/captcha.75891/) | [InstantlyMoist/Captcha](https://github.com/InstantlyMoist/Captcha) (`me.kyllian.captcha`), author *Kyllian* | yes - a map captcha, **already in the dataset** as `InstantlyMoist/Captcha` / `textcaptcha` |
| [captcha.103993](https://www.spigotmc.org/resources/captcha.103993/) | [reidjJava/Captcha](https://github.com/reidjJava/Captcha) | no - inventory GUI |
| [captcha.120533](https://www.spigotmc.org/resources/captcha.120533/) (= Modrinth `captcha`, id `xXOC18H0`) | author *Aznos* | no - stained-glass GUI |
| [captcha.77939](https://www.spigotmc.org/resources/captcha.77939/) | [Nicbo/Captcha](https://github.com/Nicbo/Captcha) - **the GitHub repo now 404s** | no |
| [captcha.84509](https://www.spigotmc.org/resources/captcha.84509/) | [max11-dev/Captcha](https://github.com/max11-dev/Captcha) - **the GitHub repo now 404s** | no |
| [captcha.86350](https://www.spigotmc.org/resources/captcha.86350/) | [DevSakio/Captcha](https://github.com/DevSakio/Captcha) | no |

(The two dead GitHub links are the ones the SpigotMC pages pointed at when they were read; the
repositories 404 with no redirect, i.e. they are gone rather than renamed. The other source
repositories in the table still resolve.)

The one genuinely Russian plugin in that family that **does** draw an image is
`UCRAFTS/CaptchaPlugin` (author *oDD1 / Alexander Repin*): it fetches a JPEG captcha from
`UCRAFTS/CaptchaService` (Express + Redis) and shows it on a map item. The renderer is the
npm package **`gm-captcha` 1.0.2** (<https://github.com/eidonjoe/gm-captcha>, MIT), driven by
the service's `.env`:

```
CAPTCHA_LENGTH=5
CAPTCHA_PATTERN=йцукенгшщзхъёэждлорпавыфячсмитьбю1234567890
CAPTCHA_WIDTH=512
CAPTCHA_HEIGHT=256
CAPTCHA_BACKGROUND=#bca881
CAPTCHA_WORLD_SPACING=64
CAPTCHA_MAX_SWIRL=128
CAPTCHA_MAX_SHEAR=8
CAPTCHA_FONT_SIZE=64
```

and `app/utils/text.js` builds the answer from that pattern - **Russian keyboard layout,
lower case, plus digits**, each character independently upper-cased with p = 0.5. Upstream
defects to preserve: the loop `for (let i = 0; i <= length; i++)` emits **length + 1 = 6**
characters for a configured length of 5, and the service passes `lineCount = -1` and
`pointCount = -1` to `gm-captcha`, whose loops `for (i = 0; i < lineCount; i++)` therefore
draw **no interference lines and no noise points at all**. The image is a solid `#bca881`
background with six characters at x = 0, 64, 128, 192, 256, 320, baseline y = 64, each with a
random outline colour and a random swirl/shear distortion; the font is the bundled
`font/DroidSansFallback.ttf` at size 64 - but `.font()` is queued **after** `.drawText()`, so
the first character is drawn with the default GraphicsMagick font.

None of this matches the 250x150 catalogue families, and the number-word family in
sections V2/V3 is now known to be **LimboFilter** (§7.8) - a Velocity plugin, and not one of
the six reserved names - so the reserved `Captcha/` folder still needs a decision: either the
uCrafts plugin above (the only Russian image renderer found) or a plain "no image, GUI only"
note like SmartCaptcha.

### 7.7 A correction to the premise

None of the three identified plugins contains a single Russian string - `CaptchaVerifyZ`
and `SmartCaptcha` are entirely English, and `CaptchaGUI` uses `¡Click here!`. The
Cyrillic captchas in sections V2, V3 and V52 are a **different** family - and since §7.8
that family is identified too: it is **LimboFilter**, a Velocity anti-bot plugin, which is
again not one of the six reserved names.

### 7.8 LimboFilter - the plugin behind the Russian family and the "puzzle" sections

The number-word family (V2, V3, V52) and the framed "puzzle" sections (V4, V5, V52, V53) are
produced by **LimboFilter** by *Elytrium* (<https://github.com/Elytrium/LimboFilter>,
AGPL-3.0), a **Velocity** anti-bot plugin, sold on SpigotMC.RU as part of the
LimboAPI / LimboAuth / LimboFilter family. The renderer lives in
`net.elytrium.limbofilter.captcha.CaptchaGenerator` and
`net.elytrium.limbofilter.captcha.painter.CaptchaPainter`.

The full identification, with the evidence, is in `reports/LIMBOFILTER_IDENTIFICATION.md`. The
parts that matter here:

* **The number is spelled out in words, one word per line** - upstream's
  `NUMBER_SPELLING` + `EACH_WORD_ON_SEPARATE_LINE` pair, and `randomAnswer()` returns
  `Pair.of(spellNumber(value), String.valueOf(value))`: the map shows the *words*, the player
  has to type the *digits*. That is exactly the catalogue's `ВВЕДИТЕ ТОЛЬКО ЦИФРЫ` /
  `НАПИШИ ЦИФРАМИ` captions.
* **A word is never split, it is clipped** - the half-cut «т» of «восемьдесят» in
  `s02/013.png` is the single most diagnostic artefact of the family.
* **The black interference curves are LimboFilter's** - `CubicCurve2D.Double` curves,
  `CURVES_AMOUNT` 3, `CURVE_SIZE` 2, `CURVES_COLORS` `["000000"]`.
* **The multi-coloured words are the gradient mode**, not a per-word colour list.
* **The 250x150 catalogue PNGs are the gallery's own composites** of the 128x128 map plus a
  chat/title overlay; the captions are chat strings, not renderer output.
* **The "puzzle" sections are `FRAMED_CAPTCHA`** - see §3.2.

Because the plugin is a Velocity proxy plugin and not one of the six reserved names, it had no folder of
its own in `dataset/out_ru/`; it now has one - `dataset/out_ru/LimboFilter/` - because the generator
rewrites it faithfully enough to be worth shipping as the plugin's own output. `GalleryCaptcha/` keeps the
**gallery's presentation** of the same map (the 250×150 composite with the caption).

## 8. What was built out of this

`dataset/out_ru/` (1 200 images, 12 captcha types x 100):

| Folder | Type | Provenance | Mode |
|---|---|---|---|
| `LimboFilter/map` | the Russian number spelled out in words, one word per line, clipped at the right edge, black bezier curves over it, on a 128x128 Minecraft map | upstream source, read directly | **clean-room** |
| `LimboFilter/symbols` | the same plugin in its `PATTERN` mode: three characters of the Cyrillic alphabet on a 128x128 map | upstream source, read directly | **clean-room** |
| `LimboFilter/framed3x3` | `FRAMED_CAPTCHA`: the number-word body on a 384x384 picture, cut into nine 128x128 maps, each turned by a multiple of 90 degrees | upstream source, read directly | **clean-room** |
| `LimboFilter/framed2x2` | the same on a 256x256 picture, cut into four maps | upstream source, read directly | **clean-room** |
| `GalleryCaptcha/ru-numberword` | the gallery's composite of a LimboFilter map at 250x150, without the caption | reconstructed from the reference screenshots | reconstructed |
| `GalleryCaptcha/ru-numberword-caption` | the same plus a caption (`ВВЕДИТЕ ТОЛЬКО ЦИФРЫ`, `ВВЕДИТЕ ЦИФРЫ С КАРТИНКИ В ЧАТ`, `ВВЕДИТЕ СИМВОЛЫ`) | reconstructed | reconstructed |
| `GalleryCaptcha/ru-symbols` | the gallery's composite of a LimboFilter **symbol** map plus the caption | reconstructed | reconstructed |
| `GalleryCaptcha/ru-web` | the 150x90 web captcha: a mixed-case alphanumeric over a decorated background | reconstructed | reconstructed |
| `GalleryCaptcha/ru-object-swatch` | the 3x3 grid of flat colour fills with JPEG ringing; a colour-picking task, not OCR | reconstructed | reconstructed |
| `BotFilter/map` | the 128x128 map captcha with a 4-5 digit answer | upstream source, read directly | **clean-room** |
| `CaptchaVerifyZ/map` | the 128x128 map captcha | upstream source, decompiled | **clean-room, pixel-verified** |
| `CaptchaGUI/clickblock` | the 9-slot inventory GUI with the emerald block | upstream source, read directly | **clean-room** |

The answer of every `ru-numberword*` and `LimboFilter/map` sample is the digits the spelled-out number
stands for; the answer of `ru-web` and of `LimboFilter/symbols` is the character string; the answer of
the framed types is the digits the number stands for, but it lies in **turned frames** and needs a
solver step (turn the frames, reassemble, then read); the answer of `ru-object-swatch` is the colour to
click; the answer of `BotFilter/map` and `CaptchaVerifyZ/map` is the code; the answer of
`CaptchaGUI/clickblock` is the slot index.

`dataset/out_ru/GalleryCaptcha/real_shots/` holds the catalogue's own samples, grouped by the
family they are the reference for, plus the full 525-image catalogue under
`real_shots/catalogue/`. `dataset/out_ru/LimboFilter/real_shots/` holds the catalogue's
rotatable-frame sections.

**Known issues in the shipped samples — and what has been fixed since.** The generator tree was
audited separately (`docs/adr/0001-dataset-is-kept-in-git.md`), and that review found real defects in the generated
data. The findings are kept as they were written; this is what has happened to each of them since:

* an off-by-one in the Russian number spelling, so the drawn word disagreed with the label in 183 of the
  200 shipped `ru-numberword*` samples (**still open at the time of the review**) — **fixed**: the
  spelling is now a 1-based units table plus a separate teens table, `tools/check_labels_and_roi.py`
  re-derives every number's spelling independently of the generator, and the shipped tree measures
  **0 mismatches**;
* the letters of the 2x2 base were never positioned, so the shipped `ru-puzzle2x2` samples carried blobs
  but no text (**still open at the time of the review**) — **obsolete**: `PuzzleCaptcha.java` and the
  `ru-puzzle*` types are gone; the puzzle family is now LimboFilter's `FRAMED_CAPTCHA`, generated as
  `LimboFilter/framed3x3` / `framed2x2`;
* the answer colour was missing from the grid in 12 of the 100 shipped `ru-object-swatch` samples (the
  generator has been fixed, but those samples predate the fix) — **fixed in the generator and in the
  shipped tree**: the fills are drawn first and the target is then chosen as the **minority** colour
  that is actually in the grid;
* `ru-symbols` was a misreading of its reference (**still open at the time of the review**) — **fixed
  differently than the review suggested**: the symbol family turned out to be a *LimboFilter* captcha
  too (catalogue section V3 is the plugin in its `PATTERN` mode), so `ru-symbols` is now the gallery's
  composite of `LimboFilter/symbols` and the ground truth is that symbol string.

Nothing in this section should be read as a claim that every shipped sample is correct; the affected
samples have to be regenerated once the generators are fixed.

