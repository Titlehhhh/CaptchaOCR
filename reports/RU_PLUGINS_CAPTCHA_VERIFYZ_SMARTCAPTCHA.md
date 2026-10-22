# CaptchaVerifyZ and SmartCaptcha — upstream research findings

Research date: 2026-10-21. Sources: Modrinth API, SpigotMC (via the Spiget API mirror),
mcreference.com, spigotmc.ru, GitHub API, decompilation with CFR 0.152.

Artefacts live in `research/` (jars, CFR output, reference renders).

---

## 1. CaptchaVerifyZ — FOUND (fully decompiled)

### Authoritative locations

| What | URL |
|---|---|
| Modrinth project | https://modrinth.com/plugin/captchaverifyz  (id `LbnXX4g9`, slug `captchaverifyz`) |
| Modrinth API | https://api.modrinth.com/v2/project/LbnXX4g9 |
| Jar (latest, 1.4-2) | https://cdn.modrinth.com/data/LbnXX4g9/versions/dHdoDcmQ/CaptchaVerifyZ-1.4.jar |
| SpigotMC | https://www.spigotmc.org/resources/captchaverifyz-1-21-x-26-x.125355/ (author `mateita254`) |
| Spiget mirror (works while Spigot is down) | https://api.spiget.org/v2/resources/125355 |
| mcreference | https://mcreference.com/plugins/captchaverifyz |

**No public source repository.** Modrinth `source_url` is `null`; the Spigot description links only a Discord invite.
Licence: Modrinth reports `LicenseRef-All-Rights-Reserved` (all rights reserved) ⇒ any re-implementation must be
**clean-room** (re-implement the algorithm; do not copy upstream code).

### Metadata

- Java package: `com.Mateitaa1.CaptchaVerifyZ`; main class `com.Mateitaa1.CaptchaVerifyZ.CaptchaVerifyZ`
- Platform: Bukkit / Spigot / Paper / Purpur (`api-version: 1.21`), Java 21, `spigot-api 26.3-R0.1`
- Maven coordinates: `com.Mateitaa1:CaptchaVerifyZ:1.4` (1.0 used `com.example`)
- Author: Mateitaa1 (Spigot: `mateita254`)

### Renderer — exact upstream file + method

`com/Mateitaa1/CaptchaVerifyZ/CaptchaVerifyZ.java` → inner class `CaptchaMapRenderer`, method:

```java
public void render(MapView map, MapCanvas canvas, Player player)
```

This is a **Minecraft map captcha**: the rendered 128×128 image is handed to the player as a `FILLED_MAP` item
(`giveCaptchaMap()`), not as a chat image.

Verbatim upstream source (CFR 0.152 decompile of `CaptchaVerifyZ-1.4.jar`):

```java
private static class CaptchaMapRenderer
extends MapRenderer {
    private final String captcha;
    private boolean rendered = false;

    public CaptchaMapRenderer(String captcha) {
        this.captcha = captcha;
    }

    public void render(MapView map, MapCanvas canvas, Player player) {
        if (this.rendered) {
            return;
        }
        this.rendered = true;
        BufferedImage image = new BufferedImage(128, 128, 1);
        Graphics2D g2d = image.createGraphics();
        g2d.setColor(Color.DARK_GRAY);
        g2d.fillRect(0, 0, 128, 128);
        g2d.setColor(Color.WHITE);
        g2d.setFont(new Font("Arial", 1, 12));
        g2d.drawString("SECURITY VERIFICATION", 5, 20);
        g2d.setColor(Color.YELLOW);
        g2d.setFont(new Font("Arial", 1, 24));
        FontMetrics fm = g2d.getFontMetrics();
        int x = (128 - fm.stringWidth(this.captcha)) / 2;
        g2d.drawString(this.captcha, x, 70);
        g2d.setColor(Color.LIGHT_GRAY);
        g2d.setFont(new Font("Arial", 0, 10));
        g2d.drawString("Type the code in chat", 15, 100);
        g2d.dispose();
        canvas.drawImage(0, 0, (Image)image);
    }
}
```

### Rendering algorithm (pixel-faithful spec)

- **Canvas**: `new BufferedImage(128, 128, 1)` → 128×128, `TYPE_INT_RGB`. Exactly the Minecraft map size.
- **Background**: solid `java.awt.Color.DARK_GRAY` (64,64,64), `fillRect(0,0,128,128)`.
  No gradient, no bundled image asset.
