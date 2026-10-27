"""The PP-OCRv6 fine-tune: `common`, `ppocr_core`, `ppocr_data`, `ppocr_run`.

The entry point stays `train/finetune_ppocr.py`; the flat `train/ppocr_data.py`
name is kept as a re-export shim for the external importers (`webapp/pipeline.py`,
`reports/HTML/make_scoreboard.py`, `train/soup_eval.py`).
"""
