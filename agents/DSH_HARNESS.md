# DSH HARNESS — what the DeepSeek Harness reads from this repository

**Companion files:** [`agents/INDEX.md`](INDEX.md) (where everything in the repo is),
[`agents/AGENT_LOG.md`](AGENT_LOG.md) (who owns what, and the subagent protocol).

**What this file is for:** an agent that has never seen the DeepSeek Harness ("DSH") needs to know
*what the harness will read from this repository*, *what it will ignore*, and *what the repository
therefore has to provide*. This file answers that, and every claim about the harness carries a
`path:line` citation into the harness source.

**Rule of this document:** if the harness source does not show it, it does not exist as far as this
document is concerned. Where something could not be verified, it says **"not verified"** and says what
was tried. Nothing here is inferred from marketing, from a README, or from memory.

Paths are relative to the harness checkout `C:\Users\Title\deepseek-harness` unless stated otherwise.

---

## 1. The harness on this machine

| Fact | Value | Evidence |
|---|---|---|
| Harness source checkout | `C:\Users\Title\deepseek-harness` — a git repo with `packages/`, `apps/`, `docs/`, `patches/` | the checkout itself; `packages/bundle/base/cordis.patch.yml` is its base composition |
| Installed npm package | `@deepseek-ai/dsh` **0.2.1-rc.2**, at `C:\Users\Title\AppData\Local\npm-cache\_npx\1e7f6d9597241db0\node_modules\@deepseek-ai\dsh` | `node_modules/@deepseek-ai/dsh/package.json` — `"name": "@deepseek-ai/dsh"`, `"version": "0.2.1-rc.2"` |
| What the package ships | only `lib/*.js` + `lib/types/*.d.ts` + the READMEs — **no source** | same `package.json`, the `"files"` field |
| Harness home | `C:\Users\Title\.dsh` (`$DSH_HOME`), containing `skills/`, `sessions/`, `profiles/`, `storages/`, `.agent-presets/` | `resolveDshHome()` — `packages/util/home-paths/src/index.ts:79-95`; `defaultDshHome()` — `:61-62` |
| Active profile | `web` — `$DSH_PROFILE=web`, `$DSH_PROFILE_DIR=C:\Users\Title\.dsh\profiles\web` | the session's environment; the profile dir holds `cordis.yml` + `cordis.patch.yml` |
| Web GUI | `http://127.0.0.1:3080` | `DSH_WEB_URL` in the session environment; the default bind is `127.0.0.1:3080` — `packages/bundle/web-app/cordis.patch.yml:134-139` |
| Active agent preset | `standard-ddgs`, at `C:\Users\Title\.dsh\.agent-presets\standard-ddgs\agent.cordis.yml` | `$DSH_HOME/.agent-presets/`; the default preset row is `packages/bundle/web-app/cordis.patch.yml:487-491` |
| Model route | `openrouter` → `minimax/minimax-m3.1-flash:free` | `C:\Users\Title\.dsh\profiles\web\cordis.patch.yml:6-10` |

**How to read the harness source.** The npm package is not the source of truth — it ships only
compiled `lib/`. The truth is the checkout: `packages/<group>/<package>/src/*.ts`. Each package has a
one-line module docstring that states what it is; the `README.md` next to it usually carries the
composition rules. Two directories matter most for this repository:
`packages/context/agent-instructions/` (the AGENTS.md loader) and `packages/skill/` (the skill
registry and the filesystem provider).

