# Russian captcha plugins — upstream source research

Research date: 2026-10-21. Every URL below was fetched during this session.
Nothing here is inferred: each item states the page/file it was read from.

---

## 1. BotFilter — **LOCATED** (authoritative source found)

### 1.1 Authoritative upstream

| | |
|---|---|
| Repository | **<https://github.com/Leymooo/BungeeCord>** (default branch `master`, last push 2026-09-29) |
| Repo description | `BungeeCord with built in AntiBot protection. (RUS lang)` |
| Author | Leymooo = **Vjatšeslav Maspanov** — credited in the forks as "Original BotFilter developer" |
| Download links in the README | RuBukkit thread <http://www.rubukkit.org/threads/137038/> , Yandex Disk <https://yadi.sk/d/QrSeJWeU3LAq4p> |
| Java package | `ru.leymooo.botfilter` (+ `.captcha`, `.captcha.generator`, `.captcha.generator.map`, `.caching`, `.packets`, `.config`, `.utils`) |
| Platform | **BungeeCord proxy** (a fork of `SpigotMC/BungeeCord`) — it is a proxy plugin, *not* a Bukkit/Spigot plugin |
| Licence | `LICENSE` = the md_5/BungeeCord **BSD 2-clause** ("Copyright (c) 2012, md_5. All rights reserved.") **plus** the extra clause *"You may not use the software for commercial software hosting services without written permission from the author."* GitHub therefore reports `NOASSERTION` (not a standard SPDX id). Redistribution and modification are allowed with the notice retained → a faithful re-implementation is legally fine, but a **clean-room** rewrite is the safer house style because of the extra clause. |

The same plugin code also lives in three forks, all byte-identical in the captcha package
(useful if `Leymooo/BungeeCord` disappears):

* <https://github.com/Ymxer/BotFilter> (Chinese; "Config 提供者: Ymxer"; update-check points at the ZHCN fork)
* <https://github.com/Loyisa/BungeeCord-BotFilter-ZHCN> (Chinese)
* <https://github.com/DionaMC/BungeeCord-BotFilter-ENG> (English)

Fork chain (from the GitHub API):
`SpigotMC/BungeeCord` → `DionaMC/BungeeCord-BotFilter-ENG` → `Loyisa/BungeeCord-BotFilter-ZHCN` → `Ymxer/BotFilter`.

### 1.2 The rendering code — file + method

**`proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/CaptchaPainter.java`**

* `public BufferedImage draw(Font font, Color fGround, String text)` — the entry point
* `protected BufferedImage createImage()` — canvas
* `protected Graphics2D configureGraphics(Graphics g, Font font, Color fGround)` — antialiasing hints
* `protected void draw(Graphics2D g, String text)` — glyph vector, scaling, outline
* `protected void transform(Graphics2D g, String text, GlyphVector v)` — per-glyph rotation + spacing jitter
* `protected BufferedImage postProcess(BufferedImage img)` — ripple + blur

**`proxy/src/main/java/ru/leymooo/botfilter/captcha/CaptchaGeneration.java`**

* `public void generateImages()` — picks the font and the colour, calls the painter, converts to a map
* `private Color randomNotWhiteColor()` — palette colour with the near-white entries rejected
* `private String randomAnswer()` — the captcha answer

**`proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/Rippler.java`** — `public BufferedImage filter(BufferedImage src, BufferedImage dest)`
**`proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/map/CraftMapCanvas.java`** — `public void drawImage(int x, int y, BufferedImage image)`
**`proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/map/MapPalette.java`** — `colors[]` (the Minecraft map palette), `prepareColors()`, `imageToBytes()`, `matchColor()`

Raw sources (identical in `Leymooo/BungeeCord` and the three forks):
<https://raw.githubusercontent.com/Leymooo/BungeeCord/master/proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/CaptchaPainter.java>
<https://raw.githubusercontent.com/Leymooo/BungeeCord/master/proxy/src/main/java/ru/leymooo/botfilter/captcha/CaptchaGeneration.java>
<https://raw.githubusercontent.com/Leymooo/BungeeCord/master/proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/Rippler.java>
<https://raw.githubusercontent.com/Leymooo/BungeeCord/master/proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/map/MapPalette.java>
<https://raw.githubusercontent.com/Leymooo/BungeeCord/master/proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/map/CraftMapCanvas.java>

