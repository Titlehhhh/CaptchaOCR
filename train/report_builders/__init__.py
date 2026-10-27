"""The report builders of `train/make_report.py`.

Three builders, one per measurement:

| module | the report it builds | where the numbers come from |
|---|---|---|
| `ppocr_log` | `reports/TRAINING_PPOCR_V6.json` | the log of the first PP-OCRv6 run |
| `ppocr_result` | `reports/TRAINING_PPOCR_V6_BIG.json` | the `result.json` of the big run |
| `crnn` | `reports/TRAINING_CRNN_BIG.json` | the `val_report.json` of the CRNN run |

They used to live as three copies inside the run directories
(`train/runs/**`), which are git-ignored: the code that produced a measured report
was invisible to git and had to be found on disk. The builders are here now; the
run directories keep their results.
"""