**Read the *active* composition, not the source in isolation.** The running tree is:
`packages/bundle/base/cordis.patch.yml` → `packages/bundle/web-app/cordis.patch.yml` (the web surface
disables many base rows) → `$DSH_PROFILE_DIR/cordis.patch.yml` (the user's layer) → the agent preset
`$DSH_HOME/.agent-presets/<id>/agent.cordis.yml` (the agent plane). **A row that is disabled in the
web bundle can still be live because the preset mounts it instead** — that is exactly what happens to
`skill-filesystem` and `agent-instructions` (§2.1, §2.2).

---

## 2. What the harness reads from a workspace

### 2.1 Workspace instruction files (AGENTS.md)

**Which files.** Per directory, the candidates are `AGENTS.md` and `CLAUDE.md`, and the local overlays
are `AGENTS.local.md` and `CLAUDE.local.md` —
`packages/context/agent-instructions/src/config.ts:11-13`. There is one user-global file,
`$DSH_HOME/AGENTS.md` (`render.ts:98`).

**Which project root.** The loader walks up from the session cwd until it finds a directory that
contains a marker; the only default marker is **`.git`** — `config.ts:11`, `files.ts:181-197`. For
this repository that is `C:\Users\Title\Projects\CaptchaOCR` (the repo has a `.git` directory).

**Which order.** Discovery order is the model precedence order: the user-global file first, then the
chain of directories from the project root down to the cwd, **broadest first**; inside one directory
the base candidates come before the local overlays — `files.ts:285-313` (the chain is built by
`ancestorChain`, `files.ts:204-217`). Two files in the *same* directory whose trimmed content is
identical collapse to the earlier one — `files.ts:375-391`.

**What the agent sees.** Each loaded file is rendered as
`Instructions from: <project-relative path>` + its content, wrapped in a `<system-reminder>` with a
fixed intro paragraph — `render.ts:85-87`, `render.ts:12-14`, `render.ts:227-243`.

**The byte budget — the rule that matters.**

| Knob | Value | Meaning | Evidence |
|---|---|---|---|
| `maxBytes` | **65536** | the **total** budget for *all* instruction files rendered together, including the `<system-reminder>` framing and the intro paragraph | `packages/bundle/base/cordis.patch.yml:268-271`; restated by the active preset at `C:\Users\Title\.dsh\.agent-presets\standard-ddgs\agent.cordis.yml:31-34`; the field is documented as "UTF-8 byte cap for one rendered baseline" in `config.ts:22-24` |
| `maxSourceBytes` | **1 048 576** (1 MiB) | a **per-file** cap on the *source* read | `config.ts:14`, `config.ts:43` |
| `maxBytes <= 0` | disables loading entirely | no instructions at all | `files.ts:419-420`, `render.ts:280-282` |

Two different things, and the difference matters:

- **A file bigger than 1 MiB is ignored entirely** — not truncated. `readBounded()` returns
  `undefined` for it (`files.ts:344`, and the streaming guard at `files.ts:350-357`). It simply is not
  in the baseline.
- **The 64 KiB budget applies to the rendered total.** If the rendered text does not fit, the
  renderer first **omits the broadest files** one by one (`render.ts:289-294`), and if only the most
  specific file is left and still does not fit, it **truncates that file** at a UTF-8 code-point
  boundary (`render.ts:249-273`, `render.ts:296-315`; the cut is UTF-8-safe, `render.ts:69-79`).
  If even that does not fit, only a bare marker survives (`render.ts:317-331`).
- The agent is **told** what happened, in the prompt itself:
  `Workspace instruction budget 65536 bytes: omitted <path>; truncated <path> from N to M bytes`
  (`render.ts:215-225`), and the compact variant of the intro says
  "Workspace instructions were omitted or truncated to fit the configured byte budget"
  (`render.ts:19`).

**Practical limit for this repository's `AGENTS.md`.** `AGENTS.md` at the project root is the *most
specific* instruction file (the user-global `~/.dsh/AGENTS.md` does not exist on this machine, and
there is no deeper directory in the chain), so when it outgrows the budget it is **truncated, not
omitted** — the model sees the *beginning* of the file and a marker line, and silently loses the tail.
The tail is where the environment notes and the safety rules live, so this is a real failure mode and
not a theoretical one. The framing overhead is roughly 300 bytes (the wrapper, the intro paragraph
and the section header), so:

> **Keep `AGENTS.md` well under 65536 bytes — target ≤ 60000 — and never let it grow past the budget
> without checking.** If it is truncated, the agent works without the rules, and says nothing about it.

**Re-projection on file touch.** After a `read`, `write` or `edit` tool call, the loader re-projects
the touched file's instructions into the agent's context (`index.ts:74`, `index.ts:343-359`), and
`AGENTS.md` in a *nested* directory under the project root is loaded too when the session cwd is
deeper (`files.ts:306-312`). In this repository the session cwd is the project root, so only the
root `AGENTS.md` applies.

### 2.2 Skills

**Which roots are scanned, and in which order.**

| Root | Rank | Source label | Evidence |
|---|---|---|---|
| `<projectRoot>/.dsh/skills` | 100 | `project-dsh` | `packages/skill/skill-filesystem/src/index.ts:36-40`, `:250` |
| `<projectRoot>/.agents/skills` | 200 | `project-agents` | same, `:251` |
| `customSkillDirs` (config only) | 300 | `custom` | same, `:254` |
| `$DSH_HOME/skills` (= `C:\Users\Title\.dsh\skills`) | 400 | `user-dsh` | same, `:257` |
| `~/.agents/skills` (`$DSH_AGENTS_HOME` or `~/.agents`) | 500 | `user-agents` | same, `:258`, `:168` |
| the bundled root (`$DSH_BUNDLED_SKILL_DIR`) | 600 | `bundled` | same, `:262`; rank constant `packages/skill/skill/src/index.ts:28` |

The project root for skills is found the same way — walk up to `.git` —
`skill-filesystem/src/index.ts:945-955`. **The project roots are scanned only when the lookup has a
`cwd`** — `skill-filesystem/src/index.ts:247` — and the skill tool always passes the session cwd
(`packages/skill/tool-skill/src/index.ts:133`, `:222`).

**Precedence.** Within one registry layer, the **lower rank wins** — `skill/src/index.ts:807-811`.
Across layers, the nearest scope layer wins outright (`skill/src/index.ts:551-565`). So a project
skill beats a user skill, which beats the bundled one.

**What a skill is.** A directory containing `SKILL.md`, or a flat `*.md` file in the root —
`skill-filesystem/src/index.ts:728-733`.

**The frontmatter contract.**

- The file must start with `---` on the first line and close with `---`; the YAML between them is
  the frontmatter — `skill-filesystem/src/index.ts:917-929`.
- `name` and `description` are **mandatory**; a file missing either is ignored with a warning —
  `skill-filesystem/src/index.ts:814-819`.
- `name` must be kebab-case: `/^[a-z0-9]+(?:-[a-z0-9]+)*$/` — `skill/src/index.ts:21`, `:35-37`.
- `whenToUse` (optional string) and `metadata` (optional object) are passed through —
  `skill-filesystem/src/index.ts:114`, `:834`, `:1039-1045`.
- `disable-model-invocation` and `user-invocable` are the invocation switches; the legacy spellings
  `disableModelInvocation` / `modelInvocable` / `userInvocable` are **rejected** with an error —
  `skill-filesystem/src/index.ts:1000-1016`.

**Is a project skill "trusted" or "enabled"?** There is no trust gate for project skills. The
**bundled** root is `trustedHost` and is read with plain Node `fs`; every other root — including the
project roots — is read through `ctx.fs`, the sandboxed filesystem provider —
`skill-filesystem/src/index.ts:95`, `:262`, `:755-756`, `:846-893`. Under the `danger-full-access`
file mode of this session that read is unrestricted; under `workspace-write` the file still has to be
inside the readable workspace. A skill can be hidden from the model catalog with
`disable-model-invocation: true`, and from the human catalog with `user-invocable: false`.

**How a skill reaches the model.** The catalog is published as an `<available_skills>` block with only
the name and the description — `packages/skill/tool-skill/src/index.ts:254-277`; the description is
normalised and capped at **500 characters** — `:27`, `:391-395`. The model then calls the `skill`
tool with the exact name, and the body is returned as `<skill_content>` — `:81-161`,
`packages/skill/skill/src/index.ts:170-183`. A user may also invoke a skill with a `/name` line —
`tool-skill/src/index.ts:177-204`, `:409-430`.

**Is the project root active in this profile?** Yes, and this is verifiable two ways:

1. *Composition.* The **host** `skill-filesystem` row is disabled in the web bundle
   (`packages/bundle/web-app/cordis.patch.yml:406-407`), but the **active preset** mounts
   `skill-filesystem` and `tool-skill` itself
   (`C:\Users\Title\.dsh\.agent-presets\standard-ddgs\agent.cordis.yml:84-88`). The preset's row
   carries **no config**, so `includeDefaultRoots` keeps its schema default of `true`
   (`skill-filesystem/src/index.ts:78`) — the project roots are included.
2. *Runtime.* This session's own available-skills catalog contains `web-search` (from
   `C:\Users\Title\.dsh\skills\web-search\SKILL.md`) and the bundled
   `diagnose-windows-sandbox-acl` — so the filesystem provider is live in the `web` profile, and the
   rank table above is the live table. **And the two project-local skills this session added —
   `.agents/skills/captcha-dataset/SKILL.md` and `.agents/skills/captcha-train/SKILL.md` — appeared in
   the live catalog as `captcha-dataset` and `captcha-train` the moment they were written.** That is
   the end-to-end proof that `<projectRoot>/.agents/skills` is scanned in this profile.

