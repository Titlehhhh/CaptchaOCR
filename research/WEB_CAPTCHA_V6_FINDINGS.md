# The 150×90 "web captcha" family: what generates it?

**Result: there is no single generator.** The 70 reference samples are a *corpus* of real-world
web captchas, not the output of one library. Everything below was measured from the reference
corpus during the 2026-10-21 research session and from the upstream sources of the open-source
libraries listed in §3.

> The reference corpus itself is not part of this repository any more: it was third-party
> material and was removed from the working tree. The measurements and the open-source
> references below are kept, because they are what the dataset design rests on.

## 1. What the corpus is

* The samples are 150×90 PNGs, file-named `109.png … 1514.png` (internal catalogue ids of the
  collection we studied), grouped under a "Веб капчи" (web captchas) heading.
* The collection was presented as a demo of a **general-purpose web-captcha solver**: the FAQ of
  the operator claimed "more than 6000 kinds of captchas from all over the internet", and stated
  that 250×150 is the size their model wants — 150×90 is simply the native size of the
  web-captcha idiom they collected.
* So the section is a **demo gallery of a general-purpose web-captcha solver**, and the 70
  pictures are examples taken from that 6000+ type collection.

## 2. Measurements that rule out one generator

All 70 files are 150×90 PNG. Nothing else about them is uniform.

| Property | Measured |
|---|---|
| PNG colour model | **19 RGB, 41 RGBA, 10 palette (P)** |
| Distinct colours per image | **2 … 12 728** (the extreme cases: 2, 3, 6 and 12 728) |
| Anti-aliasing | some samples are hard-edged (1-bit-ish, 2–6 colours), others fully anti-aliased (thousands of colours) |
| String length | **3, 4, 5 and 6** all occur |
| Character set | not constant: digits only, letters only, mixed, and **Cyrillic** in one sample |
| Per-character colour | four samples colour every glyph differently |
| Backgrounds | white, flat colour, gradient, diagonal hatch, coloured dots, graph paper, **photographs** (handwriting, photo mosaic, brick wall, wood, sunflower) |
| Borders | a 2 px white rounded frame in one, a 2 px black square frame with 16 px graph-paper cells in another |
| Rendering engine | one hard-edged renderer (3 colours, grid drawn 2 px wide every 16 px); one photographic JPEG-noise renderer; one anti-aliased serif renderer |

A single library has one charset literal, one length, one drawing routine and one PNG encoder.
The table above is incompatible with that: it is a **grab-bag**, and the neighbouring sections of
the same collection are uniform by comparison (the 250×150 ones are all RGBA).

## 3. Libraries checked and ruled out (default size measured from source)

| Library | Language / licence | Default size | Verdict |
|---|---|---|---|
| [Gregwar/Captcha](https://github.com/Gregwar/Captcha) | PHP, MIT | **150×40** (`CaptchaBuilder::build(int $width = 150, int $height = 40)`) | wrong size, one font, no background catalogue |
| [S1SYPHOS/php-simple-captcha](https://github.com/S1SYPHOS/php-simple-captcha) | PHP, MIT (Gregwar fork) | **150×40** (`build(150, 40)`) | closest feature match (6 fonts, bg image, scatter, random font per symbol) but wrong size and no background catalogue |
| [walijoy/captcha-generator](https://github.com/walijoy/captcha-generator) | PHP (DL sample generator) | `build(200, 80)`; CLI default **300×150** | **closest algorithmic match**: charset `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789`, random length, random font, background = random image *or* flat colour, per-character colour chosen to contrast with the background average (`buildColor()`), interference = `lines()` + `writeNoise()` + `writeCurve()`, distortion. But it saves **JPEG**, rotates every character ±30°, and its demo output is saturated/rotated — not the corpus |
| [akiraly/cage](https://github.com/akiraly/cage) | Java, Apache-2 | 200×70 ("G" template) / 290×80 ("Y" template) | wrong size, no backgrounds |
| captcha4j | Java | example `new ImageCaptchaBuilder(200, 50)` | wrong size |
| easy-captcha (whvcse) | Java | 200×100 | wrong size, no backgrounds |
| kaptcha | Java | 200×50 | wrong size |
| Securimage | PHP | 250×75, 5 chars, one GD font | wrong size, one font |
| svg-captcha | Node | 200×70 | wrong size |
| miraculx/captcha | Python | 190×90 | closest size in Python, but one of 2 bundled fonts, no backgrounds/border |
| base64Captcha | Go | 240×80 | wrong size |
| [kuszaj/claptcha](https://github.com/kuszaj/claptcha) | Python/Pillow, MIT | **100×30** (the README's "150x90" is an *example* of changing the size) | the only GitHub hit for `"150x90"` in a captcha README, but no backgrounds/border/noise |
| BotDetect | PHP/Java/.NET | (image size 175×50 class) | wrong size |

Search coverage: GitHub repo+README search for `captcha in:readme "150x90"` → 2 hits
(kuszaj/claptcha, one junk repo); `"150 x 90"` → 0; **210 npm captcha packages scanned, 0 hits**;
`imagecreatetruecolor(150, 90)` in public code → 19 hits, all Drupal's `color.module`
(false positives); `new BufferedImage(150, 90` → 0.

## 4. The framed sections are compositions (measured, not assumed)

A script cut each puzzle sample on exact thirds and searched for the tile permutation that
minimises the colour discontinuity across the seams (60 000 random permutations per image). The
best permutation beat the median random one by a factor of **2–40** (2×2 family: ratio
0.027–0.47), and the reassembled images were coherent: one became a single web-captcha picture
with a readable two-digit text, another a fantasy artwork picture. (The analysis scripts and the
reassembled images were removed together with the reference corpus.)

The base pictures of the 2×2/3×3 families are **250×150 web-captcha art** (big decorated text on
a white/graphic field), *not* the 150×90 samples — no tile of the 3×3/2×2 families matches any of
the 70 150×90 samples, nor any of the 343 images of the neighbouring section (mean abs. error
never below ~30).

Conclusion: **the framed families are composites of a web-captcha renderer**, but the base image
is a 250×150 web captcha, not one of the 150×90 samples. The photographic families are the same
construction applied to photographs, not to a captcha renderer.

**Update (later the same day): the renderer around the base is identified too.** The framed
families are **LimboFilter's `FRAMED_CAPTCHA`** (`reports/LIMBOFILTER_IDENTIFICATION.md`): the
captcha is painted on a canvas of `128·WIDTH × 128·HEIGHT`, split into `WIDTH × HEIGHT` separate
128×128 map items, and each of those frames is rotated by a random multiple of 90° with
probability `FRAME_ROTATION_CHANCE`. So the frames are **not shuffled** — the earlier
"cut and permuted" reading of the sections was wrong, and the rotation, not a permutation, is what
the player has to undo. The base art remains unidentified; the "composite of some web-captcha
renderer" wording above is still the right one for it.

## 5. What this means for the dataset

* Our `ru-web` type must stay a **reconstruction of the idiom** (as it already is); it cannot
  be a faithful port of a single upstream renderer, because there is no single upstream
  renderer.
* The honest label for the family is "web-captcha corpus", not "the output of library X".
* If per-style fidelity is wanted, the corpus should be split into the eight style families
  above and each modelled separately — the 150×90 canvas, the 3–6 character length range and
  the mixed-case alphanumeric alphabet are the only global constants.
