from __future__ import annotations

import glob
import html
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

IMG_DIR = os.path.join(HERE, "img")
THUMB_DIR = os.path.join(IMG_DIR, "t")
TYPES_JSON = os.path.join(IMG_DIR, "types.json")
SCOREBOARD = os.path.join(ROOT, "reports", "model_scoreboard.json")
BENCH_DIR = os.path.join(ROOT, "reports", "bench_models")
OUT_HTML = os.path.join(HERE, "index.html")

HF_DATASET = "https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset"
HF_MODEL = "https://huggingface.co/Titlehhhh/captchaocr-ppocrv6"

FONT_STACK = {
    "ui": '"Segoe UI", "Helvetica Neue", Arial, system-ui, sans-serif',
    "display": '"Bahnschrift Light", "Segoe UI Light", "Segoe UI", "Helvetica Neue", Arial, sans-serif',
    "mono": '"Cascadia Mono", Consolas, ui-monospace, "SFMono-Regular", Menlo, monospace',
}

LIGHTBOX_JS = """
<script>
(function () {
  var TYPES = __DATA__;
  var ti = 0, si = 0, lastFocus = null;
  var lb = document.getElementById('lb');
  var img = document.getElementById('lb-img');
  var elType = document.getElementById('lb-type');
  var elGold = document.getElementById('lb-gold');
  var elPred = document.getElementById('lb-pred');
  var elScore = document.getElementById('lb-score');
  var elPos = document.getElementById('lb-pos');
  var elHf = document.getElementById('lb-hf');
  var elClose = document.getElementById('lb-close');

  function render() {
    var t = TYPES[ti], s = t.samples[si];
    img.src = s.src;
    img.alt = t.id + ' ' + s.file;
    elType.textContent = t.id;
    elGold.textContent = s.gold === null || s.gold === undefined ? '' : s.gold;
    elPred.textContent = s.pred === '' ? '(пусто)' : s.pred;
    elPred.className = s.ok ? 'ok' : 'bad';
    elScore.textContent = (s.score === null || s.score === undefined) ? '-' : s.score.toFixed(3);
    elPos.textContent = 'тип ' + (ti + 1) + '/' + TYPES.length +
      ' · образец ' + (si + 1) + '/' + t.samples.length +
      ' · exact ' + (t.exact * 100).toFixed(1) + '%' +
      ' · CER ' + (t.cer === null || t.cer === undefined ? '-' : t.cer.toFixed(3));
    elHf.href = t.hf;
  }
  function open(t, s) {
    ti = t; si = s;
    lastFocus = document.activeElement;
    render();
    lb.hidden = false;
    document.body.style.overflow = 'hidden';
    elClose.focus();
  }
  function close() {
    lb.hidden = true;
    document.body.style.overflow = '';
    if (lastFocus && lastFocus.focus) { lastFocus.focus(); }
  }
  function stepSample(d) {
    var n = TYPES[ti].samples.length;
    si = (si + d + n) % n;
  }
  function stepType(d) {
    ti = (ti + d + TYPES.length) % TYPES.length;
    var n = TYPES[ti].samples.length;
    if (si >= n) { si = n - 1; }
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest ? ev.target.closest('.shot') : null;
    if (b) { open(parseInt(b.getAttribute('data-t'), 10), parseInt(b.getAttribute('data-s'), 10)); }
  });
  lb.addEventListener('click', function (ev) { if (ev.target === lb) { close(); } });
  elClose.addEventListener('click', close);
  document.getElementById('lb-prev-sample').addEventListener('click', function () { stepSample(-1); render(); });
  document.getElementById('lb-next-sample').addEventListener('click', function () { stepSample(1); render(); });
  document.getElementById('lb-prev-type').addEventListener('click', function () { stepType(-1); render(); });
  document.getElementById('lb-next-type').addEventListener('click', function () { stepType(1); render(); });
  document.addEventListener('keydown', function (ev) {
    if (lb.hidden) { return; }
    var k = ev.key;
    if (k === 'Escape') { ev.preventDefault(); close(); }
    else if (k === 'ArrowLeft') { ev.preventDefault(); stepSample(-1); render(); }
    else if (k === 'ArrowRight') { ev.preventDefault(); stepSample(1); render(); }
    else if (k === 'ArrowUp' || k === 'PageUp') { ev.preventDefault(); stepType(-1); render(); }
    else if (k === 'ArrowDown' || k === 'PageDown') { ev.preventDefault(); stepType(1); render(); }
    else if (k === 'Home') { ev.preventDefault(); si = 0; render(); }
    else if (k === 'End') { ev.preventDefault(); si = TYPES[ti].samples.length - 1; render(); }
  });
})();
</script>
"""