- **Bundled assets: none.** The jar contains only three classes
  (`CaptchaVerifyZ.class`, `CaptchaVerifyZ$CaptchaMapRenderer.class`, `CaptchaVerifyZ$1.class`),
  `config.yml`, `plugin.yml` and a Maven pom. No PNGs, no fonts, no textures.
- **Fonts** (logical font names; on Windows `Arial` resolves to `Arial-BoldMT` / `ArialMT`):
  | Text | Font | Colour | Position |
  |---|---|---|---|
  | `SECURITY VERIFICATION` | `new Font("Arial", Font.BOLD, 12)` | `Color.WHITE` (255,255,255) | x=5, baseline y=20 |
  | the code | `new Font("Arial", Font.BOLD, 24)` | `Color.YELLOW` (255,255,0) | x=(128−fm.stringWidth(code))/2, baseline y=70 |
  | `Type the code in chat` | `new Font("Arial", Font.PLAIN, 10)` | `Color.LIGHT_GRAY` (192,192,192) | x=15, baseline y=100 |
- **Draw order**: background → header → code → footer; then `g2d.dispose()` and `canvas.drawImage(0,0,image)`.
- **Noise / interference: none.** No lines, no curves, no distortion, no rotation, no per-character jitter,
  no per-character colour, no anti-aliasing hints (Java2D defaults).
- **One-shot renderer**: `if (this.rendered) { return; }` — the image is drawn exactly once per map view.
- **Centring**: integer division on `FontMetrics.stringWidth(code)` measured with the **code** font
  (Arial Bold 24). Example: `A7K2X` → width 76 → x = 26.

#### Upstream defects to preserve (do not "fix")

1. **The header is clipped.** `SECURITY VERIFICATION` is 137.0 px wide in Arial Bold 12, drawn at x=5, so it
   ends at x=142 on a 128 px canvas — the trailing characters are cut off. Reference renders show
   `SECURITY VERIFICATIO…`. A faithful generator must clip, not shrink or centre the header.
2. **The answer is also printed in chat.** The default `messages.welcome` contains `"&a&l➤ &f&l{captcha}"`, and
   `startVerificationProcess()` substitutes the code into it. The map captcha is therefore bypassable by
   reading chat. The same happens on a wrong attempt via `messages.incorrect-attempt`.
3. **Verification is `message.equalsIgnoreCase(correctCaptcha)`** — case-insensitive but an exact match
   (not a substring match).

### Charset / code generation

```java
private String generateCaptcha() {
    StringBuilder captcha = new StringBuilder();
    String chars = this.getConfig().getString("captcha.characters", "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789");
    int length = this.getConfig().getInt("captcha.length", 5);
    for (int i = 0; i < length; ++i) {
        captcha.append(chars.charAt(this.random.nextInt(chars.length())));
    }
    return captcha.toString();
}
```

- Default charset: `ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789` (uppercase A–Z + digits 0–9, 36 symbols), no ambiguity filter.
- Default length: **5**. Both are configurable (`captcha.characters`, `captcha.length`).
- Uses a single `java.util.Random` field for the whole plugin (`private final Random random = new Random();`).

### Version stability

The `CaptchaMapRenderer` body is **bytecode-identical in every published version** checked:
1.0, 1.1, 1.2, 1.3, 1.4 and 1.4-2. Re-implementing once covers all versions.

"Byte-identical" would be too strong: the class files differ in every version, because the
`LineNumberTable` differs (`javap -v` diffs show only `line NNN: X` entries changing), but
`javap -p -c` output is identical for all six jars. The packaging did change, and it is worth
getting the attribution right: **1.0, 1.1 and 1.2 are all shaded fat jars** (4 978 entries /
4 669 classes), and **1.3, 1.4 and 1.4-2 are slim** (15 entries / 3 classes). The fat-jar-ness is
therefore not what distinguishes 1.2, and `javap -v` shows no annotation difference between 1.2
and 1.4 either - the only delta is the line-number table.