**Size cap for a `SKILL.md`.** No truncation rule was found: the file is read whole, either with
`readFile` or with `fs.readText` — `skill-filesystem/src/index.ts:846-893`. The only size-related
limit is the 500-character cap on the *description* in the catalog. Keep a `SKILL.md` short anyway:
it is loaded into the context of every agent that calls the `skill` tool.

### 2.3 Subagents and workflows

**The tools.**

| Tool | Package | Evidence |
|---|---|---|
| `subagent` | `packages/subagent/tool-subagent` (tool name is the `toolName` config key) | `tool-subagent/src/index.ts:323`, `:389-399` |
| `subagent_fork` | the same package, mounted a second time with `provider: fork` | `tool-subagent/src/index.ts:400-428`; base bundle `packages/bundle/base/cordis.patch.yml:349-367` |
| `send_message`, `interrupt_agent` | `packages/subagent/tool-subagent-control` | `tool-subagent-control/src/index.ts:28-29`, `:76-77` |
| `list_agents` | `packages/subagent/tool-subagent-control/list-agents` | `tool-subagent-control/src/list-agents.ts:17` |
| `workflow` | `packages/workflow/tool-workflow` (the model-facing tool) | `tool-workflow/src/index.ts:28-41` |
| the workflow engine | `packages/workflow/workflow` — the `ctx.workflowEngine` service | `workflow/src/index.ts:31-34` |
| the workflow provider | `packages/workflow/workflow-ptc` | base bundle `packages/bundle/base/cordis.patch.yml:372-378` |