LIGHTBOX_HTML = """
<div class="lb" id="lb" hidden>
  <div class="lb-panel" role="dialog" aria-modal="true" aria-label="Просмотр капчи">
    <div class="lb-head">
      <span class="mono lb-type" id="lb-type"></span>
      <button type="button" class="lb-x" id="lb-close">Esc ✕ закрыть</button>
    </div>
    <div class="lb-imgwrap"><img id="lb-img" alt=""></div>
    <div class="lb-meta">
      <div><span class="k">написано (эталон)</span><b id="lb-gold"></b></div>
      <div><span class="k">модель ответила</span><b id="lb-pred"></b></div>
      <div><span class="k">уверенность</span><b id="lb-score"></b></div>
      <div><span class="k">положение</span><span class="mono" id="lb-pos"></span>
        <br><a class="more" id="lb-hf" target="_blank" rel="noopener">все 500 на Hugging Face →</a></div>
    </div>
    <div class="lb-nav">
      <button type="button" id="lb-prev-sample">← образец</button>
      <button type="button" id="lb-next-sample">образец →</button>
      <button type="button" id="lb-prev-type">↑ тип</button>
      <button type="button" id="lb-next-type">тип ↓</button>
      <span class="mono lb-hint">←/→ образец · ↑/↓ или PgUp/PgDn тип · Esc закрыть</span>
    </div>
  </div>
</div>
"""

def e(text) -> str:
    return html.escape(str(text if text is not None else ""))

def slug(type_id: str) -> str:
    return type_id.replace("/", "__")

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def micro_band(frame: dict) -> float:
    n = sum(v["n"] for v in frame.values())
    if not n:
        return 0.0
    return sum(v["acc"] * v["n"] for v in frame.values()) / n

def models_table():
    rows = []
    for path in sorted(glob.glob(os.path.join(BENCH_DIR, "*.json"))):
        name = os.path.basename(path)
        if name.startswith("T2_"):
            continue
        d = load_json(path)
        modes = d.get("modes") or {}
        band = (modes.get("band") or {}).get("full")
        frame = (modes.get("frame") or {}).get("full")
        legacy = (modes.get("band") or {}).get("legacy64")
        lic = d.get("license") or "-"
        repo = d.get("model") or "-"
        if band and band.get("ok", True) and band.get("per_type"):
            pt = band["per_type"]
            banded = {k: v for k, v in pt.items() if v.get("has_roi")}
            band_acc = micro_band(banded)
            band_note = f"{len(banded)} типов с полосой, 20 картинок на тип"
        elif band and not band.get("ok", True):
            band_acc = None
            band_note = "замер не состоялся: " + str(
                (band.get("error") or "ошибка запуска")).split("\n")[0][:80]
        elif legacy and legacy.get("ok", True):
            band_acc = micro_band(legacy["per_type"])
            band_note = "только старый набор legacy64 (8 типов)"
        else:
            band_acc = None
            band_note = "-"
        frame_acc = None
        if frame and frame.get("ok", True) and frame.get("per_type"):
            fpt = frame["per_type"]
            fbanded = {k: v for k, v in fpt.items() if v.get("has_roi")}
            frame_acc = micro_band(fbanded if fbanded else fpt)
        rows.append({
            "key": d.get("model_key"), "repo": repo, "license": lic,
            "band": band_acc, "frame": frame_acc, "note": band_note,
            "ours": False,
        })

    crnn = load_json(os.path.join(ROOT, "reports", "TRAINING_CRNN_BIG.json"))
    h = crnn["held_out"]
    t = crnn["training_types"]
    h_micro = h["micro_over_images"]["exact_match_pct"] / 100.0
    t_micro = t["micro_over_images"]["exact_match_pct"] / 100.0
    rows.append({
        "key": "our-crnn-ctc", "repo": "our model (CRNN + CTC, from scratch)",
        "license": "-",
        "band": h_micro,
        "frame": None,
        "note": (f"невиданные типы: micro {pct(h_micro)}, median "
                 f"{pct(h['median_over_types']['exact_match_pct'] / 100.0)} "
                 f"(n={h['micro_over_images']['n_images']}); свои типы {pct(t_micro)} — "
                 f"это запоминание, а не обобщение"),
        "ours": True,
        "extra": (f"свои типы exact {t_micro} (n={t['micro_over_images']['n_images']}), "
                  f"невиданные {h_micro} (n={h['micro_over_images']['n_images']})"),
    })

    pp = load_json(os.path.join(ROOT, "reports", "TRAINING_PPOCR_V6_BIG.json"))
    soup = pp["weight_interpolation"]
    agg = soup.get("best_alpha_aggregate") or {}
    rows.append({
        "key": "our-ppocrv6-soup", "repo": "Titlehhhh/captchaocr-ppocrv6",
        "license": "Apache-2.0",
        "band": agg.get("exact_match_micro"), "frame": None,
        "note": (f"PP-OCRv6 + WiSE-FT, alpha={soup.get('best_alpha')}; "
                 f"7 удержанных типов, 3500 картинок (другой протокол!)"),
        "ours": True,
        "extra": (f"median {agg.get('exact_match_median')}, micro {agg.get('exact_match_micro')}, "
                  f"CER micro {agg.get('cer_micro')}"),
    })
    return rows