Re-measured over **all twelve** versions the project lists on Modrinth (1.0.0 - two builds - 1.1,
1.2, 1.2-1, 1.3, 1.3-1, 1.3-2, 1.3-3, 1.4, 1.4-1, 1.4-2): the renderer class is 2 107 bytes in
every one, and `javap -p -c` output is **identical** across all twelve (a single hash). The class
*files* fall into six groups, one per release line - 1.0.0 (both builds), 1.1, 1.2 (= 1.2-1),
1.3 (= 1.3-1/2/3), 1.4 (= 1.4-1) and 1.4-2 - so the difference really is confined to the line
numbers. The fat/slim split is at the same place: 1.0, 1.1, 1.2 and 1.2-1 are fat jars
(4 669 classes), 1.3, 1.4 and 1.4-2 are slim (3 classes).

### Instruction / message strings (verbatim)

> **The plugin is entirely English.** There are no Russian strings anywhere in CaptchaVerifyZ.

Drawn on the image:
- `SECURITY VERIFICATION` (header, clipped at the right edge)
- `Type the code in chat` (footer)

`config.yml` → `messages.welcome` (default):
```
&6&l╔══════════════════════════════════════╗
&6&l║        &f&lSECURITY VERIFICATION        &6&l║
&6&l╚══════════════════════════════════════╝

&e&l⚠ &fPlease complete the verification process
&7Enter the following code in chat:

&a&l➤ &f&l{captcha}

&7You have &c{time} seconds &7to complete this.
&7Case insensitive - just type the code!

&8This helps protect our server from automated attacks.
```

`config.yml` → `messages.kick` (default):
```
&c&l✕ VERIFICATION FAILED

&7Reason: &f{reason}

&eYou can rejoin to try again.
&7Please complete the captcha within the time limit.

&8If you're having trouble, contact server staff.
```

Other user-facing strings:
- `messages.returning-player`: `&a&lWelcome back! &7You're already verified.`
- `messages.incorrect-attempt`: `&c&lIncorrect! &7Try again: &e&l{captcha}`
- `messages.attempts-remaining`: `&7Attempts remaining: &c{remaining}`
- Success (hard-coded): `✔ Verification successful! You will need to verify again next time.` /
  `✔ Verification successful! You won't need to verify again.` /
  `✔ Verification successful! Welcome to the server!`
- Title: `Verified!` / subtitle `Welcome to the server`
- `Please complete the captcha verification first!` (command blocked during verification)
- `No permission!`, `Configuration reloaded!`
- Kick reasons: `Too many failed attempts!`, `Verification timeout!`
- Stats header: `=== Captcha Statistics ===`
- Map item display name: `§6Security Verification`

### Reference renders (for pixel comparison of a clean-room generator)

`research/refout/ref-*.png` — produced by `research/RefRender.java`, which replicates the upstream algorithm
line-for-line. MD5s:

| file | md5 |
|---|---|
| `ref-00000.png` | `7BFE088A32A43F417287571B6C82A925` |
| `ref-A7K2X.png` | `AB5BC8B8D9DFC0641E85BA9430240595` |
| `ref-M3P9L.png` | `D3E863316B00ADEEF7930F305B996BDC` |
| `ref-QWERT.png` | `9BBB8C11A33EFAAB0D85587B637C982E` |
| `ref-ZZZZZ.png` | `FEC4A2673A6E791B104AD7DC06A1B19D` |

Measured metrics on this machine (Windows 11, OpenJDK 21.0.8, `FontRenderContext(null,false,false)`):
Arial Bold 12 header = 137.0 px; Arial Bold 24 `A7K2X` = 76.0 px; Arial Plain 10 footer = 105.0 px.

---

## 2. SmartCaptcha — FOUND, but it renders **no image**

### Authoritative locations

| What | URL |
|---|---|
| SpigotMC resource | https://www.spigotmc.org/resources/70935 (`⚑ SmartCaptcha ⚑ GUI-BASED CAPTCHA SYSTEM ⚑`) |
| SpigotMC thread | https://www.spigotmc.org/threads/%E2%9A%91-smartcaptcha-%E2%9A%91-gui-based-captcha-system-%E2%9A%91.393547/ |
| Spiget API mirror | https://api.spiget.org/v2/resources/70935 |
| Spiget CDN (file) | https://cdn.spiget.org/file/spiget-resources/70935.jar — **currently a 0-byte file** |
| Spigot direct file URL | https://www.spigotmc.org/resources/319579/smartcaptcha-gui-based-captcha-system-1.0.jar (`319579` = Spigot file/version id) |
| mcreference | https://mcreference.com/plugins/smartcaptcha-gui-based-captcha-system |
| MCModsHub | https://mcmodshub.com/mod/33953 |

