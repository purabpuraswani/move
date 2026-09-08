# MoveWell AI — OpenRouter migration

Written 2026-08-26. The AI provider is now OpenRouter. Nothing in the
application reads `ANTHROPIC_API_KEY` any more, no new Python package is
needed, and every prompt, route, schema, guardrail and screen is unchanged.

**One thing to do first, before anything else in this document.** Your
OpenRouter key was pasted into our chat in plain text. Treat it as public and
replace it: openrouter.ai → Keys → delete that key, create a new one. It is not
written into any file in this repository — I checked the whole tree for
key-shaped text and found none — but a key that has appeared in a chat log is a
key that has left your control.

---

## What was wrong

`backend/.env` has no AI key of any kind. Not a wrong one, not an empty one —
the variable is absent. So `ai_provider_available()` returned false, and both
features correctly reported themselves unavailable. The code was working as
designed; it was pointed at a provider you do not have an account with.

The Anthropic integration turned out to be confined to three files, which is
why this was a provider swap rather than a rewrite. Everything else in the
project talks to those three through an interface that does not mention any
vendor.

| Where | What it did |
| --- | --- |
| `backend/config.py` | read `ANTHROPIC_API_KEY`, and `ai_provider_available()` returned whether it was set |
| `backend/agents/llm.py` | `POST /v1/messages` with `x-api-key` and `anthropic-version`; used by the wellness guide and the care navigator |
| `backend/reports/extraction.py` | the same API with a base64 document attached; used by the report reader |
| `setup.ps1`, two report files | told you to set `ANTHROPIC_API_KEY` |

The three features and the files behind them, unchanged except where noted:
the **report reader** is `backend/reports/extraction.py` (provider layer
replaced) behind `POST /api/reports/{id}/extract`; the **wellness guide** is
`backend/agents/wellness.py`; the **care navigator** is
`backend/agents/navigation.py`. The last two share `backend/agents/llm.py`
(provider layer replaced), are sequenced by `backend/agents/orchestrator.py`
and are exposed by `backend/routes/guidance.py`. Both agent files, the
orchestrator, the routes and the tool schemas in `backend/agents/outputs.py`
were not touched at all.

---

## Every file changed

Nine files. All of them were already untracked in git, so this migration adds
no diff to any tracked file — `git status` looks exactly as it did before.

**`backend/config.py`** — the AI block was replaced. `ANTHROPIC_API_KEY` is
gone as a source of configuration; `OPENROUTER_API_KEY` takes its place, and
`ai_provider_available()` now answers the same question about the new provider.
New settings: `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`,
`OPENROUTER_SITE_URL`, `OPENROUTER_APP_TITLE`, `OPENROUTER_PDF_ENGINE`,
`SUPPORTED_AI_PROVIDERS`. `AI_PROVIDER`, `AI_REQUEST_TIMEOUT_SECONDS`,
`AI_MAX_OUTPUT_TOKENS`, `AI_AGENT_MODEL` and `AI_AGENT_MAX_OUTPUT_TOKENS` kept
their names and meanings. One new line reads the old variable and keeps only a
boolean: `LEGACY_ANTHROPIC_KEY_PRESENT = bool(_first_env("ANTHROPIC_API_KEY"))`.
The value is never stored, logged or returned — it exists so that somebody who
still has the old variable set gets told it is being ignored, instead of
reading "no key is configured" with a key sitting in front of them.

**`backend/agents/llm.py`** — `AnthropicModel` became `AgentModel` with
`name = "openrouter"`. Same class shape, same constructor arguments, same
`call(system, user_text, tool, extra_user_text=None)` signature, same injected
transport. What changed is the wire format: one `POST` to
`{OPENROUTER_BASE_URL}/chat/completions`, `Authorization: Bearer` instead of
`x-api-key`, the system prompt as a `system` message instead of a top-level
field, the tool as `{"type": "function", "function": {...}}` instead of
`{"name", "input_schema"}`, and the result read from
`choices[0].message.tool_calls[0].function.arguments` instead of from a
`tool_use` content block. The arguments arrive as a JSON string, which is
parsed; an object is also accepted, because some models behind OpenRouter send
one. `AgentUnavailable` and `AgentFailed` still mean what they meant, so the
503-versus-502 distinction in the routes still holds.

