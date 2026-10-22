# The GalleryCaptcha puzzle (V4/V5/V52/V53) and object (V8) captcha families — upstream hunt

**Status:** the **puzzle** family is **identified** — it is **LimboFilter** by *Elytrium*
(<https://github.com/Elytrium/LimboFilter>), a **Velocity** anti-bot plugin, AGPL-3.0. The
**object** family (V8) is still **not identified**; it is a *web* widget, not Minecraft software.
Everything below was measured from `site/captchas/` (the the reference gallery) and from public
code search.

Companion document: `reports/SITE_CAPTCHAS.md` (catalogue inventory, version → plugin table) and
`reports/LIMBOFILTER_IDENTIFICATION.md` (the full LimboFilter write-up).

> **What changed since this document was written (2026-10-21, later the same day).** The identification
> below was right, and the dataset now follows it: the `ru-puzzle3x3` / `ru-puzzle2x2` types and
> `PuzzleCaptcha.java` are **gone**, and the puzzle family is generated as LimboFilter's own
> `FRAMED_CAPTCHA` - `dataset/out_ru/LimboFilter/framed3x3` (384×384) and `LimboFilter/framed2x2`
> (256×256). The old generator modelled the family as a *picture cut into a grid and permuted*; the
> upstream cuts one picture into `WIDTH × HEIGHT` **maps of 128×128** and **turns each map on its own**,
> without a permutation step. §6 below is the advice that was acted on.

---

## 1. Headline

* The **puzzle** family (V4, V5, V52, V53) is **LimboFilter's `FRAMED_CAPTCHA`**. The captcha is
  rendered on a canvas of `128·WIDTH × 128·HEIGHT` pixels and handed to the player as
  **`WIDTH × HEIGHT` separate 128×128 map items**; with probability
  `FRAMED_CAPTCHA.FRAME_ROTATION_CHANCE` each of those frames is **rotated by a random multiple
  of 90°** before it is sent. The player therefore gets a set of separate map frames to *turn* -
  not a jigsaw to be put back together, and the plugin never shuffles the frames.
* The **object** family (V8) is the classic web widget "click every photo of one category",
  rendered as a justified photo gallery. No upstream was found.

The catalogue page names product lines, never software:

---

## 2. Family A — the framed captcha (the "puzzle" sections)

### 2.1 Geometry (measured)

| | canvas | frames | frame size | boundaries in the composite |
|---|---|---|---|---|
| V4, V5 | 250×150 | 3×3 | 83×50 | x {0, 83, 167, 250}, y {0, 50, 100, 150} |
| V53 | 250×150 | 2×2 | 125×75 | x {0, 125, 250}, y {0, 75, 150} |

Derived from per-column / per-row gradient seams (exact thirds: 250/3 = 83.33 → 83, 167; 150/3 = 50),
and confirmed by the flat-colour V8 samples, whose blocks land exactly on those lines.

**Cell convention.** The cells are quoted as **(row, column)**, 1-based from the top left - so
"(2,2)" is the middle cell of a 3×3 grid. `tools/crop_grid.py` labels the same cells
**(column, row)** (it prints the column number along the top edge and the row number down the
left edge), so a cell quoted here has to be transposed before it is looked up in that tool's
output.

### 2.2 The base art is natively 250×150, not a 150×90 image blown up 5/3

The base art is **250×150 web-captcha art** (a different sub-family of the V6 idiom: big
decorated text on a white or graphic field). Two independent measurements:

* **No frame matches any of the 70 V6 samples.** `research/puzzle_check.py` cuts each puzzle on
  exact thirds and looks for a frame-by-frame match against the V6 set: it prints **NO MATCH**
  for **all 13** V5 samples, and the best candidates for the V53 samples have a mean absolute
  error of **31–78** against the tool's own match threshold of 12 - 8–10× the error of a true
  match.
* **The 5/3 lattice is absent.** A nearest-neighbour 150→250 upscale can only change colour on
  the 5/3 lattice. Measured as "the fraction of colour-change positions on that lattice,
  maximised over phase", a genuine 150×90 → 250×150 nearest-neighbour upscale scores **1.000**
  and a bicubic one **0.611** (chance level), while the V4 / V5 / V52 / V53 samples score
  **0.604–0.606** over the whole image and 0.611–0.643 per frame, with **no** frame above 0.9
  (`docs/adr/0001-dataset-is-kept-in-git.md` §V9). The reference pictures are 250-space strokes, not
  staircase-blocky 150-space ones.

The reassembled sources say the same thing: `research/reassembled/V53_007.png` is a natively
250×150 teal/flame artwork carrying the text "31".

### 2.3 The frames are turned, not shuffled

* **Rotation (proven).** `s04/003.png` cell (2,2) holds the Minecraft logo upside down; rotating
  that cell 180° makes it read "…ecraft" upright (`tools/tile.py` → `tmp/tile_003_22_rot180.png`).
  `s05/002.png` shows three text fragments in three different orientations (180°, 90°, 0°) in three
  adjacent cells - per-cell rotation, not one global rotation. Upstream this is
  `FRAME_ROTATION_CHANCE` and `for (int j = 0; j < random.nextInt(4); ++j) this.rotate(mapData);`
  in `CaptchaGenerator.genNewPacket`.
* **The plugin does not shuffle the frames.** It splits the canvas into `WIDTH × HEIGHT` map
  items in order (`map.getMapData(mapId, …)`) and rotates each of them independently. The
  catalogue's grid is the gallery's own composite of those frames, in the same order.
* **The catalogue's frames are in place.** Putting `s04/003.png` back together without moving a
  single cell and turning each cell back the way it was turned gives a coherent picture again
  (a Minecraft scene with the word "legacy" in the corner), and the same holds for
  `s04/005.png` (the Goku cutout). The brute-force jigsaw solver (`tools/jigsaw2.py`,
  `tools/jigsaw3.py` - all 9! arrangements scored by seam continuity) cannot show this, because
  it tries only one **global** rotation for the whole picture: with a turn per frame every
  arrangement scores badly (best 381.9 for `s04/003.png`, where a coherent picture scores far
  lower). That negative result is a property of the solver, not evidence of a permutation - and
  the older "the tiles are permuted" reading of the sections should not be repeated: the plugin
  has no permutation step at all.

### 2.4 The "coloured digits / letters" are the captcha's OWN text

They are **not** overlaid on the frames. They are the base web captcha's text, chopped by the
frame edges.

| sample | ink colour | px | evidence |
|---|---|---|---|
| `s05/001.png` | `#B40000` (180,0,0) | 3998 ink px (red mask) | red fragments straddle the 83-px lines, in all 9 cells |
| `s07/001.png` (V53) | `#D06D8E` (208,109,142) | 1651 ink px (pink mask; `#D06D8E` itself 571 px) | pink fragments straddle the 125-px lines |
| `s07/001.png` artwork | `#5CDBD5` (92,219,213) | 6996 px | the captcha's own drawing |

(The masks are the two in `tools/glyphs.py`, which picks them from the **exact** API version:
V5 → red, V53 → pink. A substring test on `"V5"` would also match `"V53"`, which is why the tool
now matches the version number itself.)

So the answer for V5 / V52 / V53 is the **recovered character string** (hence BARE's split by
charset: Latin+digits vs Cyrillic); for V4 it is the frame order and the turns.

### 2.5 V4 source art

Anime / game artwork and Minecraft screenshots. Where the source PNG is transparent the renderer
leaves a flat fill of **`#146032` (20,96,50)** - `s04/005.png`: 12181 px = 32.48 % of the canvas.
Strong fingerprint.

In `s04/005.png` (the Goku cutout on a flat green field) the **sprite fragments are in all nine
cells**: the flat `#146032` covers 75.6 %, 55.1 %, 27.9 %, 73.9 %, 36.7 % and 23.7 % of the six
outer-column cells, but only 0.0-0.4 % of the three middle-column cells. The old reading - "the
sprite's pieces in the middle column and the flat field in the outer columns" - described the
proportions, not the picture: the cutout simply reaches further into the middle column. The
flat field is the transparent part of the source artwork, which is why it is patchy.

### 2.6 Upstream: LimboFilter (AGPL-3.0, Velocity)

| | |
|---|---|
| Name | **LimboFilter** (Velocity) - part of the *LimboAPI / LimboAuth / LimboFilter* family |
| Author | **Elytrium**; the Russian-facing SpigotMC.RU resource is posted under the alias *hevav* |
| Upstream | <https://github.com/Elytrium/LimboFilter> (branch `master`) |
| Licence | **AGPL-3.0** |
| Renderer | `net.elytrium.limbofilter.captcha.CaptchaGenerator`, `…captcha.painter.CaptchaPainter` |
| Framed captcha | `Settings.MAIN.FRAMED_CAPTCHA`: `WIDTH` × `HEIGHT` frames, `FRAME_ROTATION_CHANCE` |

The base pictures themselves are **server-owner-supplied backplates** (`BACKPLATE_PATHS`), not
plugin assets: upstream ships no images at all, so there is no asset set to look for. The V4
artwork, the V5 / V53 web-captcha art and the Russian number-word body of V52 are three different
servers' backplates and configurations.

The V52 sample is the **Russian number-word captcha** in a 3×3 frame - the same family as V2 / V3
(`NUMBER_SPELLING=true`, one word per line), which is LimboFilter too.

---

## 3. Family B — object captcha (V8)

### 3.1 Geometry (measured)

Canvas **250×150**, **3×3**, cell **83×50**, boundaries x {0, 83, 167, 250}, y {0, 50, 100, 150}.
Proven by the flat-colour samples, where every cell is one uniform colour and the blocks land
exactly on those boundaries.

Cell references use the same **(row, column)** convention as §2.1.

### 3.2 Layout — justified photo gallery

Nine photos. Each is scaled to the **83-px cell width with its aspect ratio preserved**, anchored
at the cell's top-left, so a photo taller than 50 px **overflows into the cell below**:

* `s10/004.png` cell (1,1) is a high-key photo of a pale wall with a white socket; the **photo**
  continues into cell (2,1) - one photo spanning two rows. The socket itself sits in (1,1); it is
  the photo, not the socket, that carries on.
* `s10/005.png`: the traffic light occupies (1,0) and (2,0) continuously (red+yellow above the
  seam, green below). Same frame also shows the category mix: tabby cat, silver car, grey cat
  face, traffic light, orange Pomeranian, white car, brown puppy, parrot.

Answer = the set of photos (or click points) belonging to the named category.

### 3.3 The flat-colour variant (7 of 14 samples)

Same 3×3 / 83×50 geometry, cells filled with exact fills
**`#FF0000`, `#00FF00`, `#FFF200` (255,242,0), `#000000`, `#FFFFFF`**, with JPEG-style ringing at
the cell edges (`#01FE00` ×166, `#F00F00` ×166, `#0FF000` ×164, `#FB0400` ×100 …).

**The grid was JPEG-encoded *after* the cells were drawn, not before.** Measured: in `008.png` all
490 non-fill pixels that lie on a cell seam are on a seam where the fill **changes** across it,
and **none** is on a same-colour seam; the same holds for `010.png` (977 / 0), `011.png` (906 / 0),
`012.png` (593 / 0), `013.png` (757 / 0) and `014.png` (1025 / 0). The horizontal seam at y=50 of
`008.png` carries ringing in exactly 166 of its 250 columns, which is precisely the number of
columns where the row-0 and row-1 fills differ (green|red on the left, red|red in the middle,
red|green on the right). If the swatches had been JPEG-encoded **individually** and then tiled,
*every* swatch edge would ring, including the red|red ones. The generator
(`dataset/generator_ru/dev/captcha/gens/ObjectCaptcha.java`) does the round trip after drawing the
grid, which is the right order.

Same logic, colour swatches instead of photographs.

### 3.4 No assets, no licence, no package

Stock photos, no shipped asset set. Fingerprint: the exact fills above with JPEG ringing, and the
83×50 cell.

---

## 4. Candidates checked and excluded

| candidate | verdict |
|---|---|
| **LimboFilter** (Elytrium/LimboFilter, Velocity) | **THE MATCH** for the puzzle family - `FRAMED_CAPTCHA` renders `WIDTH × HEIGHT` separate 128×128 map items and rotates each of them by a multiple of 90° (`FRAME_ROTATION_CHANCE`). The number-word family of V2 / V3 / V52 is the same plugin with `NUMBER_SPELLING`. It paints onto a Minecraft map, so it is not the V8 object family. See `reports/LIMBOFILTER_IDENTIFICATION.md`. |
| **BotFilter** (Leymooo's BungeeCord fork) | 128×128 **map** captcha. Proven locally: the 510-image set in `research/jars/bf_dataset/` is uniformly 128×128. FunTime confirmed via [mmeerrkkaa/funtime-captcha-verifed](https://github.com/mmeerrkkaa/funtime-captcha-verifed) - trigger `"BotFilter >> Введите номер с картинки в чат"`, decodes the Minecraft map palette (`lib/minecraftColors.js`). **Not** these families. |
| **LofiWebCaptcha** (shved255/LofiWebCaptcha-Bukkit + `-site`, Apache-2.0, BungeeCord+Bukkit, `ru.shved255`) | the only open-source *web* captcha plugin found - best candidate for the **V8** object family, but its `index.php` embeds **Google reCAPTCHA** (`data-sitekey 6Lf48XIqAAAAAOEG…`). **Not** the renderer. |
| **Modrinth "Captcha"** (e015SVoM) | = Mrbysco/Captcha, already in `dataset/out/`; types are "I'm not a monster" + math. |
| **CaptchasX** (Z4OLLIEZ4/reCaptcha) | already in `dataset/out/` (`captchasx`). |
| **CaptchaVerifyZ** (`com.Mateitaa1.CaptchaVerifyZ`) | already identified; 128×128 map captcha. |
| CurseForge "Captcha" mod | Cloudflare-blocked; the Modrinth project of that name is Mrbysco's (no image grid). |
| Russian forums (spigotmc.ru, mcbase.ru, black-minecraft.com) | only AltronCaptcha, WeatherActionCaptcha, BIBCRAFTCAPTCHA, BICaptcha, hateCaptcha - no image-grid captcha. |
| **Sourcegraph** public code search | no public Java implementation of the V8 object grid: Cyrillic charset literals, `"пазл"`+captcha, `"кошки"`, `"найдите все"`, `unsplash`/`loremflickr` in captcha code, `file:Captcha*.java getSubimage`, `"tiles"+"shuffle"+"BufferedImage"` -> all empty. |
| **GitHub repo search** | the 18 plugins already in `dataset/out/` are the whole open-source population *of the Bukkit/Spigot kind*; the one family that is a plugin turned out to be a **Velocity** plugin, which that search never covered. |
| **SpigotMC** | HTTP 503 ("We'll Be Back!") for the whole session; mirrors spigotunlocked.com 403 (Cloudflare), blackspigot.com is a leak site. |

---

## 5. Not identified

* The producer of the **object (V8)** renderer - most likely a third-party web-captcha service the
  gallery operator resells, not Minecraft software.
* The origin of the V4 artwork and of the V8 photo set (for V4 they are now known to be a
  server owner's LimboFilter backplate, but which server is not recoverable).
* The exact per-image configuration of the captured servers.

---

## 6. Practical advice for the generators

* **The puzzle family is now LimboFilter's `FRAMED_CAPTCHA`, and the two `ru-puzzle*` types are gone.**
  The advice this section used to give was: implement the two facts the reference images prove — the
  frames are **rotated by a random multiple of 90°**, and the coloured digits/letters are the **base
  captcha's own text cut by the frame edges**, not an overlay — and take the **permutation** out, because
  the upstream splits the canvas in order and only turns the frames.
  All three points were acted on, but in a different way than the advice assumed: the family is not
  "a picture cut into a grid" at all, it is the plugin's own captcha. The upstream paints the whole
  text on one canvas of `128·WIDTH × 128·HEIGHT`, hands that canvas to the map canvas, which cuts it
  into maps of 128×128, and then turns each of those maps on its own — with probability
  `FRAME_ROTATION_CHANCE`, by `random.nextInt(4)` quarter turns. The generated types are
  `dataset/out_ru/LimboFilter/framed3x3` (384×384) and `LimboFilter/framed2x2` (256×256): the Russian
  number spelled out in words, one word per line, cut into nine (four) maps, each turned on its own.
  The **permutation is gone** from the generator, as §2.3 said it should be, and the frames keep their
  place in the grid.
* The base art of the generated families is therefore **not** the V4 / V5 / V53 art: it is the plugin's
  own number-word body. The V4 / V5 sections are **not** generated - they are jigsaws of
  photographic / anime / meme artwork, most of them carrying no text at all, so their answer cannot be
  read out of the pixels and inventing one would be fabricating ground truth. The V53 base (a white
  field with teal blobs and thin-outlined letters) is the gallery's backplate, not the plugin's
  rendering either; it is kept as reference material in
  `dataset/out_ru/LimboFilter/real_shots/framed2x2/`.
* V8 needs a different generator: a justified photo gallery with aspect-preserving,
  width-anchored placement, plus the flat-colour variant with JPEG-ringing swatches. The
  reference PNGs' own photos are the only faithful source - no public asset set exists. The flat
  variant is generated (`GalleryCaptcha/ru-object-swatch`), and its colour model now follows the reference:
  two colours with a majority/minority split, the target being the minority.

---

## 7. Tools added (tools/)

`analyze_grid.py` (seam detection) · `analyze_cells.py` · `colors.py` · `alpha.py` · `png_meta.py` ·
`crop_grid.py` (3×3 overlay crop; labels cells **(col,row)**, the reports use **(row,col)**) ·
`zoom.py` · `down150.py` (150×90 ancestry test) · `tile.py` (rotate a single tile) · `jigsaw2.py` /
`jigsaw3.py` (brute-force jigsaw solver) · `glyphs.py` (ink components; picks the red or the pink
mask from the **exact** API version) · `sg.ps1` (Sourcegraph) · `strip_html.py` / `urls.py` /
`links.py` / `man.py` (BARE page + manifest parsing).

---

## 8. URLs

- <https://github.com/Elytrium/LimboFilter> · <https://spigotmc.ru/resources/limboapi-limboauth-limbofilter-virtualnye-servera-dlja-velocity.715/>
- <https://github.com/mmeerrkkaa/funtime-captcha-verifed>
- <https://github.com/shved255/LofiWebCaptcha-Bukkit> · <https://github.com/shved255/LofiWebCaptcha-site>
- <https://github.com/GiovanniEliasDaRosa/Image-Puzzle> (a 3×3 web jigsaw over
  `https://source.unsplash.com/random/400x400` - same idea, not the source; that Unsplash
  endpoint no longer works)
- <https://api.modrinth.com/v2/project/e015SVoM> · <https://api.github.com/> ·
  <https://sourcegraph.com/.api/search/stream>
- <https://spigotmc.ru/> · <https://mcbase.ru/> · <https://www.spigotunlocked.com/> ·
  <https://www.spigotmc.org/> (503 throughout)