**The backends.** `packages/subagent/` contains `subagent-spawn-in-process` (the `spawn` provider: a
fresh child, no parent context — `subagent-spawn-in-process/src/index.ts:49-50`),
`subagent-fork-in-process` (the `fork` provider: the child is seeded with the parent's
completed-turn prefix — `subagent-fork-in-process/src/index.ts:70-83`),
`subagent-in-process-driver` (the shared driver), `subagent-acp`, `subagent-claude-code`,
`subagent-codex` and `subagent-dsh-sdk` (out-of-process providers).
`subagent-codex` and `subagent-claude-code` are **disabled** in the active preset — they need an
extra bundle that production `dsh` does not install —
`C:\Users\Title\.dsh\.agent-presets\standard-ddgs\agent.cordis.yml:200-220`.

**The delegation contract.** The `subagent` tool takes exactly `description` (3–5 words, for
display) and `prompt` (the whole brief), plus optional `provider` / `model` / `reasoning_effort` and
`run_in_background` — `tool-subagent/src/index.ts:389-428`. **There is no `cwd` parameter**: the
child inherits the parent's session cwd — `packages/subagent/subagent/src/child-agent.ts:144-147`.
The default recursion cap is `maxDepth: 3` — `tool-subagent/src/index.ts:129`.

### 2.4 The key question: can a repository define its own subagents?