def pct(x):
    if x is None:
        return "—"
    return f"{100 * x:.1f}%"

def full_id(t) -> str:
    tree = t.get("tree") or "out"
    tid = t["type"]
    return tid if tid.startswith(tree + "/") else f"{tree}/{tid}"

def copy_thumbnails(types_meta, scoreboard):
    os.makedirs(THUMB_DIR, exist_ok=True)
    copied = 0
    for t in types_meta:
        tid = full_id(t)
        sb = scoreboard["types"].get(tid, {})
        ex = sb.get("examples") or []
        dst_dir = os.path.join(THUMB_DIR, slug(tid))
        os.makedirs(dst_dir, exist_ok=True)
        for e_ in ex:
            src = os.path.join(ROOT, e_["path"].replace("/", os.sep))
            if "real_shots" in src.replace(os.sep, "/").split("/"):
                raise RuntimeError(f"refusing to copy a real_shots picture: {src}")
            if not os.path.isfile(src):
                continue
            shutil.copyfile(src, os.path.join(dst_dir, e_["file"]))
            copied += 1
    return copied

def build():
    types_meta = load_json(TYPES_JSON)
    scoreboard = load_json(SCOREBOARD)
    sb_types = scoreboard["types"]
    agg = scoreboard["all_46"]
    held = scoreboard["held_out_7_reproduced"]
    pub = scoreboard["published_reference"]

    n_copied = copy_thumbnails(types_meta, scoreboard)
    print(f"thumbnails copied: {n_copied}")

    rows = []
    for t in types_meta:
        tid = full_id(t)
        sb = sb_types.get(tid, {})
        acc = sb.get("exact_match")
        cer = sb.get("cer")
        hf = f"{HF_DATASET}/tree/main/data/{tid}"
        rows.append(
            '<tr>'
            f'<td class="mono type">{e(tid)}</td>'
            f'<td><span class="g g{t["group"]}">{e(t["group"])}</span></td>'
            f'<td class="num">{e(sb.get("n", t["samples"]))}</td>'
            f'<td class="num strong">{pct(acc)}</td>'
            f'<td class="num">{("—" if cer is None else f"{cer:.3f}")}</td>'
            f'<td class="num">{e(sb.get("pred_len_median", "—"))}</td>'
            f'<td><a class="more" href="{e(hf)}" target="_blank" rel="noopener">все 500 →</a></td>'
            '</tr>')

    blocks = []
    lightbox_types = []
    for ti, t in enumerate(types_meta):
        tid = full_id(t)
        sb = sb_types.get(tid, {})
        acc = sb.get("exact_match")
        cer = sb.get("cer")
        hf = f"{HF_DATASET}/tree/main/data/{tid}"
        samples = []
        lb_samples = []
        for si, ex in enumerate(sb.get("examples", [])):
            ok = ex.get("exact")
            verdict = "ok" if ok else "bad"
            pred = ex.get("pred") or "(пусто)"
            src = f"img/t/{slug(tid)}/{ex['file']}"
            lb_samples.append({"src": src, "file": ex["file"], "gold": ex.get("gold_text"),
                               "pred": pred, "ok": bool(ok), "score": ex.get("score")})
            samples.append(
                f'<button type="button" class="shot" data-t="{ti}" data-s="{si}" '
                f'aria-label="{e(tid)} {e(ex["file"])} — увеличить">'
                f'<img loading="lazy" src="{e(src)}" alt="{e(tid)} {e(ex["file"])}">'
                f'<span class="cap">'
                f'<span class="mono file">{e(ex["file"])}</span>'
                f'<span class="gt">написано: <b>{e(ex.get("gold_text"))}</b></span>'
                f'<span class="pr {verdict}">модель: <b>{e(pred)}</b></span>'
                '</span></button>')
        lightbox_types.append({"id": tid, "hf": hf, "group": t["group"],
                               "exact": acc, "cer": cer, "samples": lb_samples})
        solver = t.get("solver") or "—"
        blocks.append(
            '<article class="type-card">'
            '<header class="tc-head">'
            f'<h3 class="mono">{e(tid)}</h3>'
            f'<span class="g g{t["group"]}">группа {e(t["group"])}</span>'
            f'<span class="tc-meta">n={e(sb.get("n", t["samples"]))} · '
            f'exact <b>{pct(acc)}</b> · CER <b>{e("—" if cer is None else f"{cer:.3f}")}</b> · '
            f'полоса {e(t["with_band"])}/{e(t["samples"])}</span>'
            f'<a class="more" href="{e(hf)}" target="_blank" rel="noopener">все 500 →</a>'
            '</header>'
            f'<p class="tc-solver">решающий шаг: {e(solver)}</p>'
            f'<div class="shots">{"".join(samples)}</div>'
            '</article>')

    mrows = []
    for m in sorted(models_table(), key=lambda r: (r["ours"], -(r["band"] or -1))):
        link = (f'<a href="https://huggingface.co/{e(m["repo"])}" target="_blank" rel="noopener">'
                f'{e(m["repo"])}</a>') if "/" in m["repo"] else e(m["repo"])
        mrows.append(
            '<tr>'
            f'<td>{link}</td>'
            f'<td class="num">{pct(m["band"])}</td>'
            f'<td class="num">{pct(m["frame"])}</td>'
            f'<td class="lic">{e(m["license"])}</td>'
            f'<td class="note">{e(m["note"])}</td>'
            '</tr>')

    lightbox_js = LIGHTBOX_JS.replace(
        "__DATA__", json.dumps(lightbox_types, ensure_ascii=False))
    lightbox_html = LIGHTBOX_HTML

    head = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CaptchaOCR — галерея 46 типов капч и замеры модели</title>