### 1.3 The algorithm, in enough detail to re-implement it

**Canvas and background**

```java
private final int width = 128;
private final int height = 128;
private final Color background = Color.WHITE;
...
protected BufferedImage createImage()
{
    return new BufferedImage( width, height, BufferedImage.TYPE_3BYTE_BGR );
}
```

* 128 × 128 px, `TYPE_3BYTE_BGR`, **solid white** background (`g2.clearRect(0,0,128,128)`).
* **No bundled background image** — no PNG assets at all. (The "128 × 128 background picture" in
  BotFilterPlus' description is that *fork's* own option, not upstream BotFilter.)

**Charset / answer**

```java
private String randomAnswer()
{
    if ( rnd.nextBoolean() )
    {
        return Integer.toString( rnd.nextInt( ( 99999 - 10000 ) + 1 ) + 10000 );
    } else
    {
        return Integer.toString( rnd.nextInt( ( 9999 - 1000 ) + 1 ) + 1000 );
    }
}
```

* digits only (`0-9`); 4 digits (1000–9999) or 5 digits (10000–99999), 50/50.
* 900 captchas are pre-generated at proxy start-up (`for (int i = 100; i <= 999; i++)`), each
  cached as a map packet.

**Font**

```java
Font[] fonts = new Font[]
{
    new Font( Font.SANS_SERIF, Font.PLAIN, 50 ),
    new Font( Font.SERIF, Font.PLAIN, 50 ),
    new Font( Font.MONOSPACED, Font.BOLD, 50 )
};
...
BufferedImage image = painter.draw( fonts[rnd.nextInt( fonts.length )], randomNotWhiteColor(), answer );
```

* three logical fonts, **size 50**, picked uniformly at random per captcha.
* Rendering hints: `TEXT_ANTIALIASING ON`, `FRACTIONALMETRICS ON`, `ANTIALIASING ON`,
  `COLOR_RENDER_QUALITY`, `DITHERING ENABLE`, `INTERPOLATION_BICUBIC`,
  `ALPHA_INTERPOLATION_QUALITY`, `RENDER_QUALITY`.

**Colour** — one colour for the whole text, taken from the Minecraft map palette with the
near-white entries re-rolled:

```java
private Color randomNotWhiteColor()
{
    Color color = MapPalette.colors[rnd.nextInt( MapPalette.colors.length )];
    ... rejects 255,255,255 / 220,220,220 / 199,199,199 / 255,252,245 / 220,217,211 / 247,233,163 ...
    return color;
}
```

`MapPalette.colors` is the Minecraft map palette as the plugin carries it: **144 entries** - four
black shades (the slots the map uses for "nothing here") followed by 35 rows of 4 = 140 real
colours; the vanilla map item can only show 128 of them, and the plugin still picks from the whole
array. `prepareColors()` maps every colour to its palette byte:
`byte index = (byte) ( i < 128 ? i : -129 + ( i - 127 ) );` - the `i < 128` branch is what makes the
formula meaningful, which is only possible because the array is longer than 128. The generator's
`MAP_PALETTE` (`BotFilter.java:97-134`) was compared with the live upstream array entry by entry:
**144 vs 144, 0 mismatching entries**.

**Per-glyph transform** (`transform`) — rotation and spacing:

```java
double rotateCur = ( rnd.nextDouble() - 0.5 ) * Math.PI / 8;      // start ±π/16
double rotateStep = Math.signum( rotateCur )
        * ( rnd.nextDouble() * 3 * Math.PI / 8 / glyphNum );        // step ≤ 3π/8 per glyph
...
if ( rnd.nextDouble() < 0.25 ) { rotateStep *= -1; }               // direction flip, p = 0.25
```

* rotation is applied per glyph as an `AffineTransform.getRotateInstance(rotateCur)`;
  the accumulated angle advances by `rotateStep`, which may change sign.