- Author: Spigot user `CommandSender`, real name **`elapsed0`** (author id 317151). His only two resources are
  `iReports` (69907) and `SmartCaptcha` (70935). A Spiget name search for `smartcaptcha` returns **exactly one
  resource**, so there is no other "SmartCaptcha" on Spigot and no ambiguity.
- v1.0, released 2020-03-22 (original post 2019-08-31), 4.1k downloads, 9 ratings averaging 3.6.
- Platform: Bukkit/Spigot, tested versions 1.7–1.14. Licence: **not stated** (free, `premium: false`, price 0).
- **No source repository** — not on GitHub, Modrinth or Hangar. GitHub code/repo searches for `smartcaptcha` +
  Java return only unrelated Yandex-SmartCaptcha web projects.

### There is no captcha image

SmartCaptcha is an **inventory (chest GUI) captcha**. The upstream resource description -
recovered in full from the base64 `description` field of the Spiget API
(`https://api.spiget.org/v2/resources/70935`, decoded with a plain base64 decoder) - says:

> **CAPTCHA GUI-SYSTEM** — SmartCaptcha plugin is able to detect players using console clients with a GUI
> authentication system that will be open to every player join in the server.
>
> **AUTHME SUPPORT** — If "AuthMe" plugin is enabled, you will be able to complete the captcha only after your
> authme authentication.
>
> **FULLY CUSTOMIZABLE CONFIGURATION** — You will be able to customize all the messages of this plugin!
>
> Commands & Permissions: `/captcha reload` » Reload the config; Permissions: `captcha.*` (Default = OP)
>
> **CAPTCHA EXAMPLE** — By clicking on the item displayed at the top, you will be authenticated.
>
> Disclaimer: The ice block can be another random block, the same for the arrow

The same description carries the upstream `config.yml`, reproduced **exactly** as it appears there
(the YAML block, comments and all):

```yaml
## KICK THE PLAYER AFTER %seconds% IF HE ISN'T AUTHENTICATED
kick-after: 20
## KICK THE PLAYER IF HE FAIL THE CAPTCHA OR IF HIS AUTHENTICATION TIME ENDS
fail-kick: true
## KICK MESSAGE (if fail-kick is enabled)
fail-kick-msg: "&cYou've been kicked from the server because you failed the captcha. Please try again."
## CAPTCHA-GUI NAME (no colors)
captcha-gui-name: "Click the %block%"
## CAPTCHA-GUI ITEMS
captcha-real-item: "&aClick here!"
captcha-fake-item: "&cDon't click here!"
## SUCCESSFUL AUTHENTICATION MESSAGE
authentication-msg: "&aYou've been successfully authenticated after passing the captcha test!"
## CONFIG RELOAD MESSAGE
config-reload-msg: "&aConfig successfully reloaded."
## NO PERMISSIONS MESSAGE
no-permissions-msg: "&cYou haven't &ecaptcha.* &cpermission, so you can't perform this command."
```

Note the two item names: the **real** item is `captcha-real-item` (`"&aClick here!"`, the arrow) and
the **decoy** is `captcha-fake-item` (`"&cDon't click here!"`, the ice). There is no image, texture,
skull, canvas, font or character-set key in the config at all.

Mechanics: on join the plugin opens a chest inventory whose **title** is `captcha-gui-name`
(e.g. `Click the ICE`); the top slot holds the real item (default: the arrow) and the remaining slots hold random
decoy blocks (default: ice). Clicking the correct item authenticates the player; clicking anything else, or
letting `kick-after` seconds elapse, kicks them. The point of the plugin is to defeat **console clients**, which
cannot click a GUI slot — so an image captcha would be the wrong tool by design.

Consequences for the dataset:

- **There is no canvas size, no image type, no background, no charset, no font, no noise pass and no caption to
  reproduce.** A "SmartCaptcha" image generator would be an invention, not a re-implementation.
