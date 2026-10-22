These are NOT captcha samples. They are two video frames kept as evidence of what
WeatherActionCaptcha actually does. What they show, exactly:

  yt_62jp1hEeSFk.png   a promo title card - a small floating world with a crafting table,
                       an enchanting table, a chest and a furnace, and the plugin's own
                       banner ("WEATHERACTIONCAPTCHA - КАПЧА ДЛЯ ЗАЩИТЫ СЕРВЕРА. ВЫПОЛНИ
                       ДЕЙСТВИЕ И ПРОЙДИ НА СЕРВЕР"). It is marketing material, not
                       gameplay. From https://www.youtube.com/watch?v=62jp1hEeSFk -
                       "ПРОВЕРКА НА БОТА / ЗАЩИТА СЕРВЕРА / WEATHERACTIONCAPTCHA ОБЗОР
                       ПЛАГИНОВ #1", channel IlyosYT (https://www.youtube.com/@faynerYT).

  yt_a3_VRVRGuEc.png   a NeoWare 2.3.0 bot-client debug overlay on play.reserv.fun - the
                       ATTACKER side, not a player doing the task. It is the frame that
                       confirms the boss-bar text: "У вас есть 48 секунд, чтобы войти."
                       From https://www.youtube.com/watch?v=a3_VRVRGuEc - "WeatherActionCaptcha
                       passing | NeoWare Client", channel KrytickYT
                       (https://www.youtube.com/@krytickyt).

WeatherActionCaptcha (SpigotMC.RU 3275, author "Любитель Метала" / verylovemetal) is an
ACTION captcha: the player is dropped into a prepared world and has to perform a task
within a time limit shown on that boss bar. The upstream page names only the blocks that
will be there - "в котором будут нужные блоки, по типу верстака для крафта или стола
зачарования" (a crafting table, an enchanting table). No coal and no count of blocks is
confirmed by any evidence in this repository, so none is claimed here.

It renders no image at all, and the author's stated reason is exactly that: image captchas
had become easy for bots to bypass. The claim rests on the page text, the author's own
statement and these two frames - NOT on the jar, which spigotmc.ru only serves to logged-in
users, so it was never obtained.

The advertised GitHub source (verylovemetal/WeatherActionCaptcha) 404s and the account no
longer exists (the GitHub API answers 404 for /users/verylovemetal, with no redirect). The
Wayback Machine, Software Heritage, authenticated GitHub code search and every mirror
tried hold no copy. There is therefore no upstream image to be faithful to, and no
generator is provided for this plugin.

PROVENANCE: the two frames were taken from the YouTube videos named above; the titles and
channels were recovered from YouTube's oEmbed endpoint on 2026-10-21.

Distribution page:
  https://spigotmc.ru/resources/weatheractioncaptcha-luchshaja-kapcha-dlja-zaschity-servera-vypolni-dejstvie-i-projdi-na-server.3275/