<style>
:root {{
  --paper:#F8F8F8; --paper-raised:#FDFDFD; --paper-deep:#EEEEEE;
  --gray:#E4E4E4; --gray-2:#D7D7D7;
  --ink:#070707; --text:#1B1B1B; --text-muted:#585858; --text-faint:#666666; --text-mute-deep:#929292;
  --kinpaku:#FFBA00; --kinpaku-vivid:#FFC700; --kinpaku-pale:#E7CE9D; --kinpaku-rich:#DDAB46; --kinpaku-deep:#9F7D45; --on-gold:#0B0903;
  --patina:#0FB6AC; --patina-pale:#8ED3CC; --patina-deep:#006662; --patina-ink:#005C58;
  --vermilion:#B23B1D;
  --instrument:#1F1F1F; --instrument-deep:#0F0F0F; --instrument-raised:#303030;
  --instrument-text:#E8E8E8; --instrument-muted:#989898;
  --rule:rgba(0,0,0,.08); --edge:rgba(0,0,0,.45);
  --radius-sm:3px; --radius-md:8px; --radius-pill:999px;
  --control-sm:26px; --control-md:32px; --control-lg:44px;
  --section-pad:clamp(72px,8vw,120px);
  --lift-1:0 1px 1px rgba(0,0,0,.05),0 2px 3px rgba(0,0,0,.04),0 6px 12px rgba(0,0,0,.05);
  --lift-2:0 1px 1px rgba(0,0,0,.04),0 3px 5px rgba(0,0,0,.05),0 12px 20px rgba(0,0,0,.06),0 32px 48px rgba(0,0,0,.07);
  --ease:cubic-bezier(.2,.8,.2,1); --quick:.12s; --settle:.2s;
  --font:{FONT_STACK['ui']};
  --font-display:{FONT_STACK['display']};
  --mono:{FONT_STACK['mono']};
}}
*{{box-sizing:border-box}}
body{{background:var(--paper);color:var(--text);font:400 1rem/1.65 var(--font);
  margin:0;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 clamp(20px,4vw,48px)}}