**No.** A repository cannot define subagents, agent roles, or personas that the harness will load.
The evidence:

1. **The child's composition is supplied at the tool call**, not discovered from disk: the tool
   parameters are `description` + `prompt` (+ optional model selection) —
   `packages/subagent/tool-subagent/src/index.ts:389-419`. The persona and the tool filter are
   *plugin configuration* of the mounted tool, not per-task data — `:78-93`.
2. **The durable record of a child carries no file-backed role**: the `subagent/descriptor` session
   event holds the mode (`one-shot` / `continuable`), the provider name, a label, the model route, an
   optional persona and an optional tool filter — `packages/subagent/subagent/src/descriptor.ts:50-92`.
   Nothing is read from the workspace to build it.
3. **There is no loader for workspace-relative agent definitions.** Searching every source file of
   `packages/subagent/**` for `readFile` / `readdir` / `join(projectRoot…)` finds only test fixtures
   and the two out-of-process SDK bootstraps (`subagent-codex/src/run.ts:46`,
   `subagent-claude-code/src/process.ts`) — neither of which reads agent *roles* from a workspace.
   The same search over the whole `packages/` tree finds **no** `agents/`, `AGENTS.json` or
   agent-role loader.
4. **The only "agent" the harness knows is the preset** — a host-plane composition at
   `$DSH_HOME/.agent-presets/<id>/agent.cordis.yml`, which is *not* a workspace file.

**What this means for this repository.** The `agents/` folder here is **our own convention**, not a
harness feature. `agents/INDEX.md`, `agents/AGENT_LOG.md` and `agents/DSH_HARNESS.md` are read by
*agents* (and by a human), on request — the harness never opens them. No document in this repository
may imply that the harness loads them automatically.

### 2.5 What the harness does **NOT** read from the workspace

Do not wait for these; they do not exist.

| Not read from the project | Where that file actually lives | Evidence |
|---|---|---|
| `cordis.patch.yml` | the bundle's own patch file and `$DSH_PROFILE_DIR/cordis.patch.yml` | `packages/boot/app-boot/src/profile.ts:53`; the active one is `C:\Users\Title\.dsh\profiles\web\cordis.patch.yml` |
| a settings file | `$DSH_HOME/settings.yaml` (hot-reloaded) | `packages/bundle/base/cordis.patch.yml:87-92` |
| a project-level `.dsh/` config of any kind | **nothing** — the only `.dsh/` path read from a project is `.dsh/skills` | `packages/skill/skill-filesystem/src/index.ts:250` |
| `.mcp.json` or any MCP server file | nothing — the MCP surface is host-configured | searched `packages/**` for `\.mcp\.json` → no match |
| a subagent / agent-role / persona directory | nothing — see §2.4 | `packages/subagent/**` search |
| `README.md`, `HANDOVER.md`, `CONTINUE.md`, `agents/*.md`, `build.ps1`, `paths.py` | nothing — these are read by *agents*, on request | the instruction loader's candidate list is closed: `config.ts:11-13` |
| `CLAUDE.md` / `AGENTS.local.md` | they *are* read **if they exist** — this repository has neither | `config.ts:12-13` |

**The one genuine exception:** a **project `.env`** is read as a read-only credential fallback —
`packages/credentials/credentials-local/src/index.ts:8` (and the base bundle's comment on the
credential sources, `packages/bundle/base/cordis.patch.yml:93-97`). This repository has no `.env`.

---

## 3. What this repository provides

