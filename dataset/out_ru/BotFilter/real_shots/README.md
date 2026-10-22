# BotFilter - 510 real upstream renders

These are **not** generated samples. They are 510 captcha PNGs that the BotFilter plugin
actually produced, recovered from the community dataset

> <https://github.com/ServerSideProject/botfilter_captcha_dataset> - MIT, 2022

* The original archive is kept in `research/jars/botfilter_captcha_dataset.rar`; the
  extracted originals live in `research/jars/bf_dataset/`.
* Every file is a 128x128 PNG and **the file name is the answer** (`1024.png` -> `1024`).
  The answers are 4 or 5 digits, exactly as upstream's `randomAnswer()` produces.
* They are the **pre-quantisation** painter output, i.e. anti-aliased blends. The generated
  samples in `dataset/out_ru/BotFilter/map/` are quantised to the Minecraft map palette,
  which is what the player finally sees.