h1,h2,h3{{font-weight:300;letter-spacing:0;margin:0}}
a{{color:var(--patina-ink);text-decoration:none;border-bottom:1px solid transparent;transition:border-color var(--quick) var(--ease),color var(--quick) var(--ease)}}
a:hover{{border-bottom-color:var(--kinpaku-rich)}}
.mono{{font-family:var(--mono);font-size:.6875rem;letter-spacing:.12em}}
.num{{font-family:var(--mono);font-size:.8125rem;letter-spacing:.04em;text-align:right}}
.strong{{font-weight:600;color:var(--ink)}}
header.hero{{padding:clamp(56px,9vw,110px) 0 0}}
.hero h1{{font-family:var(--font-display);font-size:clamp(3.2rem,6.2vw,5.6rem);font-weight:300;line-height:1.0}}
.hero .lead{{font-size:1.125rem;color:var(--text-muted);max-width:62ch;margin:22px 0 0}}
.hero .rule{{height:1px;background:var(--rule);margin:34px 0 0}}
.facts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:1px;
  background:var(--rule);border:1px solid var(--rule);border-radius:var(--radius-sm);margin-top:40px;overflow:hidden}}
.fact{{background:var(--paper-raised);padding:20px 22px}}
.fact .k{{font-family:var(--mono);font-size:.6875rem;letter-spacing:.12em;color:var(--text-mute-deep)}}
.fact .v{{font-family:var(--font-display);font-size:2rem;font-weight:300;line-height:1.1;margin-top:6px}}
.fact .d{{font-size:.8125rem;color:var(--text-muted);margin-top:4px}}
section{{padding:var(--section-pad) 0 0}}
section:last-of-type{{padding-bottom:var(--section-pad)}}
.sec-head{{display:flex;align-items:baseline;gap:20px;flex-wrap:wrap;border-bottom:1px solid var(--rule);padding-bottom:16px}}
.sec-head h2{{font-family:var(--font-display);font-size:clamp(2.4rem,3.6vw,3.4rem);font-weight:300;line-height:1.04}}
.sec-head .hint{{color:var(--text-muted);font-size:.9375rem;max-width:70ch}}
.note{{color:var(--text-muted);font-size:.875rem}}
table{{width:100%;border-collapse:collapse;margin-top:24px}}
th{{text-align:left;font-weight:500;font-size:.75rem;letter-spacing:.06em;color:var(--text-mute-deep);
  border-bottom:1px solid var(--rule);padding:10px 10px}}
td{{padding:9px 10px;border-bottom:1px solid var(--rule);vertical-align:top;font-size:.875rem}}
td.type{{font-size:.75rem;color:var(--ink)}}
tr:hover td{{background:var(--paper-raised)}}
.g{{display:inline-flex;align-items:center;gap:6px;font-size:.6875rem;letter-spacing:.08em;
  border:1px solid currentColor;border-radius:var(--radius-sm);padding:2px 7px;color:var(--text-muted)}}