**`backend/reports/extraction.py`** — `AnthropicProvider` became
`OpenRouterProvider`, same shape, same `extract(file_bytes, extension)`. A PDF
now travels as `{"type": "file", "file": {"filename", "file_data"}}` with a
`data:application/pdf;base64,` URL; a photograph or scan travels as
`{"type": "image_url", ...}`. `SYSTEM_PROMPT`, `USER_PROMPT`, the extraction
tool schema, the field validation, the candidate/confirmed trust boundary and
`extract_candidates` are all untouched.

**`backend/.env.example`** — documents the new variables, with three model
suggestions and a note that a model needs both tool calling and image input.
Contains no key.

**`setup.ps1`** — checks for `OPENROUTER_API_KEY`, prints the model in use, and
if it finds a leftover `ANTHROPIC_API_KEY` says plainly that it is no longer
read.

**`backend/tests/test_report_schema.py`** — two lines: a fixture said the
provider was `"anthropic"`, and one assertion checked it. A string round-trip,
no behaviour.

**`IMPLEMENTATION_REPORT.md`** and **`SETUP_REPORT.md`** — one line each, so
the project's own documentation stops telling you to set a variable the code no
longer reads.

**`backend/check_openrouter.py`** — new, and the answer to "how do I know it
works". Described at the end of this document. It is a diagnostic; nothing
imports it and the application does not run it.

### A defect found while verifying, and fixed

Both modules included the provider's own error text in the message they raise,
and those messages end up in an HTTP response body that reaches the browser.
OpenRouter is a proxy, and several of the providers behind it quote the
offending key back in an authentication error. A comment in the code asserted
that the key "is never part of it"; nothing enforced that. Now something does:
text shaped like an API key is masked to `sk-***` before the message is built,
in the one function both modules funnel provider text through. The rest of the
provider's message survives, because that is the part that makes the error
useful. This was pre-existing behaviour rather than something the migration
introduced, but the migration made it likelier to matter.

---

## What to add to `backend/.env`

One line is enough. Everything else has a working default in `config.py`.

```
OPENROUTER_API_KEY=sk-or-v1-your-new-rotated-key
```

Optionally, to be explicit about the rest — these are the defaults, so setting
them changes nothing, but they are the knobs that exist:

```
AI_PROVIDER=auto
OPENROUTER_MODEL=google/gemini-2.5-flash
AI_REQUEST_TIMEOUT_SECONDS=90
AI_MAX_OUTPUT_TOKENS=4096
AI_AGENT_MODEL=
AI_AGENT_MAX_OUTPUT_TOKENS=3000
OPENROUTER_SITE_URL=http://localhost:5173
OPENROUTER_APP_TITLE=MoveWell AI
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_PDF_ENGINE=
```

`google/gemini-2.5-flash` is the default because reading a photographed lab
report needs image input, writing structured guidance needs tool calling, and
it is inexpensive at both. `anthropic/claude-sonnet-4.5` is more accurate and
costs more; `openai/gpt-4o-mini` is cheaper and weaker on faint print. Change
`OPENROUTER_MODEL` and restart — no code change. `AI_AGENT_MODEL` overrides the
model for the two writing agents only; left empty it follows
`OPENROUTER_MODEL`.

Your OpenRouter account needs credit. Without it the API returns 402 and the
app says so in those words.

Two things about that file while you are in it. Delete the leftover `MONGO_URL`
and `MONGO_DB` lines — they still say localhost while `MONGODB_URI` now points
at Atlas, and although `config.py` prefers the newer names, a file that
contradicts itself is a trap for whoever reads it next. And `JWT_SECRET` still
needs rotating, because `backend/.env` remains in `HEAD`'s tree at commits
`a3f6044` and `6907387`; untracking a file does not unpublish it.

---

## Dependencies to install

None. Both call sites use `urllib.request` from the standard library, which is
why `backend/requirements.txt` is unchanged and why swapping providers needed
no `pip install`. Your virtual environment is already complete — I can see all
24 packages installed under Python 3.13.15, including `pydantic 2.10.4` and
`bcrypt 4.2.1`, which the earlier setup report warned might not have 3.13
wheels. They did.

If you want to confirm nothing is missing:

```
cd C:\Users\PURAB\Downloads\Projects\MoveWell-AI\backend
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## Starting it

Backend, in one terminal:

```
cd C:\Users\PURAB\Downloads\Projects\MoveWell-AI\backend
.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Frontend, in a second:

```
cd C:\Users\PURAB\Downloads\Projects\MoveWell-AI
npm.cmd run dev
```

