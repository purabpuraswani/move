# MoveWell AI

A web application that measures how well someone moves using an ordinary
webcam, reads the values out of a medical report they upload, and combines the
two into written wellness guidance.

Pose estimation runs entirely in the browser. Video frames are never uploaded,
never stored and never sent to a server — only the numbers derived from them
are. There is no custom machine-learning model in this project and none is
trained: movement is measured by explicit geometry over the keypoints that
Google's MoveNet returns, and scored by rules that live in readable source
files rather than in weights.

## Scope, stated plainly

This is not a medical device and not a diagnostic tool. It does not identify
conditions, does not interpret a medical report on the user's behalf, and does
not recommend treatment, medication or dosage. The AI agents are constrained to
general wellness guidance and to suggesting which kind of qualified
professional a person might choose to see. Every number that reaches a user is
either something measured on their own device or something they confirmed
themselves from their own document.

The assessment thresholds in `src/assessment/config/protocol.js` are
implementation parameters, chosen so that detection behaves sensibly with a
consumer webcam. They are not clinical norms or published reference values and
are never presented as such.

## How it works

The pipeline is deliberately one-directional, so that no later stage can invent
something an earlier stage did not measure:

```
pose engine  ->  test-specific measurement  ->  raw results
             ->  interpretation and scoring  ->  AI guidance
```

**Three movement assessments**, each with a defined camera view and a defined
measurand:

- **Shoulder** — bilateral active shoulder abduction, front-facing camera,
  three repetitions. Measures arm elevation angle and left/right symmetry.
- **FTSST** — five times sit-to-stand, side-facing camera. Measures the time to
  complete five repetitions.
- **Balance** — eyes-open single-leg stance, front-facing camera. Measures hold
  duration.

A test that cannot be measured reliably is recorded as `invalid` with its
reasons, rather than being scored anyway. Frame quality, pose confidence,
frame rate and trunk compensation are all checked, and a session records the
`protocol_version` that produced it so a stored result is always interpretable
against the parameters in force at the time.

**Medical report reading.** An uploaded PDF or photograph is transcribed by a
vision-capable model into *candidate* values. Nothing is stored as fact until
the user confirms each field individually, and the guidance agents read only
confirmed values. If no AI provider is configured, the report is left exactly
as uploaded and manual entry is offered — the pipeline works without an AI key
and never fabricates a value to fill a gap.

**AI guidance.** Two agents run over the confirmed data: a wellness guide and a
care navigator. Both are forced to answer through a tool schema rather than in
prose, so nothing reaches a user without having passed validation, and both
refuse to run when there is no assessment data rather than producing something
generic.

## Stack

React 19 and Vite on the front end, with TensorFlow.js and MoveNet for pose
detection. FastAPI and MongoDB on the back end, with bcrypt password hashing
and JWT sessions. The AI provider is OpenRouter, reached over its
OpenAI-compatible chat-completions API using `urllib` from the Python standard
library — there is no vendor SDK, which is why swapping providers touched three
files and added no dependency.

## Getting started

You will need Node 20 or newer, Python 3.10 or newer, and a MongoDB database
(local or Atlas).

```bash
# Front end
npm install

# Back end
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # .venv\Scripts\pip.exe on Windows
```

Copy `backend/.env.example` to `backend/.env` and fill it in. The file is
gitignored and must never be committed. At minimum:

| Variable | Purpose |
| --- | --- |
| `MONGODB_URI` | connection string; `mongodb://localhost:27017` or an Atlas `mongodb+srv://` URI |
| `MONGODB_DB_NAME` | database name |
| `JWT_SECRET` | signing secret for session tokens; generate a long random value |
| `OPENROUTER_API_KEY` | optional. Without it the app runs and the AI features report themselves unavailable |
| `OPENROUTER_MODEL` | optional. Defaults to a model that supports both tool calling and image input |

Then run the two servers in separate terminals:

```bash
cd backend && python -m uvicorn main:app --reload --port 8000
npm run dev
```

The app is at http://localhost:5173 and the generated API documentation at
http://localhost:8000/docs.

To check the AI configuration on its own, `python backend/check_openrouter.py`
prints what it found and sends one real request through the same code path the
agents use. It never prints the API key.

## Tests

```bash
npm test                                        # assessment logic, 104 tests
cd backend && python -m unittest discover -s tests -t .
```

The front-end tests cover the measurement and scoring logic and need no
`node_modules`, because the pose engine imports TensorFlow dynamically inside
a function.

## Layout

```
src/assessment/     pose engine, per-test measurement, scoring, protocol config
src/pages/          screens: assessment, reports, guidance, history, dashboard
backend/assessments/ session schema and validation
backend/reports/    upload handling, extraction, the candidate/confirmed boundary
backend/agents/     the guidance agents, their tool schemas and guardrails
backend/routes/     /api/auth, /api/profile, /api/assessments, /api/reports, /api/guidance
```

## Licence

No licence file is included, so all rights are reserved by default. Add one if
you intend others to reuse this.