.g::before{{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}}
.gA{{color:#186A42}} .gB{{color:#165496}} .gC{{color:#8C3C14}}
.more{{font-family:var(--mono);font-size:.6875rem;letter-spacing:.1em;color:var(--kinpaku-deep);white-space:nowrap}}
.more:hover{{color:var(--ink)}}
.type-card{{background:var(--paper-raised);border:1px solid var(--rule);border-radius:var(--radius-sm);
  box-shadow:var(--lift-1);padding:20px 22px 22px;margin-top:22px}}
.tc-head{{display:flex;align-items:center;gap:14px;flex-wrap:wrap}}
.tc-head h3{{font-size:.8125rem;color:var(--ink);font-weight:500}}
.tc-meta{{color:var(--text-muted);font-size:.8125rem;margin-left:auto;text-align:right}}
.tc-meta b{{color:var(--ink);font-weight:600}}
.tc-solver{{color:var(--text-faint);font-size:.8125rem;margin:10px 0 0}}
.shots{{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:14px;margin-top:16px}}
.shot{{margin:0;padding:0;border:1px solid var(--rule);border-radius:var(--radius-sm);background:var(--paper);
  overflow:hidden;text-align:left;font:inherit;color:inherit;cursor:pointer;
  transition:border-color var(--quick) var(--ease),background-color var(--quick) var(--ease)}}
.shot:hover{{border-color:var(--kinpaku-rich);background:var(--paper-raised)}}
.shot:focus-visible{{outline:2px solid var(--patina-deep);outline-offset:3px}}
.shot img{{display:block;width:100%;height:150px;object-fit:contain;background:var(--paper-deep);
  border-bottom:1px solid var(--rule)}}
.shot .cap{{padding:8px 10px 10px;font-size:.75rem;line-height:1.5;display:flex;flex-direction:column;gap:2px}}
.shot .file{{color:var(--text-mute-deep)}}
.shot .gt{{color:var(--text-muted)}}
.shot .gt b{{color:var(--ink);font-family:var(--mono);font-size:.75rem;word-break:break-all}}
.shot .pr b{{font-family:var(--mono);font-size:.75rem;word-break:break-all}}
.shot .pr.ok{{color:var(--patina-ink)}} .shot .pr.bad{{color:var(--vermilion)}}
.lb{{position:fixed;inset:0;z-index:60;background:rgba(7,7,7,.84);display:flex;align-items:center;
  justify-content:center;padding:clamp(12px,3vw,32px)}}
.lb[hidden]{{display:none}}
.lb-panel{{background:var(--paper-raised);border:1px solid rgba(255,255,255,.14);border-radius:var(--radius-sm);
  width:min(1120px,94vw);max-height:94vh;display:flex;flex-direction:column;overflow:auto}}
.lb-head{{display:flex;align-items:center;justify-content:space-between;gap:16px;
  padding:12px 18px;border-bottom:1px solid var(--rule)}}
.lb-type{{color:var(--ink);word-break:break-all}}
.lb-imgwrap{{background:var(--paper-deep);padding:16px;display:flex;align-items:center;justify-content:center}}
.lb-imgwrap img{{max-width:100%;max-height:60vh;min-width:320px;min-height:300px;object-fit:contain;display:block}}
.lb-meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px;
  padding:16px 18px;border-top:1px solid var(--rule)}}
.lb-meta .k{{display:block;font-family:var(--mono);font-size:.6875rem;letter-spacing:.12em;color:var(--text-mute-deep)}}
.lb-meta b{{font-family:var(--mono);font-size:1rem;word-break:break-all;color:var(--ink)}}
.lb-meta .ok{{color:var(--patina-ink)}} .lb-meta .bad{{color:var(--vermilion)}}
.lb-nav{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:0 18px 18px}}
.lb-nav button,.lb-x{{font:inherit;font-size:.8125rem;min-height:32px;padding:0 12px;
  border:1px solid var(--rule);border-radius:var(--radius-sm);background:var(--paper-raised);color:var(--ink);
  cursor:pointer;transition:border-color var(--quick) var(--ease),background-color var(--quick) var(--ease)}}