| File | What it is | Who reads it | When it is loaded |
|---|---|---|---|
| `AGENTS.md` | the workspace instruction file — the only file the harness itself reads from this project | the harness's instruction plugin (`@deepseek-ai/dsh-agent-instructions`) | into the durable context before the first request, and re-projected after a `read`/`write`/`edit` touch (`agent-instructions/src/index.ts:315-341`, `:343-359`) |
| `agents/DSH_HARNESS.md` | this file — what the harness reads, and what it does not | agents (on request) | never automatically |
| `agents/INDEX.md` | the agent-facing map of the whole repository | agents (on request) | never automatically |
| `agents/AGENT_LOG.md` | the ownership table and the session log; the subagent protocol | agents (on request) | never automatically |
| `agents/INDEX.json` | the machine-readable index | agents (on request) | never automatically |
| `HANDOVER.md` | the project state, the A/B/C type split, the measured journal | agents (on request) | never automatically |
| `CONTINUE.md` | the "paste this into a new session" prompt | the human (on request) | never automatically |
| `README.md` | the dataset's own per-plugin documentation | agents (on request) | never automatically |
| `.agents/skills/captcha-dataset/SKILL.md` | a **project skill** — how to build, validate and inspect the dataset | the harness's skill provider (`@deepseek-ai/dsh-skill-filesystem`) | the skill catalog is published to the model at each step; the body is loaded only when the `skill` tool is called (`tool-skill/src/index.ts:213-251`) |
| `.agents/skills/captcha-train/SKILL.md` | a **project skill** — how to run the trainer, and the traps that cost this project days | the same | the same |
| `build.ps1` | the one-shot rebuild script | **nobody** — it cannot be executed on this machine (see §5) | never |
| `dataset/out/`, `dataset/out_ru/` | the generated dataset | agents (read), the main agent (regenerates) | never automatically |
| `dataset/out_ru/*/real_shots/` | the reference images | agents (read only) | never automatically |
| `tools/*.py`, `train/*.py`, `bench/*.py` | the checkers, the trainer, the benchmark harnesses | agents | never automatically |
| `reports/**` | measured results | agents (read) | never automatically |

---

## 4. The subagent protocol for this repository

The full protocol lives in [`agents/AGENT_LOG.md`](AGENT_LOG.md) §1 and is not repeated here. The
harness-side facts that shape it:

- The harness gives a child **only what the brief contains**. The `spawn` backend starts a fresh
  child with no parent context (`subagent-spawn-in-process/src/index.ts:49-50`); the `fork` backend
  seeds it with the parent's completed turns (`subagent-fork-in-process/src/index.ts:70-83`).
  **Neither inherits the parent's working knowledge automatically** — hence a brief must be
  self-contained.
- The child works in the **same workspace** as the parent: the cwd is inherited, not a parameter —
  `subagent/src/child-agent.ts:144-147`. Ownership of files is therefore *not* enforced by the
  harness; it is enforced by the brief and by `agents/AGENT_LOG.md` §2.
- A child that stops half-way through an edit leaves the tree inconsistent; **compilation catches
  it** (§5.4).
- The child's final message *is* the result — there is no separate artefact channel.

Summary of the roles:

| Step | Who | What |
|---|---|---|
| brief | main agent | 8 parts, per `AGENTS.md` §0 and `agents/AGENT_LOG.md` §1.2 |
| work | subagent | only the files it owns; no commit |
| report | subagent | files touched / what was verified / what was not / what is broken / discrepancies |
| accept | main agent | the acceptance checklist in `AGENTS.md` §0 |
| log | main agent | a row in `agents/AGENT_LOG.md` §3 |
| commit | main agent | only the main agent commits |

---

## 5. Traps

### 5.1 The instruction budget

`AGENTS.md` is capped at **65536 rendered bytes in total** (§2.1). Over the cap it is *truncated*,
the tail disappears, and the agent says nothing about it. Keep it ≤ 60000 bytes. This document
(`agents/DSH_HARNESS.md`) is **not** part of that budget — it is never loaded automatically — so it
can be as long as it needs to be.

