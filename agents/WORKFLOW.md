# agents/WORKFLOW.md — как запускать workflow-оркестрацию

**Зачем:** главный агент (DeepSeek) дорог для владельца; субагенты на бесплатных моделях
OpenRouter стоят ноль. Владелец просил использовать их **по максимуму** — «маленькая,
тупенькая, но бесплатная». Этот файл — проверенный рецепт, чтобы каждый агент не
переоткрывал механизм заново.

## Проверено 2026-10-26 (эта машина, харнесс DSH)

| модель | как указана | статус |
|---|---|---|
| `recursive/flint-v1.0:free` | `provider: "openrouter", model: "recursive/flint-v1.0:free"` | **работает** |
| `recursive/flint-v1.0:free` | только `model`, без provider | **работает** |
| `thinkingmachines/inkling:free` | `provider: "openrouter", model: …` | **работает** |
| `nvidia/nemotron-3.5-super-vl:free` | `provider: "openrouter", model: …` | **не работает** (child failed) |

**Выбор по умолчанию: `recursive/flint-v1.0:free`.** Fallback: `thinkingmachines/inkling:free`.
Суффикс `:free` — часть id модели на OpenRouter; без него тариф платный.

## Бесплатные модели OpenRouter — полный список (проверен 2026-10-27 через `/api/v1/models`)

Все 19 моделей с `pricing.prompt=0` и `pricing.completion=0`:

| id | контекст | примечание |
|---|---|---|
| `recursive/flint-v1.0:free` | 262 144 | **работает** (основная) |
| `thinkingmachines/inkling:free` | 1 048 576 | **работает** (fallback) |
| `thinkingmachines/inkling-small:free` | 1 048 576 | **не работает** (child failed, 27.10) |
| `nvidia/nemotron-3.5-lightning:free` | 1 000 000 | **работает** (протестирован 27.10) |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 1 000 000 | **работает** (протестирован 27.10) |
| `poolside/laguna-s-2.1:free` | 262 144 | **работает** (протестирован 27.10) |
| `nvidia/nemotron-3.5-super-vl:free` | 1 000 000 | **не работает** (child failed) |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | 256 000 | не работает (27.10) |
| `xingchen-agi/xing4.0-29b-a4b:free` | 262 144 | не работает (27.10) |
| `dots-studio/dots-3-note-preview:free` | 512 000 | не работает (27.10) |
| `liquid/lfm-2.5-2.6b:free` | 65 536 | не работает (27.10) |
| `poolside/laguna-xs-2.1:free` | 262 144 | не работает (27.10) |
| `cohere/north-mini-code:free` | 256 000 | не работает (27.10) |
| `google/gemma-4-26b-a4b-it:free` | 262 144 | не работает (27.10) |
| `google/gemma-4-31b-it:free` | 262 144 | не работает (27.10) |
| `nvidia/nemotron-3.5-content-safety:free` | 128 000 | не для кода (content-safety) |
| `openrouter/free` | 200 000 | роутер по всем free |
| `google/lyria-3-pro-preview` / `google/lyria-3-clip-preview` | — | аудио, не для кода |

**Итого рабочих free-моделей для кода: 5** — `flint-v1.0`, `inkling`, `nemotron-3.5-lightning`,
`nemotron-3-ultra-550b-a55b`, `laguna-s-2.1`. Тест 27.10: «стрип комментариев из .py» — 
nemotron-light и laguna-s прошли, nemotron-ultra дополнительно показал off-by-one в подсчёте
строк (не критично). Если flint падает дважды подряд → `inkling` → затем одна из nemotron/laguna.

## Минимальный вызов

Инструмент `workflow` принимает `script`, `meta` (обязательно: `name`, `description`), опционально
`args` и `run_in_background`. Скрипт — тело на **чистом JavaScript**: без TypeScript, без
`import`/`export`, top-level `await` разрешён, в конце обязан быть `return <JSON-значение>`.

## Хуки скрипта

- `agent(prompt, opts?)` — запускает одного субагента до конца. Без `opts.schema` возвращает
  финальный текст; с `opts.schema` (JSON Schema — **только** `type/properties/required/
  additionalProperties/items/enum/const/oneOf`) — проверенный объект. Падение ребёнка → `null`
  (фильтруй `.filter(Boolean)`).
- `opts`: `{ provider, model, label, phase, schema }` — `provider`/`model` это независимые
  переопределения LLM-цели (вот здесь и указывается бесплатная модель).
- `pipeline(items, ...stages)` — стадии **без барьера**; стадия получает `(prev, item, index)`;
  брошенное исключение роняет только этот `item` в `null`.
- `parallel(thunks)` — барьер, ждёт **все**; брошенное исключение → `null`.
- `phase(title)`, `log(message)`, `args` — прогресс и вход инструмента.
- В скрипте **нет** файловой системы, сети, таймеров и Node API — всю работу делают агенты.

## Шаблон для задач в этом репозитории

```js
const brief = `…8 обязательных частей брифа (см. AGENTS.md §0.2)…`;
const r = await agent(brief, {
    provider: "openrouter",
    model: "recursive/flint-v1.0:free",
    label: "короткое-имя-задачи"
});
return r ? String(r).slice(0, 3000) : "AGENT FAILED (null)";
```

## Правила

1. **Бриф самодостаточен** — субагент стартует с чистым контекстом: цель, входные пути, файлы
   во владении, запрещённые файлы, определение готовности, команда самопроверки, формат
   отчёта, дедлайн/бюджет итераций (AGENTS.md §0.2). Три файла во владении у двух агентов —
   запрещены (§0.4).
2. **flint маленькая** — бриф давать максимально конкретно (почти псевдокод, готовые команды),
   самопроверку делать обязательной (`javac`, чекеры репозитория), результат принимает главный
   агент по чек-листу §0.3. Два провала подряд → fallback на `inkling:free`, затем обычный
   `subagent` (платный) — с явным указанием причины.
3. **Возвращай короткие результаты** (`String(r).slice(0, 3000)`) — не раздувай контекст
   главного агента.
4. `run_in_background: true` — когда синхронный ответ не нужен; иначе workflow ждёт завершения.
5. **Секреты (токены, ключи) в prompt не передавать** — субагент наследует окружение машины.
6. Машинные особенности (Windows, PowerShell 5.1, запуск `.ps1` заблокирован, headless,
   `dataset/out*` не трогать) — включать в бриф прямо, субагент не читает корневой AGENTS.md
   сам по себе… читает его при первом обращении к файлам, но полагаться на это нельзя.

## Когда workflow НЕ нужен

- Разовые команды (pwsh, чекеры, javac) — главный агент делает сам (§0.1 MAY).
- Многочасовое обучение — отдельный бриф, см. `train/AGENTS.md`.
- Задача, которую главный агент закрывает за одну команду, — оркестрация дороже результата.
