# Licence of the CaptchaOCR dataset

**This dataset has no single licence.** Every row of it belongs to a different upstream
Minecraft anti-bot plugin, and those plugins do not share one licence. The licence of a row is
the licence of the plugin that row was re-rendered from — check the tables below before you use
the data.

That is exactly what the YAML header of the dataset card means:

```yaml
license: other
license_name: mixed-per-plugin-licences
```

| | |
|---|---|
| repository | `{REPO_ID}` (dataset) |
| captcha types | **{N_TYPES}** |
| labelled PNG | **{N_PNG_FILES}** ({N_SAMPLES} rows in `labels.jsonl`) |
| upstream plugins | **{N_PLUGINS}** |
| reconstruction modes | faithful {N_FAITHFUL_TYPES} · clean-room {N_CLEAN_ROOM_TYPES} · reconstructed {N_RECONSTRUCTED_TYPES} |

## What the pictures actually are

**Every PNG in this dataset is our own render.** All {N_PNG_FILES} images were produced by this
project's **own Java generators** — not by a live server, not by a third-party service, and not
by copying anybody else's pictures. The renders reproduce the upstream algorithms (font,
palette, noise, layout, even the upstream defect), but the pixels are a re-render, not a
screenshot of a real session.

The reference screenshots of the upstream plugins are **not** part of this dataset: they are other
people's images, they stay in the project's working tree and they are not redistributed here.

The `source` field of every row of `labels.jsonl` names the upstream class and method the type
was re-implemented from, so the provenance of any single row can be audited without trusting
this file.

## The licences, in one table

{LICENCE_SUMMARY}

## The plugins, one by one

{PLUGIN_TABLE}

## What each licence means for you

* **MIT, Apache-2.0, BSD-2-Clause, CC0-1.0** — you may use, modify and redistribute the rows of
  those types. Keep the copyright notice and the licence text of the upstream project.
* **GPL-3.0** (the `jonesdevelopment/sonar`, `China2B2T/Captcha` and `irootdev/AnBot` families) —
  the rows of those types are published under the copyleft of the upstream plugin. If you
  redistribute them, the GPL-3.0 terms of that plugin apply to what you distribute.
* **AGPL-3.0** (`LimboFilter`) — the strongest obligation of the set. The renders of those types
  reproduce the upstream algorithm, and a clean-room rewrite of the algorithm does not by itself
  remove the upstream licence: the AGPL-3.0 terms of the upstream plugin apply to those rows, and
  the upstream notice must be preserved. The upstream project is
  <https://github.com/Elytrium/LimboFilter> (© Elytrium, AGPL-3.0).
* **BSD-2-Clause plus an explicit ban on commercial hosting** (`BotFilter`) — the additional
  restriction of the upstream plugin applies to that type: it may not be used to run a commercial
  captcha-solving service.
* **No licence file / all rights reserved** — for those plugins the upstream author granted no
  permission at all. {NO_LICENCE_NOTE}

{AGPL_NOTE}

## The generator code is under a separate licence

The **data** in this repository is licensed as described above. The **generator code** of the
project that produced it is under its own licence, in the project repository — the two are not
the same thing, and the dataset card does not claim otherwise.

## What this file is, and what it is not

* It **is** the per-plugin licence breakdown of this dataset, computed from `labels.jsonl` by the
  project's publishing tool (`tools/publish_hf.py`) at upload time — the table is not typed by
  hand and cannot silently disagree with the data.
* It **is not** a licence grant by the authors of the upstream plugins, and it does not replace
  their terms. Where they granted nothing, this file says so plainly instead of inventing a
  licence.

A user of this dataset must comply with the licence of the plugin each row came from.