.lb-nav button:hover,.lb-x:hover{{border-color:var(--kinpaku-rich);background:var(--paper-deep)}}
.lb-nav button:focus-visible,.lb-x:focus-visible{{outline:2px solid var(--patina-deep);outline-offset:3px}}
.lb-hint{{margin-left:auto;color:var(--text-mute-deep)}}
.badge-ok{{color:var(--patina-ink)}} .badge-bad{{color:var(--vermilion)}}
code,.mono code{{font-family:var(--mono);font-size:.78rem;background:var(--paper-deep);padding:1px 5px;border-radius:var(--radius-sm)}}
pre{{background:var(--instrument);color:var(--instrument-text);border-radius:var(--radius-sm);
  padding:20px 22px;overflow:auto;font-family:var(--mono);font-size:.8125rem;line-height:1.6}}
pre .c{{color:var(--instrument-muted)}}
.lic{{color:var(--text-faint);font-size:.75rem}}
.note-cell{{color:var(--text-muted);font-size:.8125rem}}
footer{{border-top:1px solid var(--rule);margin-top:var(--section-pad);padding:28px 0 60px;color:var(--text-mute-deep);font-size:.8125rem}}
.two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:28px}}
.box{{background:var(--paper-raised);border:1px solid var(--rule);border-radius:var(--radius-sm);padding:20px 22px;box-shadow:var(--lift-1)}}
.box h3{{font-size:1.0625rem;font-weight:600;margin-bottom:8px}}
.kicker{{font-family:var(--mono);font-size:.6875rem;letter-spacing:.12em;color:var(--kinpaku-deep);text-transform:uppercase}}
</style>
</head>
<body>
<div class="wrap">

<header class="hero">
  <h1>CaptchaOCR</h1>
  <p class="lead">46 типов капч из 23 плагинов Minecraft-антиботов, 23 000 размеченных PNG
  и честный замер опубликованной модели на каждом типе: сколько капч она решает целиком,
  где ошибается и почему.</p>
  <div class="rule"></div>
  <div class="facts">
    <div class="fact"><div class="k">ТИПОВ</div><div class="v">46</div><div class="d">23 плагина, группы A / B / C</div></div>
    <div class="fact"><div class="k">КАРТИНОК</div><div class="v">23 000</div><div class="d">500 PNG на тип</div></div>
    <div class="fact"><div class="k">EXACT MATCH (ВСЕ 46)</div><div class="v">{pct(agg["exact_match_micro"])}</div><div class="d">micro по всем картинкам</div></div>
    <div class="fact"><div class="k">MEDIAN ПО ТИПАМ</div><div class="v">{pct(agg["exact_match_median"])}</div><div class="d">медиана по 46 типам</div></div>
  </div>
</header>

<section>
  <div class="sec-head">
    <h2>Скорее таблица</h2>
    <p class="hint">Опубликованная модель <a href="{HF_MODEL}" target="_blank" rel="noopener">Titlehhhh/captchaocr-ppocrv6</a>
    (PP-OCRv6_medium_rec + WiSE-FT, α = 0.4) на всех 46 типах. Кроп: полоса <code>roi</code>,
    где она есть, иначе кадр, обрезанный по рамке чернил. Эталон — нарисованная строка
    <code>text</code>. Та же строка в таблице — то, что модель ответила.</p>
  </div>
  <table>
    <thead><tr>
      <th>ТИП</th><th>ГРУППА</th><th class="num">N</th><th class="num">EXACT</th>
      <th class="num">CER</th><th class="num">ДЛИНА ОТВЕТА</th><th></th>
    </tr></thead>
    <tbody>
{chr(10).join(rows)}
    </tbody>
  </table>
  <p class="note" style="margin-top:14px">Микро по всем 46 типам: <b>{pct(agg["exact_match_micro"])}</b> exact,
  CER <b>{agg["cer_micro"]}</b>; медиана по типам: <b>{pct(agg["exact_match_median"])}</b> exact,
  CER <b>{agg["cer_median"]}</b>.
  На тех же 7 удержанных типах этот же код даёт <b>{pct(held["exact_match_micro"])}</b> micro /
  <b>{pct(held["exact_match_median"])}</b> median — опубликованные числа были
  <b>{pct(pub["micro_exact"])}</b> / <b>{pct(pub["median_exact"])}</b>, то есть пайплайн воспроизводится.</p>
</section>

