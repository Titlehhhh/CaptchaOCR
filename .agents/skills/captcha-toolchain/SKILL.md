---
name: captcha-toolchain
description: Use when a CaptchaOCR task needs the machine-local toolchain — locating the JDK, authenticating to Hugging Face, finding where a DeepSeek Harness skill or env layer lives, or choosing the right python. Carries the verified paths (JDK 21 on drive I:, the HF token in .hf-cache/token, the project and machine .env layers), the fact that build.ps1 cannot be executed here, and which interpreter trains on the GPU.
---

# CaptchaOCR local toolchain — where things live on this box

Every path below was read from the installed DeepSeek Harness package sources and from the machine
itself, on this computer. Nobody has to re-discover them. The tabular version is `docs/LOCAL_ENV.md`.

## The JDK: `I:\ForAndroid\Java\21`

JDK 21.0.8 (LTS) is installed at **`I:\ForAndroid\Java\21`** — a **fixed** internal NTFS volume
(drive `I:`, not removable). `JAVA_HOME` is **already set as a Windows user-level environment
variable** to that path, so every new shell inherits it; nothing has to be exported by hand.

**`java` and `javac` are *not* on `PATH`** on this machine. Reach the JDK through `JAVA_HOME`:

```powershell
$env:JAVA_HOME                                     # I:\ForAndroid\Java\21
& "$env:JAVA_HOME\bin\java.exe" -version            # 21.0.8 (2025-07-15 LTS)
$javac = "$env:JAVA_HOME\bin\javac.exe"; $java = "$env:JAVA_HOME\bin\java.exe"
```

The Java generators in `dataset/generator/` and `dataset/generator_ru/` need it. The exact build
commands are in `AGENTS.md` §4 and in the `captcha-dataset` skill.

## Hugging Face: the token is in the project cache

The account token for **Titlehhhh** lives in the project-local Hugging Face cache:

```
C:\Users\Title\Projects\CapthaModel\.hf-cache\token
```

`HF_HOME` must point at that directory for `hf` and `huggingface_hub` to find it:

```powershell
$env:HF_HOME="C:\Users\Title\Projects\CapthaModel\.hf-cache"
hf auth whoami        # [OK] Logged in / user: Titlehhhh
```

`.hf-cache/` is gitignored. **Never print, copy or commit the token itself** — quote only its path.

## Where DeepSeek Harness keeps things

Two roots, four skill layers:

| Scope | Path | Rank | What |
|---|---|---|---|
| project | `<projectRoot>\.dsh\skills\` | 100 | harness skills, project-local |
| project | `<projectRoot>\.agents\skills\` | 200 | agent skills, project-local — **this repo** |
| user | `~\.dsh\skills\` | 400 | harness skills, user-local |
| user | `~\.agents\skills\` | 500 | agent skills, user-local, shared with other agent tools |

`<projectRoot>` is the nearest ancestor directory containing `.git` — here
`C:\Users\Title\Projects\CapthaModel`. This repo already keeps `captcha-dataset` and `captcha-train`
in `.agents/skills/`, so a new project skill goes in `.agents/skills/<name>/SKILL.md`.

The harness home `~\.dsh\` (`$DSH_HOME`) holds the user data — `.credentials.yaml`, `cache/`,
`sessions/`, `profiles/`, `skills/`, `settings.yaml` (on this box the settings file is present as
`settings.yaml.imported`). The shared agents root `~\.agents\` (`$DSH_AGENTS_HOME`) is deliberately
separate from it. Both may be overridden by the `DSH_HOME` / `DSH_AGENTS_HOME` variables.

## The two `.env` layers

The harness reads **two** env files and **snapshots them at launch**, so a change takes effect on the
**next** launch, not in the running session:

| Layer | File | Owner |
|---|---|---|
| project | `C:\Users\Title\Projects\CapthaModel\.env` | this repo — `JAVA_HOME`, `HF_HOME`, `HF_HUB_CACHE`, `PYTHONIOENCODING` |
| machine | `C:\Users\Title\.dsh\.env` | this computer — `JAVA_HOME`, `PYTHONIOENCODING` |

Precedence: inherited process env → project `.env` → machine `.env`. `.env` is gitignored.

## `build.ps1` cannot be executed here

Executing a `.ps1` file is blocked by the execution policy ("AuthorizationManager check failed"),
even for a file in the working tree. **Never run `build.ps1`** — run its logic inline instead (the
commands are in `AGENTS.md` §4 and in the `captcha-dataset` skill). There is also **no `pwsh`** on this
machine: only Windows PowerShell 5.1.

## Which python trains

**`.venv-gpu\Scripts\python.exe`** — the CUDA build (`torch 2.14.1+cu126`, `cuda.is_available()` is
`True`). The **system python is CPU-only**.

```powershell
.venv-gpu\Scripts\python.exe train\train.py --trees both --epochs 80 --val-types "haq/mapcha/map" "CaptchaVerifyZ/map"
```

GPU: NVIDIA GeForce GTX 1080 Ti (11.8 GB, sm_61), driver 581.57.

## Never

- print, copy or commit the HF token — only its path;
- run `build.ps1`, or any `.ps1` at all;
- call `pwsh`;
- train on the system python;
- assume `java` is on `PATH` — it is not.
