# SmartCaptcha - no real shots, and none can exist

This folder is **empty**, and that is deliberate: SmartCaptcha renders **no image at all**.
It is a chest-GUI captcha - on join an inventory opens whose title comes from
`captcha-gui-name`, the top slot holds the real item (the arrow by default) and the rest
hold random decoy blocks (ice by default) - so there is no captcha image to photograph.

The plugin's jar is unobtainable as well: the Spiget CDN serves a 0-byte object
(`x-bz-content-sha1` = the SHA-1 of the empty string) and spigotmc.org is down, so the
"renders no image" claim rests on the README / config evidence only.

See `dataset/out_ru/SmartCaptcha/README.txt` and
`reports/RU_PLUGINS_CAPTCHA_VERIFYZ_SMARTCAPTCHA.md` section 2.