* glyph spacing is squeezed by `Math.min(preBounds.getWidth(), bounds.getWidth()) *
  ( rnd.nextDouble() / 20 + 0.27 )` — i.e. 0.27 … 0.32 of the narrower glyph width is removed
  between neighbours (the `0.1` alternative is dead code: `rotateEnabled` is hard-coded `true`).

**Scaling and outline** (`draw`)

```java
final float wr = width / bw * ( rnd.nextFloat() / 20 + 0.89f );
final float hr = height / bh * ( rnd.nextFloat() / 20 + 0.68f );
g.translate( ( width - bw * wr ) / 2, ( height - bh * hr ) / 2 );
g.scale( wr, hr );
...
g.draw( vector.getOutline( Math.signum( rnd.nextFloat() - 0.5f ) * 1 * width / 200 - bx,
                           Math.signum( rnd.nextFloat() - 0.5f ) * 1 * height / 70 + height - by ) );
g.drawGlyphVector( vector, -bx, height - by );
```

* the text is scaled to ~89–94 % of the canvas width and ~68–73 % of its height, centred;
* an **outline** (a stroked copy of the glyph outline) is drawn first, offset by
  ±width/200 (≤ 0.64 px) horizontally and ±height/70 (≤ 1.83 px) vertically — the outline is
  drawn in the *same* colour as the text, so it only thickens the glyphs;
* `outlineEnabled` is hard-coded `true` (the `0.92f` / `0.75f` alternatives are dead code).

**Noise / interference passes** (`postProcess`) — two passes, no lines, no dots:

```java
final Rippler.AxisConfig vertical = new Rippler.AxisConfig(
        rnd.nextDouble() * 2 * Math.PI, ( 1 + rnd.nextDouble() * 2 ) * Math.PI, img.getHeight() / 10.0 );
final Rippler.AxisConfig horizontal = new Rippler.AxisConfig(
        rnd.nextDouble() * 2 * Math.PI, ( 2 + rnd.nextDouble() * 2 ) * Math.PI, img.getWidth() / 100.0 );
final Rippler op = new Rippler( vertical, horizontal );
img = op.filter( img, createImage() );
...
final float[] blurArray = new float[ 9 ];
fillBlurArray( blurArray );
final ConvolveOp op = new ConvolveOp( new Kernel( 3, 3, blurArray ), ConvolveOp.EDGE_NO_OP, null );
img = op.filter( img, createImage() );
```

1. **Ripple** — a sinusoidal wave displacement. Vertical axis: random phase, length 1π…3π,
   amplitude `height/10 = 12.8 px`; horizontal axis: random phase, length 2π…4π, amplitude
   `width/100 = 1.28 px`. `Rippler.filter` does
   `ny = (y + verticalDelta[x] + height) % height; nx = (x + horizontalDelta[ny] + width) % width;`.
2. **Blur** — a 3×3 `ConvolveOp` whose nine weights are `rnd.nextFloat()` each, normalised to
   sum 1, `EDGE_NO_OP` (edges are *not* extended, they are left transparent).
3. **Palette quantisation** — `CraftMapCanvas.drawImage` → `MapPalette.imageToBytes` →
   `tryFastMatchColor` / `matchColor` (weighted RGB distance,
   `weightR = 2 + rmean/256`, `weightG = 4`, `weightB = 2 + (255-rmean)/256`, and the palette
   scan starts at index 4). The player only ever sees the quantised image, so this step is
   part of the visible algorithm.