`npm.cmd` rather than `npm`, because bare `npm` resolves to `npm.ps1` and a
restrictive execution policy refuses to load it. `node_modules\.bin\vite` now
exists, so this should start cleanly.

Then http://localhost:5173 for the app and http://localhost:8000/docs for the
API.

---

## Testing that the AI actually works

**Fastest, and it tells you the most.** With the backend stopped or running,
either is fine:

```
cd C:\Users\PURAB\Downloads\Projects\MoveWell-AI\backend
.venv\Scripts\python.exe check_openrouter.py
```

It prints the configuration it found — including whether the key is present and
how long it is, never the key itself — then what the app reports about its own
availability, then sends exactly one real request through the same code path
the wellness agent uses: same model selection, same forced tool call, same
parsing. On success it prints the model's reply and confirms that tool calling
works, the model name is valid and the key is accepted, which is everything all
three features depend on. On failure it prints the message a user would have
seen, and those messages name the setting to change. It costs a fraction of a
cent.

**Through the app**, once that passes. Sign in, and the report reader is on the
medical reports screen: upload a photo or PDF of a lab report and choose to
read it automatically. Values come back as *candidates* — nothing is stored as
fact until you confirm each one, which is deliberate and unchanged. The
wellness guide and care navigator are on the guidance screen: record at least
one movement assessment first, since with nothing recorded the agents correctly
decline to run rather than inventing something to say.

**Through the API**, if you prefer curl. Both status endpoints need a token:

```
POST http://localhost:8000/api/auth/signin      -> take the token
GET  http://localhost:8000/api/guidance/status  -> Authorization: Bearer <token>
GET  http://localhost:8000/api/reports/extraction-status
POST http://localhost:8000/api/guidance/run     -> actually spends a request
```

**What failure looks like, so you can tell the cases apart.** A missing key
gives HTTP 503 and "not set up on this server", with the offer of manual entry
intact. A rejected key names `OPENROUTER_API_KEY`. An exhausted balance says
there is no credit left. A model name that does not exist names
`AI_AGENT_MODEL` or `OPENROUTER_MODEL` and points at openrouter.ai/models. A
model that cannot do tool calling says so and names the same variable. None of
those messages contain any part of your key.

---

## What I verified, and the one thing I could not

Everything below runs offline. The provider is exercised through the transport
seam both modules already had, so the request construction and the response
parsing execute for real and only the socket is replaced.

```
backend suite      python -m unittest discover -s tests -t .   200 tests, OK
frontend suite     npm test                                    104 pass, 0 fail

verify_openrouter_wire.py   40/40   verify_security.py     40/40
verify_reports.py           59/59   verify_assessments.py  32/32
verify_agents.py            39/39   verify_backend.py      28/28
verify_flow.py              20/20   verify_frontend.mjs    17/17
```

`verify_openrouter_wire.py` is new and exists because of the limitation in the
next paragraph. It pins the endpoint and the bearer header; that the key is
absent from the body, the URL, every other header, both status dictionaries and
all 32 error paths; that the tool is sent in OpenAI function shape with the
schema the agents declared and that the call is forced; that arguments parse as
a JSON string and as an object; that prose, truncated JSON, a length-limited
response, a 200 carrying an error object and a non-object body are each a
distinct failure naming its own fix; that 401, 402, 403, 404, 429 and 5xx are
each distinguishable; that an unreachable host and a timeout are reported
rather than raised raw; that a PDF and a photograph take their separate routes
and base64-decode back to the original bytes; that the PDF engine plugin is
sent only when configured and only for PDFs; and that with no key, or with
`AI_PROVIDER=none`, or with a provider this build cannot speak to, nothing is
sent at all.

**The limitation.** openrouter.ai is not reachable from my sandbox — outbound
requests to it are refused by a proxy, which you can see for yourself in
`check_openrouter.py`'s output if you run it here rather than on your machine.
So **no request in this project has ever been answered by the real API.** The
request and response shapes are built from the OpenAI-compatible specification
OpenRouter implements, and they are pinned by the harness above, but pinned
against my understanding rather than against the live service. The same applies
to the default model slug `google/gemini-2.5-flash`.

That risk is bounded and cheap to resolve. A wrong model name produces a 404
whose message names the variable to change, and changing it is one line in
`backend/.env` with no restart of anything but the backend. A wrong request
shape would produce a 400 carrying OpenRouter's own explanation, which the app
now passes through to you verbatim apart from anything key-shaped.
`check_openrouter.py` is the fastest way to find out, and if it prints
something unexpected, paste the output and I will work through it.