**Measured on 2026-10-21** (after the §0 rewrite): the file is **25 899 bytes**; rendered with the
harness's own framing (`<system-reminder>` + the intro paragraph + `Instructions from: AGENTS.md` +
the content) it is **26 201 bytes** — **39 335 bytes of headroom** under the 65 536 budget.

### 5.2 `fs-observation-policy`: read before you edit

The plugin is mounted in the base bundle (`packages/bundle/base/cordis.patch.yml:256-258`) and is
live. It keeps, per agent session, what has been *observed* about each file
(`packages/fs/fs-observation-policy/src/index.ts:21-95`):

- `edit` on a file **not read in this session** → rejected with `FS_NOT_OBSERVED` —
  `fs-observation-policy/src/index.ts:78-88`.
- `edit` on a file observed as **absent** → rejected with `FS_NOT_FOUND` — same place.
- `write` on a file observed as present → a compare-and-swap on the observed version
  (`replaceIfVersion`); on an unseen or absent file → `createIfAbsent` — `:65-71`.
- A `write`/`edit` that fails (or is rejected) does **not** record an observation
  (`agent-instructions/src/index.ts:346`).

**So: `read` the file first, then `edit` it. And if a write fails, re-read before retrying.**

### 5.3 The Windows sandbox and its ACL denials

- On Windows the sandbox backend is the **windows-acl** rung — `packages/sandbox/sandbox-local/src/index.ts:165`.
  The mechanism is a `WRITE_RESTRICTED` token plus standing write ACEs on the workspace
  (`packages/sandbox/sandbox-windows-acl/src/index.ts:1-21`).
- **Writes are restricted; reads, network and process visibility are not**
  (`sandbox-windows-acl/src/index.ts:23-25`). A read denial is therefore *not* the sandbox — look
  elsewhere.
- The denial signatures the seam recognises are `access is denied`, `access to the path`,
  `permission denied`, `operation not permitted` — `sandbox-local/src/index.ts:211`; the runner's own
  failure line is `windows-acl-run: <detail>` — `:239`.
- **Expected** denials need no repair: writes outside the workspace, any write in `read-only`, a
  piped grandchild `spawn EPERM`, and ConstrainedLanguage errors. **Unexpected** denials — a
  workspace write that fails, a directory that cannot be listed, a plainly readable path that
  cannot be read — are the case the bundled `diagnose-windows-sandbox-acl` skill exists for.
