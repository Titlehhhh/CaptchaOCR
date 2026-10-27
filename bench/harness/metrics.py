"""The metrics of the harness: Unicode-aware exact match and CER."""

import statistics


def norm(s) -> str:
    """Unicode-aware normalisation of an OCR string.

    Keeps letters and digits of *any* script plus the arithmetic operators, and
    drops everything else (spaces, punctuation, artefacts).  The old harness
    used ``re.sub(r"[^A-Za-z0-9+\\-*]", "", s)``, which silently emptied every
    Cyrillic sample; that is why the old numbers only cover ASCII types.
    """
    if s is None:
        return ""
    out = []
    for ch in str(s):
        if ch.isalnum() or ch in "+-*/=×÷":
            out.append(ch)
    return "".join(out)


def lev(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(pred, gold) -> float | None:
    p, g = norm(pred), norm(gold)
    if not g:
        return None
    return lev(p, g) / len(g)


def aggregate(items, preds):
    """Per-type and overall exact-match / CER, split by 'has a band'."""
    per_type = {}
    for it, pr in zip(items, preds):
        t = it["type"]
        d = per_type.setdefault(t, {"n": 0, "exact": 0, "cer_sum": 0.0,
                                    "exact_ans": 0, "cer_ans_sum": 0.0,
                                    "has_roi": it["has_roi"]})
        d["n"] += 1
        c = cer(pr, it["text"])
        ca = cer(pr, it["answer"])
        if c is not None:
            d["cer_sum"] += c
            d["exact"] += int(norm(pr) == norm(it["text"]))
        if ca is not None:
            d["cer_ans_sum"] += ca
            d["exact_ans"] += int(norm(pr) == norm(it["answer"]))

    def block(rows):
        if not rows:
            return None
        accs = [d["exact"] / max(d["n"], 1) for d in rows]
        cers = [d["cer_sum"] / max(d["n"], 1) for d in rows]
        n = sum(d["n"] for d in rows)
        ex = sum(d["exact"] for d in rows)
        cs = sum(d["cer_sum"] for d in rows)
        exa = sum(d["exact_ans"] for d in rows)
        csa = sum(d["cer_ans_sum"] for d in rows)
        return {
            "types": len(rows),
            "items": n,
            "acc_micro": round(ex / max(n, 1), 4),
            "cer_micro": round(cs / max(n, 1), 4),
            "acc_micro_answer": round(exa / max(n, 1), 4),
            "cer_micro_answer": round(csa / max(n, 1), 4),
            "acc_median_over_types": round(statistics.median(accs), 4),
            "cer_median_over_types": round(statistics.median(cers), 4),
            "acc_mean_over_types": round(statistics.fmean(accs), 4),
            "cer_mean_over_types": round(statistics.fmean(cers), 4),
            "types_with_acc_1": sum(1 for a in accs if a >= 0.999),
            "types_with_acc_0": sum(1 for a in accs if a <= 0.001),
        }

    band_rows = [d for d in per_type.values() if d["has_roi"]]
    noband_rows = [d for d in per_type.values() if not d["has_roi"]]
    blocks = {
        "roi_types": block(band_rows),
        "no_roi_types": block(noband_rows),
        "all_types": block(list(per_type.values())),
    }
    for d in per_type.values():
        n = max(d["n"], 1)
        d["acc"] = round(d["exact"] / n, 4)
        d["cer"] = round(d["cer_sum"] / n, 4)
        d["acc_answer"] = round(d["exact_ans"] / n, 4)
        d["cer_answer"] = round(d["cer_ans_sum"] / n, 4)
        del d["exact"], d["cer_sum"], d["exact_ans"], d["cer_ans_sum"]
    return {
        "per_type": per_type,
        **blocks,
    }