**Caption / instruction text drawn on the image** — **none**. The image contains only the
digits. The instruction is a chat message sent by the proxy
(`ru.leymooo.botfilter.caching.PacketUtils` / the plugin's own message files); upstream's
`messages.properties` in the BungeeCord fork is the stock BungeeCord one, the BotFilter text
lives in the plugin's own config/message handling.

### 1.4 Real reference renders

<https://github.com/ServerSideProject/botfilter_captcha_dataset> — *"png images with captcha's"*,
MIT licence, 2022. Contains `BotFilter Dataset.rar` with **510 real 128×128 captcha PNGs**,
**file name = the answer** (`1024.png` → answer `1024`).

Downloaded and extracted during this session:

* archive: `research/jars/botfilter_captcha_dataset.rar`
* extracted: `research/jars/bf_dataset/` (510 PNGs)
* copies placed in the dataset: `dataset/out_ru/BotFilter/real_shots/` (510 PNGs + `README.md`)

Spot-checked `1024.png` by eye: olive-green distorted `1024`, wavy, blurred — exactly the
`CaptchaPainter` output.

---

## 2. "Captcha" (the plain-named one) — **NOT uniquely identified**

There is no single "the Russian Captcha plugin". SpigotMC alone has dozens of resources
named *Captcha*, and the four that are actually relevant here are listed below. The parent's
reserved folder `dataset/out_ru/Captcha/` therefore needs a decision about *which* one is meant.

| Plugin (SpigotMC / source) | Author / language | What it renders |
|---|---|---|
| **Captcha** <https://www.spigotmc.org/resources/captcha.75891/> → source <https://github.com/InstantlyMoist/Captcha> (`me.kyllian.captcha`) | Kyllian, English | **Map captcha** (`MapHandlerNew` / `MapHandlerOld`, `TextCaptcha`) — *already in the parent dataset as `InstantlyMoist/Captcha` / `textcaptcha`* |
| **Captcha** <https://www.spigotmc.org/resources/captcha.103993/> → source <https://github.com/reidjJava/Captcha> | reidj, English | inventory GUI (click the right item) — no image |
| **Captcha** <https://www.spigotmc.org/resources/captcha.120533/> (also on Modrinth as `captcha`, id `xXOC18H0`) | Aznos, English | 36-slot inventory of stained-glass panes — no image |
| **Captcha** <https://www.spigotmc.org/resources/captcha.77939/> → source <https://github.com/Nicbo/Captcha> | Nicbo, English | GUI pages of options — no image |
| **Captcha** <https://www.spigotmc.org/resources/captcha.84509/> → source <https://github.com/max11-dev/Captcha> | rambymax, English | GUI — no image |
| **Captcha** <https://www.spigotmc.org/resources/captcha.86350/> → source <https://github.com/DevSakio/Captcha> | Dablure, EN/ES | GUI — no image |
| **CaptchaPlugin** <https://github.com/UCRAFTS/CaptchaPlugin> (+ <https://github.com/UCRAFTS/CaptchaService>) | oDD1 / Alexander Repin, **Russian** | map item with a JPEG captcha generated by the Node service |

The last one is the only genuinely-Russian plugin in this family that renders an **image**,
and its renderer is a third-party npm library, so it is fully documented:

### 2.1 uCrafts `CaptchaPlugin` (Russian) — image rendering found

* Plugin: <https://github.com/UCRAFTS/CaptchaPlugin> — `@Plugin(name = "CaptchaPlugin", version = "1.0.0")`,
  `@Author(value = "oDD1 / Alexander Repin")`, Bukkit/Paper 1.16.5+, needs Redis + the service.
* Service: <https://github.com/UCRAFTS/CaptchaService> — Express wrapper, one endpoint
  `/api/v1/captcha/create`, stores the base64 JPEG in Redis, returns the answer.
* Renderer: npm package **`gm-captcha` 1.0.2** — <https://github.com/eidonjoe/gm-captcha> (MIT),
  a GraphicsMagick/ImageMagick wrapper.

Configuration shipped in `CaptchaService/.env.example` (the effective defaults):

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

`app/utils/text.js` builds the answer: `length` characters taken from `CAPTCHA_PATTERN`
(**Russian keyboard layout, lower case, plus digits**), each character independently
upper-cased with p = 0.5 — and note the loop `for (let i = 0; i <= length; i++)` produces
**length + 1 = 6 characters** for `CAPTCHA_LENGTH=5` (upstream defect: the answer is one
character longer than configured).

`app/service/captcha.js` maps the env vars onto `gm-captcha`:

```js
let captcha = new GmCaptcha({
    width: process.env.CAPTCHA_WIDTH,      // 512
    height: process.env.CAPTCHA_HEIGHT,    // 256
    text: text,
    background: process.env.CAPTCHA_BACKGROUND,   // '#bca881'
    wordSpacing: process.env.CAPTCHA_WORLD_SPACING,  // 64
    maxSwirl: process.env.CAPTCHA_MAX_SWIRL,    // 128
    maxShear: process.env.CAPTCHA_MAX_SHEAR,    // 8
    lineCount: -1, lineWidth: -1, pointCount: -1,
    fontSize: process.env.CAPTCHA_FONT_SIZE      // 64
})
```

`gm-captcha/index.js` rendering rules (verbatim behaviour):

* canvas `width × height` on the solid `background` colour; font = bundled
  `font/DroidSansFallback.ttf` (a CJK-capable font, so Cyrillic renders), `fontSize` 64.
* **text**: for each character, `stroke(colour, randomBetween(1, maxTextWidth))` (maxTextWidth
  defaults to 3) then `drawText(i * wordSpacing, fontSize, char)`, then
  `font(file)`, `fontSize(size)`, `swirl(symbol + randomBetween(0, maxSwirl))`,
  `shear(symbol + randomBetween(0, maxShear), symbol + randomBetween(0, maxShear))` where
  `symbol` is `''` or `'-'` with p = 0.5 (so the swirl/shear value is random in
  `[-maxSwirl, 0) ∪ [0, maxSwirl]`). Text colour comes from `getColors(20)` (20 random
  colours) unless `textColor` is set.
  *Quirk:* the `.font()` / `.fontSize()` calls are queued **after** `.drawText()`, so the
  **first character is drawn with the default GraphicsMagick font**, not DroidSansFallback.
* **lines**: `for (i = 0; i < lineCount; i++)` with `lineCount = -1` → **no interference lines
  are drawn at all** (upstream defect: the service passes -1, which disables the lines and the
  noise points entirely).
* **points**: `pointCount = -1` → no noise dots either.
* `generator()` executes the array `['line','text','line','point']` in that order and finally
  `resize(width, height, "!")`.

So the uCrafts captcha is: solid `#bca881` background, 6 Cyrillic/digit characters at
x = 0, 64, 128, 192, 256, 320, baseline y = 64, each with a random outline colour and a random
swirl/shear distortion, **no lines and no dots**, JPEG output, shown on a Minecraft map
(`ImageTools.resizeToMapSize`).

---

## 3. Siblings — status of the other four reserved names

| Name | Where it really is | Renders an image? |
|---|---|---|
| `CaptchaGUI` | SpigotMC <https://www.spigotmc.org/resources/captchagui.89583/> (block-select GUI). A *different*, unrelated plugin with the same name is at <https://github.com/Supl1n/CaptchaGUI> (`me.supl1na.captcha`) — a 9-slot inventory with one emerald block. | No (GUI) |
| `SmartCaptcha` | SpigotMC <https://www.spigotmc.org/resources/%E2%9A%91-smartcaptcha-%E2%9A%91-gui-based-captcha-system-%E2%9A%91.70935/> by **CommandSender**, 2019, free, "GUI-based captcha system". | No (GUI) |
| `CaptchaVerifyZ` | <https://www.spigotmc.org/resources/captchaverifyz-1-21-x-26-x.125355/> and <https://modrinth.com/project/LbnXX4g9>; author `mateita254` / Modrinth `natzproz`, org "Survivalcraft & Warmania Developers". Jar-only (`com.Mateitaa1.CaptchaVerifyZ`, `pom` 1.4, Java 21, spigot-api 26.3). The parent already has the jar. | Yes — on a **map** (`CaptchaMapRenderer extends org.bukkit.map.MapRenderer`) |
| `WeatherActionCaptcha` | SpigotMC.RU <https://spigotmc.ru/resources/weatheractioncaptcha-luchshaja-kapcha-dlja-zaschity-servera-vypolni-dejstvie-i-projdi-na-server.3275/> by *Любитель Метала* (verylovemetal), Paper 1.16–1.21, Java 16. The advertised source <https://github.com/verylovemetal/WeatherActionCaptcha> **404s and the account no longer exists** (GitHub API 404 for `/users/verylovemetal`, no redirect; no Wayback snapshot). | No — it is an *action* captcha (craft a table etc.) |

**None of the six are siblings of one author.** BotFilter is Leymooo's BungeeCord fork,
CaptchaVerifyZ is Mateitaa1's, WeatherActionCaptcha is verylovemetal's, SmartCaptcha is
CommandSender's, CaptchaGUI is a separate plugin. The "paid Russian marketplace" hypothesis
could not be confirmed for any of them.

---

## 4. Correction about the reference corpus the reconstructions came from

> **Superseded later the same day.** The conclusion below was wrong, and it was wrong because the
> search was restricted to Bukkit/Spigot plugins. The Russian number-word family and the framed
> "puzzle" families are produced by **LimboFilter** by *Elytrium* (<https://github.com/Elytrium/LimboFilter>), a **Velocity** anti-bot
> plugin, AGPL-3.0 — the captcha is painted onto a 128×128 Minecraft map, and the 250×150 reference
> PNGs are composites of that map with a chat/title overlay. The full write-up is
> `reports/LIMBOFILTER_IDENTIFICATION.md`.

The reference corpus was **not** a catalogue of Minecraft plugin output. Every section was
**250 × 150** (or 150 × 90 for the web sections) and showed classic *web* captchas — cartoon
backgrounds, coloured characters, black squiggle lines — including the "Русские капчи" sections,
whose content is **Russian number words written in letters**
(`двести сорок три` …) split over up to three rows. That family is the one we reconstructed as
the `ru-numberword` type.

No Minecraft plugin could be attributed to that family: the uCrafts `gm-captcha` service
produces 512 × 256 JPEGs, BotFilter 128 × 128 maps, CaptchaVerifyZ a 128 × 128 map. The
number-word family therefore looks like a **web** captcha type, not a plugin. If a "Captcha"
plugin must be pinned to it, the search for a Bukkit plugin that draws a Russian number word on a
250 × 150 image found none.

---

## 5. URLs relied on

* <https://github.com/Leymooo/BungeeCord> (BotFilter upstream) + the four raw source files
* <https://github.com/Ymxer/BotFilter>, <https://github.com/Loyisa/BungeeCord-BotFilter-ZHCN>, <https://github.com/DionaMC/BungeeCord-BotFilter-ENG> (forks)
* <https://github.com/ServerSideProject/botfilter_captcha_dataset> (510 real renders, MIT)
* <https://github.com/UCRAFTS/CaptchaPlugin>, <https://github.com/UCRAFTS/CaptchaService>, <https://github.com/eidonjoe/gm-captcha> (npm `gm-captcha` 1.0.2)
* <https://github.com/InstantlyMoist/Captcha> (= SpigotMC Captcha 75891, already in the dataset)
* <https://github.com/reidjJava/Captcha> (SpigotMC Captcha 103993)
* <https://github.com/Nicbo/Captcha>, <https://github.com/max11-dev/Captcha>, <https://github.com/DevSakio/Captcha>
* <https://github.com/Supl1n/CaptchaGUI>
* <https://www.spigotmc.org/resources/captcha.75891/> (page read from the Wayback snapshot 20230128155815)
* <https://www.spigotmc.org/resources/captcha.103993/> (Wayback snapshot 20250823110151)
* <https://spigotmc.ru/resources/weatheractioncaptcha-luchshaja-kapcha-dlja-zaschity-servera-vypolni-dejstvie-i-projdi-na-server.3275/>
* <https://spigotmc.ru/tags/kapcha/>, <https://spigotmc.ru/tags/captcha/>, <https://spigotmc.ru/search/search?keywords=Captcha&c[type]=resource`
* <https://modrinth.com/project/LbnXX4g9> (CaptchaVerifyZ), <https://api.modrinth.com/v2/search?query=captcha>
* <https://www.spigotmc.org/resources/captchagui.89583/>, <https://www.spigotmc.org/resources/%E2%9A%91-smartcaptcha-%E2%9A%91-gui-based-captcha-system-%E2%9A%91.70935/>

Note: `www.spigotmc.org` was serving **HTTP 503 "We'll Be Back!"** for the whole session, so
every SpigotMC page quoted above was read through `web.archive.org` snapshots, and
`mcreference.com` (a SpigotMC metadata mirror) was used for the resource IDs.