<section id="gallery">
  <div class="sec-head">
    <h2>Галерея по типам</h2>
    <p class="hint">По шесть картинок на тип: что нарисовано, что ответила модель.
    Зелёным — точное совпадение, красным — ошибка. Ссылка «все 500 →» открывает папку типа
    на Hugging Face. <b>Клик по картинке</b> открывает её крупно: ←/→ листают образцы этого типа,
    ↑/↓ (или PgUp/PgDn) — соседние типы, Esc закрывает.</p>
  </div>
{chr(10).join(blocks)}
</section>

<section>
  <div class="sec-head">
    <h2>Модели</h2>
    <p class="hint">Единый протокол: 20 картинок на тип, два режима — «полоса» и «весь кадр».
    Число — micro exact match по 29 типам, у которых есть полоса. Строки «наши» измерены
    другим протоколом (500 картинок на тип, разбиение по типам), поэтому в один столбец
    с чужими моделями они не сопоставимы — это отмечено.</p>
  </div>
  <table>
    <thead><tr><th>МОДЕЛЬ</th><th class="num">ПОЛОСА</th><th class="num">КАДР</th><th>ЛИЦЕНЗИЯ</th><th>ПРИМЕЧАНИЕ</th></tr></thead>
    <tbody>
{chr(10).join(mrows)}
    </tbody>
  </table>
</section>

<section>
  <div class="sec-head">
    <h2>Как это повторить</h2>
  </div>
  <div class="two">
    <div class="box">
      <h3>Замер</h3>
      <p class="note">Модель, датасет и пайплайн — те же, что в обучении; код импортируется,
      а не переписывается.</p>
      <pre><span class="c"># скорее таблица (46 типов, 23 000 картинок)</span>
.venv-gpu\\Scripts\\python.exe reports\\HTML\\make_scoreboard.py

<span class="c"># галерея: листы, миниатюры, страница</span>
.venv-gpu\\Scripts\\python.exe reports\\HTML\\make_report.py
.venv-gpu\\Scripts\\python.exe reports\\HTML\\make_gallery.py

<span class="c"># публикация карточки на Hugging Face</span>
.venv-gpu\\Scripts\\python.exe tools\\publish_gallery.py --dry-run
.venv-gpu\\Scripts\\python.exe tools\\publish_gallery.py</pre>
    </div>
    <div class="box">
      <h3>Честные оговорки</h3>
      <ul class="note" style="padding-left:18px;margin:0">
        <li>Эталон — <code>text</code> (что нарисовано), а не <code>answer</code> (что вводит игрок):
        в 9 типах из 46 это разные строки, нужен отдельный шаг solver'а.</li>
        <li>Группа C — это не задача OCR (ответ = название цвета, номер слота, картинка),
        поэтому нулевая точность там — это свойство типа, а не дефект модели.</li>
        <li>Кириллица и слова русским числом вне словаря модели
        (в нём нет ни одной кириллической буквы) — типы, где ответ физически нельзя выразить.</li>
        <li>Эталонные скриншоты других людей (<code>real_shots/</code>) не публикуются и не
        показываются здесь: это чужие снимки, они остаются в репозитории как основа реконструкции.</li>
        <li>Шрифты Albert Sans и Alumni Sans на этой машине не установлены — взяты ближайшие
        системные (Segoe UI / Bahnschrift, моноширинный — Cascadia Mono).</li>
      </ul>
    </div>
  </div>
</section>

<footer>
  <div class="kicker">CaptchaOCR</div>
  <p>Датасет: <a href="{HF_DATASET}" target="_blank" rel="noopener">Titlehhhh/captchaocr-dataset</a> ·
  модель: <a href="{HF_MODEL}" target="_blank" rel="noopener">Titlehhhh/captchaocr-ppocrv6</a> ·
  замеры: <code>reports/model_scoreboard.json</code> ·
  сборка страницы: <code>reports/HTML/make_gallery.py</code> ·
  замер сгенерирован {e(scoreboard["generated"])}</p>
</footer>
</div>
{lightbox_html}
{lightbox_js}
</body>
</html>
"""

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(head)
    print(f"wrote {OUT_HTML} ({os.path.getsize(OUT_HTML)} bytes)")
    return 0

if __name__ == "__main__":
    sys.exit(build())
