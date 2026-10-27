"""The CRNN + CTC export to a Hugging Face repository.

The package is the body of `train/export_hf.py`, which stays the entry point
(``python train\\export_hf.py --help``) and is now a thin wrapper around
`hf_export.cli`.

| module | what it holds |
|---|---|
| `common` | the paths, the charsets, the `auto_map` and the small helpers |
| `templates_model` | the `configuration_captcha.py` and `modeling_captcha.py` templates |
| `templates_processor` | the `processing_captcha.py` template |
| `templates_card` | the model card and the MIT licence |
| `card` | the provenance tables and the model-card writer |
| `writer` | the repository writer and the ONNX export |
| `verify` | the three-way verification (training code / exported code / ONNX) |
| `cli` | the argument parsing and `main()` |

Nothing in here is imported by the training scripts: the export is a one-way
street, and the training code never depends on the exported repository.
"""