- The skill ships **inside the installed package**:
  `C:\Users\Title\AppData\Local\npm-cache\_npx\1e7f6d9597241db0\node_modules\@deepseek-ai\dsh-sandbox-windows-acl\assets\diagnose-windows-sandbox-acl\`
  (`SKILL.md` + `scripts\diagnose-windows-sandbox-acl.ps1`). It has **no modes** — one command
  inspects the path and every ancestor and repairs what it proves:
  `-Path`, `-AllowRoot`, `-Out` (skill `SKILL.md:12-25`).
- **Run it unconfined.** The script writes permissions, which the confined token cannot do, so a
  confined run would report the sandbox's own restriction as a missing right — skill
  `SKILL.md:29-31`. **Stop** after a failed or refused repair or a failed verification, and never
  remove a deny ACE by hand — `SKILL.md:47-61`.

### 5.4 `.ps1` execution is blocked, and there is no `pwsh`

- **Executing a `.ps1` file is blocked** on this machine ("AuthorizationManager check failed"),
  even for a script inside the workspace and even with an execution-policy flag. **Do not run
  `build.ps1`.** Run its logic inline in the tool call; the inline form is in
  `agents/INDEX.md` §5.1 and in the `captcha-dataset` skill.
- **There is no `pwsh` binary** — only Windows PowerShell 5.1. The harness's own `pwsh` tool
  resolves the executable as `C:\Program Files\PowerShell\7\pwsh.exe`, then a `pwsh.exe` on `PATH`,
  and **falls back to `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`** —
  `packages/shell/pwsh-local/src/resolve.ts:21-37`, `:67-79`. It always runs with
  `-NoLogo -NoProfile -NonInteractive -Command` — `pwsh-local/src/index.ts:220`. So the harness's
  PowerShell **is** Windows PowerShell 5.1 on this machine: use 5.1 syntax, and never `pwsh -File`.
- The `bash-sandbox` row is disabled on Windows and the `pwsh-sandbox` row is enabled —
  `packages/bundle/base/cordis.patch.yml:214-222`.
- A **piped** grandchild spawn fails with `EPERM` under the confined modes — the documented
  boundary, not a bug (`packages/sandbox/sandbox-windows-acl/src/index.ts:286-295`; the harness
  documents it in the skill above). Use `stdio: 'inherit'` when a child must write to the console.

### 5.5 The dataset is an artefact, not a function

The generated pixels depend on the **fonts of the machine** (Java resolves logical AWT families
through the platform font configuration). Generate the dataset **once, on this machine**, and train
from that folder — a "continuation" that regenerates sees different pixels. This is a property of the
project, not of the harness; the harness's own facts are in §2.

### 5.6 The band rule

A band that does not fit inside the frame is **not** a band: `roi()` returns `null` rather than a
rectangle that holds only part of the answer (`AGENTS.md` §6, `HANDOVER.md` §3.1). A wrong band is
worse than no band — the label cannot be fitted and the loss never comes down, and
`dev.captcha.Validate` cannot catch it. The standing checkers are `tools/check_labels_and_roi.py` and
`tools/check_band_vs_answer.py`.

### 5.7 The flat loss is not a bug

A CTC recogniser sits in an **all-blank plateau** for thousands of steps: the loss sits at `ln 63 ≈
4.14` and creeps down very slowly (`HANDOVER.md` §6.5). A flat loss before a few thousand steps is
the expected behaviour, not a defect.

---

## 6. Not verified

Stated plainly, with what was tried.

1. **Whether a project skill needs an explicit "enable" step.** No trust or enable gate for project
   skills was found. The bundled root is `trustedHost` and bypasses `ctx.fs`; the project roots do
   not (`skill-filesystem/src/index.ts:95`, `:262`, `:755-756`). No "trusted projects" list was found
   in `packages/**`. The *effective* behaviour was verified from the running profile instead (the
   `web-search` and bundled skills are in this session's catalog, and the preset mounts the
   filesystem provider with default roots).
2. **The exact `dshHome` / `agentsHome` values the mounted `skill-filesystem` row ends up with.**
   The preset's row carries no config, and the schema marks both fields as plain strings
   (`skill-filesystem/src/index.ts:79-80`) while the implementation falls back to
   `resolveDshHome(config.dshHome)` and `$DSH_AGENTS_HOME ?? ~/.agents` — `:167-168`. The *effective*
   result was observed (`$DSH_HOME\skills\web-search` is loaded; `C:\Users\Title\.agents` does not
   exist), but the resolution order inside schemastery was not traced.
3. **A size cap for `SKILL.md`.** None was found — the file is read whole
   (`skill-filesystem/src/index.ts:846-893`). The only cap found is the 500-character description cap
   in the catalog (`tool-skill/src/index.ts:27`).
4. **Whether the `web` profile's project skill roots really are active.** **Now verified at runtime:**
   the two skills this session created under `.agents/skills/` showed up in the live available-skills
   catalog (`captcha-dataset`, `captcha-train`) as soon as they were written. The watcher
   (`skill-filesystem/src/index.ts:232-234`, `:336-341`) noticed the host mutation and invalidated the
   catalog. A `.dsh/skills` project root is the same mechanism (rank 100) and is expected to behave
   identically, but it was not exercised here — **not verified**.
5. **The `dsh` CLI's own behaviour** (`dsh --profile web`, `dsh plugin …`) was not exercised; the
   installed package ships only `lib/`, and the running composition was read from the source
   checkout and from the on-disk profile/preset files instead.
6. **Whether `AGENTS.md` in a *sub*directory of this repository would ever be loaded.** It would
   (`files.ts:306-312`), but the session cwd is the project root, so it is not.
