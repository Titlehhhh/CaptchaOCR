"""Export a trained CRNN+CTC checkpoint into a self-contained Hugging Face repository.

    .venv-gpu\\Scripts\\python.exe train\\export_hf.py --checkpoint train\\run\\ckpt\\step_0001234.pt \\
        --out build\\hf_export --charset latin

What it produces, in ``--out``:

    config.json                 model_type, auto_map, the architecture's hyper-parameters
    configuration_captcha.py     the config class
    modeling_captcha.py          the model class (CRNN + CTC head)
    processing_captcha.py        the processor (ONE class, no sub-processor)
    processor_config.json       the processor's own config (transformers 5.x layout)
    preprocessor_config.json    the same attributes, for transformers 4.x and for AutoImageProcessor
    vocab.json                  the character table
    model.safetensors           the weights
    onnx\\model.onnx             the ONNX export (torch.onnx.export, never optimum)
    README.md                   the model card, generated from the measured numbers
    LICENSE                     MIT, for the weights

**This file is the entry point; the code lives in `train/hf_export/`.** The package
is one body of code that was too long for one file (the templates of the exported
repository, the writer, the verification and the model card are four separate
concerns). The command line, the flags and the behaviour are exactly the ones of
the single-file version that came before.

Three design decisions are load-bearing and are explained where they are made:

*   **One processor, no sub-processor.**  Transformers 5.x moved every processor attribute
    into a single nested ``processor_config.json`` and stopped writing
    ``special_tokens_map.json`` / ``added_tokens.json``.  A repository that ships a
    sub-processor therefore fails to load with *"Processor was loaded, but it is not an
    instance of ProcessorMixin"* - which is what happens to
    ``hongyusir/trocr-base-printed_captcha_ocr`` and
    ``DunnBC22/trocr-base-printed_captcha_ocr``.  ``CaptchaProcessor`` below is a single
    ``ProcessorMixin`` with an empty sub-processor list on both transformers 4.x and 5.x.

*   **``torch.onnx.export``, not optimum.**  ``transformers.onnx`` was removed in
    transformers 5.x and ``optimum-onnx`` 0.1.0 declares ``transformers<4.58.0,>=4.36``,
    so the two cannot coexist.  The ONNX file is the only artefact of this repository that
    runs without ``trust_remote_code`` and without torch.

*   **The export is verified, not assumed.**  The script loads the checkpoint back, runs
    the *training* code and the *exported* code on the same images and compares the
    decoded strings; then it re-loads the repository in a **fresh process** through
    ``AutoModel`` / ``AutoProcessor`` and compares again; then it runs the ONNX through
    ``onnxruntime`` and compares a third time.  A silent mismatch is the classic way an
    export goes wrong, so the script fails loudly instead of writing a model card.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from export.hf_export.cli import main  # noqa: E402  (the package lives under train/export/)

if __name__ == "__main__":
    sys.exit(main())
