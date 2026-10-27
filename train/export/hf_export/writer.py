"""Writing the exported repository: the files, the weights and the ONNX graph.

`write_repo()` writes everything except the ONNX graph and the model card;
`export_onnx()` writes the graph with `torch.onnx.export`.
"""

import importlib
import json
import os
import sys

import torch
import torch.nn as nn

from .common import AUTO_MAP, TRAIN_DIR, log
from .templates_card import MIT_LICENSE
from .templates_model import CONFIGURATION_TEMPLATE, MODELING_TEMPLATE
from .templates_processor import PROCESSING_TEMPLATE


def derive_geometry(state: dict) -> dict:
    """Read the architecture's hyper-parameters out of the checkpoint's state dict.

    The checkpoint does not store `hidden` or `glyph_height` separately - it stores the
    tensors, and the tensors know their own shape. Deriving them from the shapes is
    exact, where reading them from a default would be a guess.
    """
    fc_w = state["fc.weight"]
    num_classes, hidden2 = int(fc_w.shape[0]), int(fc_w.shape[1])
    hidden = hidden2 // 2
    rnn_ih = state["rnn.weight_ih_l0"]
    lstm_hidden = int(rnn_ih.shape[0]) // 4
    rows = int(rnn_ih.shape[1]) // 256
    if lstm_hidden != hidden:
        raise ValueError(f"the head and the LSTM disagree on the hidden size: {hidden} vs {lstm_hidden}")
    glyph_height = rows * 8
    return {
        "num_classes": num_classes,
        "hidden": hidden,
        "glyph_height": glyph_height,
        "rows": rows,
    }


def import_from_dir(directory: str, module_name: str):
    """Import a module from a directory (the exported `modeling_captcha.py` etc.)."""
    if directory not in sys.path:
        sys.path.insert(0, directory)
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def write_repo(out_dir: str, cfg: dict, state: dict, charset: str) -> None:
    """Write everything except the weights, the ONNX and the model card."""
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "onnx"), exist_ok=True)

    with open(os.path.join(out_dir, "configuration_captcha.py"), "w", encoding="utf-8") as f:
        f.write(CONFIGURATION_TEMPLATE.format(charset=charset))
    with open(os.path.join(out_dir, "modeling_captcha.py"), "w", encoding="utf-8") as f:
        f.write(MODELING_TEMPLATE)
    with open(os.path.join(out_dir, "processing_captcha.py"), "w", encoding="utf-8") as f:
        f.write(PROCESSING_TEMPLATE.format(charset=charset))

    config = {
        "architectures": ["CaptchaModel"],
        "model_type": "captcha",
        "auto_map": AUTO_MAP,
        "num_classes": cfg["num_classes"],
        "hidden": cfg["hidden"],
        "dropout": cfg["dropout"],
        "glyph_height": cfg["glyph_height"],
        "charset": charset,
        "blank_index": 0,
        "min_width": cfg["min_width"],
        "max_width": cfg["max_width"],
        "initializer_range": 0.02,
        "torch_dtype": "float32",
    }
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")

    processor_config = {
        "processor_class": "CaptchaProcessor",
        "auto_map": {"AutoProcessor": AUTO_MAP["AutoProcessor"]},
        "glyph_height": cfg["glyph_height"],
        "min_width": cfg["min_width"],
        "max_width": cfg["max_width"],
        "charset": charset,
        "blank_index": 0,
        "mean": 0.5,
        "std": 0.5,
        "pad_value": 0.0,
        "line_std_threshold": 6.0,
    }
    with open(os.path.join(out_dir, "processor_config.json"), "w", encoding="utf-8") as f:
        json.dump(processor_config, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # The 4.x layout, and the fallback for anybody whose `processor_config.json` is
    # missing. Same attributes, plus the `auto_map` that resolves the class.
    preprocessor_config = dict(processor_config)
    with open(os.path.join(out_dir, "preprocessor_config.json"), "w", encoding="utf-8") as f:
        json.dump(preprocessor_config, f, indent=2, ensure_ascii=False)
        f.write("\n")

    vocab = {
        "blank_index": 0,
        "blank_token": "<blank>",
        "charset": charset,
        "stoi": {c: i + 1 for i, c in enumerate(charset)},
        "itos": {str(i + 1): c for i, c in enumerate(charset)},
    }
    with open(os.path.join(out_dir, "vocab.json"), "w", encoding="utf-8") as f:
        json.dump(vocab, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with open(os.path.join(out_dir, "LICENSE"), "w", encoding="utf-8") as f:
        f.write(MIT_LICENSE)

    # The weights. `safetensors` writes exactly the tensors of the state dict, with the
    # same names the model has, so `from_pretrained` finds every one of them.
    from safetensors.torch import save_file

    tensors = {k: v.detach().cpu().contiguous() for k, v in state.items()}
    save_file(tensors, os.path.join(out_dir, "model.safetensors"), metadata={"format": "pt"})


def export_onnx(out_dir: str, state: dict, cfg: dict, charset: str) -> str:
    """Export the ONNX graph with `torch.onnx.export`.

    `optimum` is not used and cannot be: `transformers.onnx` was removed in
    transformers 5.x and `optimum-onnx` 0.1.0 declares `transformers<4.58.0,>=4.36`.

    The dynamo exporter (the default since torch 2.9) cannot lower `nn.LSTM` in this
    torch build, so the TorchScript exporter is the fallback. Both are
    `torch.onnx.export`; the width stays a dynamic axis either way.
    """
    if TRAIN_DIR not in sys.path:
        sys.path.insert(0, TRAIN_DIR)
    from captcha_crnn import CRNN

    class Wrapper(nn.Module):
        def __init__(self, model):
            super().__init__()
            self.model = model

        def forward(self, pixel_values):
            f = self.model.cnn(pixel_values)
            b, c, h, w = f.shape
            f = f.permute(0, 3, 1, 2).reshape(b, w, h * c)
            f, _ = self.model.rnn(f)
            return self.model.fc(f)

    model = CRNN(cfg["num_classes"], glyph_height=cfg["glyph_height"])
    model.load_state_dict(state)
    model.eval()
    wrapper = Wrapper(model).eval()

    path = os.path.join(out_dir, "onnx", "model.onnx")
    sample = torch.zeros(1, 1, cfg["glyph_height"], 128)

    errors = []
    try:
        from torch.export import Dim

        torch.onnx.export(
            wrapper, (sample,), path,
            input_names=["pixel_values"], output_names=["logits"],
            dynamic_shapes={"x": {0: Dim("batch"), 3: Dim("width")}},
            opset_version=18, dynamo=True,
        )
        return "dynamo"
    except Exception as exc:  # noqa: BLE001 - the fallback is the point
        errors.append(f"dynamo exporter: {type(exc).__name__}: {exc}")
        log(f"  the dynamo ONNX exporter failed ({type(exc).__name__}); "
            f"falling back to the TorchScript exporter")

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        torch.onnx.export(
            wrapper, (sample,), path,
            input_names=["pixel_values"], output_names=["logits"],
            dynamic_axes={"pixel_values": {0: "batch", 3: "width"},
                          "logits": {0: "batch", 1: "time"}},
            opset_version=17, dynamo=False,
        )
    return "torchscript"