- The only sensible dataset entry would be a *reconstruction* of the GUI (title text + item layout), which must be
  labelled **reconstructed / clean-room**, not "faithful". Its "answer" is the item to click, not a string.
- The plugin icon is the generic Minecraft "hand" icon (`data/resource_icons/70/70935.jpg`), i.e. no captcha artwork
  to fingerprint.

### Outstanding gap

**The "SmartCaptcha renders no image" claim rests on the README / config evidence only** - nothing
in the jar was inspected. The jar itself has not been byte-inspected. `cdn.spiget.org/file/spiget-resources/70935.jar` serves a **0-byte**
object (`x-bz-content-sha1` = SHA-1 of the empty string, uploaded 2021-04-15), so Spiget's mirror is useless, and
`spigotmc.org` has been in scheduled maintenance ("We'll Be Back!") throughout the research window — the direct
file URL returns HTTP 503, while `/resources/70935/download` returns 403 from Cloudflare.
`research/poll_smartcaptcha2.ps1` and `research/poll_wayback.ps1` poll both routes in the background.
The direct-file URL pattern `https://www.spigotmc.org/resources/<versionId>/<filename>` was confirmed to reach
the application (503, not 404), so it should serve the file once maintenance ends.

---

## 3. Sibling lead: WeatherActionCaptcha (not part of this task, recorded for the parent)

- SpigotMC.RU resource: https://spigotmc.ru/resources/weatheractioncaptcha-luchshaja-kapcha-dlja-zaschity-servera-vypolni-dejstvie-i-projdi-na-server.3275/
  (author **Любитель Метала**, `ljubitel-metala`, user id 31915; v1.3, 14 Mar 2025).
- The page links a GitHub repo: https://github.com/verylovemetal/WeatherActionCaptcha — **the repo 404s and the
  account no longer exists** (the GitHub API answers 404 for `/users/verylovemetal`, with no redirect; that is
  consistent with a deletion but is formally indistinguishable from a rename). Software Heritage has no snapshot
  of it.
- The description says «ДАЛЬНЕЙШАЯ ПОДДЕРЖКА ОТСУТСТВУЕТ. В МОЁМ ПРОФИЛЕ ВЫ НАЙДЁТЕ ЯДРО С КАПЧЕЙ» — the author
  points to a "core with captcha" in their profile, which is the likely home of the other plugins in the set.
- spigotmc.ru requires an account to download, so the jar could not be retrieved.
- `Supl1n` (author of CaptchaGUI) has only two repos — `Supl1n/CaptchaGUI` and `Supl1n/CubecoreStatistics` — so
  there are no GitHub siblings of CaptchaGUI either.

---

## 4. URLs relied on

- https://api.modrinth.com/v2/project/LbnXX4g9
- https://api.modrinth.com/v2/project/LbnXX4g9/version
- https://cdn.modrinth.com/data/LbnXX4g9/versions/dHdoDcmQ/CaptchaVerifyZ-1.4.jar
- https://modrinth.com/plugin/captchaverifyz
- https://api.spiget.org/v2/resources/70935
- https://api.spiget.org/v2/resources/125355
- https://api.spiget.org/v2/authors/317151
- https://api.spiget.org/v2/authors/317151/resources
- https://api.spiget.org/v2/search/resources/smartcaptcha?size=30
- https://cdn.spiget.org/file/spiget-resources/70935.jar
- https://www.spigotmc.org/resources/70935
- https://www.spigotmc.org/resources/captchaverifyz-1-21-x-26-x.125355/
- https://www.spigotmc.org/resources/319579/smartcaptcha-gui-based-captcha-system-1.0.jar
- https://mcreference.com/plugins/captchaverifyz
- https://mcreference.com/plugins/smartcaptcha-gui-based-captcha-system
- https://spigotmc.ru/resources/weatheractioncaptcha-luchshaja-kapcha-dlja-zaschity-servera-vypolni-dejstvie-i-projdi-na-server.3275/
- https://spigotmc.ru/sitemap.xml
- https://github.com/verylovemetal/WeatherActionCaptcha (404)
- https://api.github.com/users/Supl1n/repos
- https://api.github.com/search/repositories?q=smartcaptcha
- https://api.github.com/search/repositories?q=captchaverifyz
- https://repo1.maven.org/maven2/org/benf/cfr/0.152/cfr-0.152.jar (decompiler)
