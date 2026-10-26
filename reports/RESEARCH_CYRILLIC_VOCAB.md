# Ответ исследования — 3 вопроса + TOP-3 (рус., с источниками)

**1. PaddleOCR: добавление языка / cyrillic-модели** [PaddleOCR `train_rec` docs](https://github.com/PaddlePaddle/PaddleOCR/blob/main/doc/doc_ch/train_rec/train_rec_ch.md): синтез 100k–500k строк (`text_renderer.py` + кириллический словарь/шрифты), расширение словаря. `finetune_ppocr.py` (`--expand-charset`, строки 352–386): новые символы в конец `character_list`, head растёт (`nn.Linear`), новые строки инициализируются `mean(pretrained) + noise·0.02`. Микс с оригиналом: replay 30% или 3:1 (без replay латиница забывается — `HANDOVER.md`: 0.480). `cyrillic_PP-OCRv5/eslav` ([PaddleOCR v4.1 release](https://github.com/PaddlePaddle/PaddleOCR/releases/tag/v4.1.0)) — **отдельные** модели (перетренированный словарь), не общий head. Рекомендация: общий head с replay.

**2. Curriculum / длинные CTC** [Graves 2006](https://www.cs.toronto.edu/~graves/icml_2006.pdf) — сложность CTC растёт экспоненциально с длиной. [Baek 2018](https://arxiv.org/abs/1803.01230) — curriculum: ≤8 → длиннее. Проект (`HANDOVER.md` + `AGENTS.md`): короткие 0.54–0.66, 10–20 символов 0.00. Дешёвый трюк: сортировка батчей по длине + фазы (≤10, затем 11–15, затем 16–20); `glyph_scale="glyph"` (`ppocr_data.py`) уменьшает шум.

**3. Anti-forgetting** [WiSE-FT 2022](https://arxiv.org/abs/2211.04408): `θ = α·θ_ft + (1-α)·θ_pre`. Проект: α=0.4 (`HANDOVER.md`) → +0.158 exact (0.480→0.638). Самый дешёвый/доказанный — WiSE-FT (0 доп. GPU). [Replay](https://arxiv.org/abs/1905.11904) — 30% оригинала (средний эффект, 0 доп. памяти). [Freeze backbone](https://arxiv.org/abs/1902.09574) — заморозка `model.model`, только head (самый дешёвый, но слабее для нового шрифта).

**TOP-3 (эффект/стоимость):**
1. Replay 30% + freeze backbone (0 ресурсов, останавливает забывание латиницы).
2. Curriculum по длине (≤10 → 20 символов, фазами) — решает 0.00 на длинных словах.
3. WiSE-FT α=0.4 + синтез 10k кириллических строк (`text_renderer`) — подтверждено (0.638), дешевле отдельной модели.
