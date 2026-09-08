# MoveWell AI — implementation report

Written 2026-08-26 at the end of a single working session that implemented the
remaining project in six batches. Everything below is scoped to what is in the
working tree now, and every claim about testing says which command produced it.

---

## 1. Completion status

All six planned batches are implemented and verified to the extent this
environment allows. The application is feature-complete against the agreed
scope: a user can sign up, complete onboarding, perform three webcam movement
assessments, upload a medical report and confirm what was extracted from it, and
receive AI wellness guidance and care-navigation suggestions built only from data
they have confirmed.

It has **not been run**. No frontend build, no lint, no server start and no
database connection were possible here, for the reasons in item 16. The honest
summary is that the code is complete and heavily verified by execution of its own
logic, and that first-run integration on your machine is still ahead of you.

## 2. Batches completed

Batch 1 built the browser-side assessment core: the `/assessment` route, one
reusable MoveNet pose engine, and the three tests with their measurement logic.
Batch 2 added the assessment backend, the `assessments` collection, save/latest/
history endpoints, and the dashboard and history screens. Batch 3 built the
medical report pipeline end to end: upload, store, extract candidate values,
present for review, edit, confirm. Batch 4 added the three agents and their
orchestration. Batch 5 integrated profile, confirmed report and assessment data
into guidance, and reviewed authentication, ownership, secrets, configuration and
CORS. Batch 6 was the final quality pass that produced the checks in item 15 and
the five fixes in item 20.

## 3. Files created

Eighty new files. The backend gained `config.py`; `auth/` (`security.py`,
`jwt_handler.py`, `deps.py`); `assessments/` (`schema.py`, `store.py`);
`reports/` (`storage.py`, `schema.py`, `extraction.py`, `store.py`); `agents/`
(`base.py`, `context.py`, `guardrails.py`, `llm.py`, `navigation.py`,
`orchestrator.py`, `outputs.py`, `plan.py`, `registry.py`, `sources.py`,
`store.py`, `wellness.py`); three route modules (`assessments.py`, `reports.py`,
`guidance.py`); `tests/` with six test modules; and `.env.example`.

The frontend gained the whole `src/assessment/` tree — `pose/poseEngine.js` and
`pose/skeleton.js`, `config/protocol.js`, `utils/` (`geometry.js`,
`keypoints.js`, `smoothing.js`, `peaks.js`, `validation.js`, `results.js`,
`labels.js`), `tests/{shoulder,ftsst,balance}/*Logic.js`, `hooks/usePoseEngine.js`
and `hooks/useTestRunner.js`, eight components, `fixtures/syntheticPoses.js` and
six test files — plus `components/RequireAuth.jsx`, the pages
`AssessmentPage.jsx`, `HistoryPage.jsx`, `ReportsPage.jsx`,
`ReportReviewPage.jsx`, `GuidancePage.jsx` with their stylesheets, and the
services `assessments.js`, `reports.js`, `guidance.js`.

Backend Python totals 9,758 lines; frontend JavaScript and JSX totals 12,770.

## 4. Files modified

Fourteen tracked files have real content changes: `.gitignore`,
`backend/database.py`, `backend/main.py`, `backend/requirements.txt`,
`backend/routes/auth.py`, `backend/routes/profile.py`, `package.json`,
`src/App.jsx`, `src/services/auth.js`, `src/services/profile.js`,
`src/pages/Dashboard.jsx`, `src/pages/Dashboard.css`,
`src/pages/LoginPage.jsx`, `src/pages/OnboardingPage.jsx`.

A further eighteen files show as modified in `git status` but differ **only by
carriage returns at end of line**: `README.md`, `backend/models.py`,
`eslint.config.js`, `index.html`, `package-lock.json`, `public/icons.svg`,
`src/assets/vite.svg`, `src/components/Navbar.{css,jsx}`, `src/index.css`,
`src/main.jsx`, `src/pages/LandingPage.{css,jsx}`, `src/pages/LoginPage.css`,
`src/pages/OnboardingPage.css`, `src/pages/SignupPage.{css,jsx}`,
`vite.config.js`. That is the pre-existing line-ending noise in this repository,
not something this session introduced. You can confirm the split yourself:

```
git diff --ignore-cr-at-eol --numstat     # the 14 with real changes
git diff --name-only                      # all 32
```

`src/App.jsx` and `src/pages/LoginPage.jsx` are CRLF in `HEAD` and were written
back as CRLF, so their diffs show only the lines that actually changed. No file
was reformatted wholesale.

## 5. Dependencies added

**None, in either half of the project.** `backend/requirements.txt` was filled in
during the foundation work and lists exactly what the backend imports: fastapi,
uvicorn, pydantic[email], python-multipart, pymongo, python-dotenv, bcrypt,
PyJWT. Batches 2 through 6 added no package, which is a design consequence rather
than an omission — pose estimation runs in the browser, so no Python vision or
machine-learning library is involved, and the AI provider is called over HTTPS
with `urllib.request` from the standard library rather than through a vendor SDK.
The frontend's `package.json` already declared `@tensorflow/tfjs`,
`@tensorflow/tfjs-backend-webgl` and `@tensorflow-models/pose-detection`; a
`test` script was added for the assessment unit tests.

## 6. Routes and endpoints

Twenty-four API endpoints across five routers, plus a root liveness route:

```
POST   /api/auth/signup                     POST   /api/reports
POST   /api/auth/signin                     GET    /api/reports
GET    /api/auth/me                         GET    /api/reports/confirmed
                                            GET    /api/reports/extraction-status
POST   /api/profile/complete                GET    /api/reports/field-categories
GET    /api/profile/summary                 GET    /api/reports/{id}
                                            POST   /api/reports/{id}/extract
POST   /api/assessments                     PUT    /api/reports/{id}/fields
GET    /api/assessments                     POST   /api/reports/{id}/confirm
GET    /api/assessments/latest              POST   /api/reports/{id}/reopen
GET    /api/assessments/{id}                DELETE /api/reports/{id}

GET    /api/guidance/agents                 GET    /api/guidance/status
GET    /api/guidance/latest                 POST   /api/guidance/run
```

Frontend routes: `/`, `/signup`, `/login` are open; `/dashboard`, `/onboarding`,
`/assessment`, `/history`, `/reports`, `/reports/:reportId` and `/guidance` are
wrapped in `RequireAuth`; `*` falls back to the landing page.

## 7. Assessment architecture

The pipeline is one direction with no shortcuts: RGB webcam → pretrained MoveNet
→ body keypoints → application geometry, timing and state logic → raw
measurements → interpretation. Each arrow is a module boundary.

`pose/poseEngine.js` owns the camera and the model and nothing else. It knows
about frames, keypoints, frame rate and teardown; it knows nothing about
shoulders or chairs. Each test's logic lives in its own module
(`tests/shoulder/shoulderLogic.js`, `tests/ftsst/ftsstLogic.js`,
`tests/balance/balanceLogic.js`) and consumes keypoints, producing measurements
and a list of reasons a recording did not qualify. Shared arithmetic sits in
`utils/` — angles in `geometry.js`, median filtering in `smoothing.js`, peak
detection in `peaks.js`, confidence and framing gates in `validation.js`. The
`useTestRunner` hook sequences a test; `usePoseEngine` binds the engine to a
component's lifetime. `config/protocol.js` holds every threshold in one place,
each named as an implementation parameter.

No custom model is trained, fine-tuned or collected for. MoveNet is used as a
pretrained keypoint detector, its own smoothing switched off so that the numbers
this application reports come from arithmetic that is written down here.

## 8. How the three assessments work

**Bilateral active shoulder abduction**, front-facing camera. Both arms are
raised out to the side. The logic tracks the angle of each upper arm relative to
the torso across the movement and reports the highest sustained elevation per
side and the difference between them.

**Five times sit-to-stand**, side-facing camera. The logic follows hip and knee
vertical position, segments the trace into repetitions by peak detection, and
reports elapsed time and the number of repetitions detected. Fewer than five
detected repetitions makes the attempt invalid rather than producing a time.

**Eyes-open single-leg stance**, front-facing camera. The logic detects when one
foot leaves the floor and reports how long the position was held before the
stance broke, capped by the protocol's ceiling.

All three are subject to the same gates: mean keypoint confidence, whether the
whole body stayed in frame, and dropout length. Failing a gate makes the result
`invalid` with reasons attached — never a lower number.

What these are not, stated in the interface as well as here: they are not
clinical range-of-motion or strength measurements, they are not equivalent to a
clinician-administered test, and they say nothing about bone, joint, internal or
mental health.

## 9. Database collections

Six collections in the `movewell` database. `users` holds name, email and
`password_hash` and nothing else about credentials. `health_profiles` and
`health_documents` carry onboarding answers and any file attached there.
`assessments` stores one document per session: `user_id`, `session_id`,
`protocol_version`, timestamps, a `summary`, and a `tests` sub-document keyed by
test id holding `status`, `measurements`, `quality`, `invalid_reasons`,
`attempts` and optional `setup`. `medical_reports` holds `user_id`, title, date,
facility, a `file` record (storage key, size, extension), a `status`, and a
`fields` list where each field carries its label, value, unit, any range the
laboratory printed, a category, and its provenance. `guidance_runs` stores each
orchestration run with its per-agent outputs, states and `context_signature`.

Stored documents are snake_case; every route serialises explicitly to camelCase
rather than leaking internal shapes.

## 10. Medical report pipeline

Upload → store → extract candidates → structured output → user review → edit →
confirm → confirmed store.

`reports/storage.py` writes the file under a server-generated key of the form
`{user_id}/{uuid4hex}{ext}`, so the uploaded filename never shapes a path. Size
is enforced while writing, with the partial file removed on rejection; empty
files and extensions outside `.pdf/.png/.jpg/.jpeg` are refused. The backend
talks to it through an abstract `ReportStorage`, so a cloud backend can be added
without touching routes; an unknown `REPORT_STORAGE_BACKEND` raises rather than
silently falling back to local disk.

`reports/extraction.py` sends the document to the AI provider as a base64
`document` or `image` block with a forced tool call, so what comes back is
structured rather than prose. Every returned field is stored as a **candidate**.
With no API key configured, `ExtractionUnavailable` leaves the report exactly as
uploaded and offers manual entry — deliberately distinct from
`ExtractionFailed`, which marks the report failed. Nothing is ever invented.

## 11. The trust boundary

Extraction produces candidates. A candidate becomes trusted only when the user
reviews it, corrects it if needed, and explicitly confirms — `POST
/api/reports/{id}/confirm`. Confirmation carries no values with it: the browser
says "confirm", and the server confirms the values it already holds, so the
client cannot decide what was confirmed. Editing after confirmation requires an
explicit reopen, and `reopen_report` refuses a report that was never confirmed.

Downstream, `agents/sources.py` reads **only** confirmed reports. An unconfirmed
report is not silently omitted, which would be its own kind of dishonesty:
the agent is told how many unconfirmed reports exist, that their values are
withheld, and that it must not speculate about them. The interface distinguishes
the two states plainly ("Needs your check" versus "Confirmed by you").

## 12. Agent architecture

Three agents behind one orchestration. The **report extraction agent** turns an
uploaded document into candidate fields. The **wellness guidance agent** produces
general, non-diagnostic guidance. The **care navigation agent** suggests
categories of support and runs second, on the wellness output.

The module split is deliberate: `context.py`, `guardrails.py`, `outputs.py`,
`plan.py`, `registry.py` and `base.py` import **standard library only** and are
pure; `sources.py`, `store.py`, `llm.py` and `orchestrator.py` do the I/O. That
is what makes the agents testable without a provider.

`context.py` builds a small structured digest: profile values, per-test movement
observations with their status, and confirmed report fields with the ranges the
laboratory printed. Missing data is described as missing. `guardrails.py` rejects
output that diagnoses, names a disease as fact, prescribes treatment, or tells
the user they definitely have a condition; care navigation is held to cautious
phrasing. Runs end in exactly one of four distinguishable states — `ok`,
`withheld_by_safety_rules`, `failed`, `not_run` — so a refusal never looks like
a success and a missing key never looks like a refusal.

## 13. Frontend integration

`services/` wraps every endpoint, attaches the bearer token, and clears the
session on a 401. `AssessmentPage.jsx` runs the intro, safety and scope notice,
the three tests and the raw results view. `Dashboard.jsx` shows the latest
assessment and report state and now confirms the signed-in account against
`/api/auth/me` rather than trusting a copy in `localStorage`. `HistoryPage.jsx`
lists past sessions. `ReportsPage.jsx` and `ReportReviewPage.jsx` implement the
upload and the review-and-confirm screen. `GuidancePage.jsx` runs the agents and
renders their output with provenance, staleness and each possible failure state.
Every data-loading screen has loading, error and empty states.

## 14. Security and configuration

Passwords are bcrypt-hashed, capped at bcrypt's 72-byte limit with an explicit
refusal rather than silent truncation, and a stored value that is not a bcrypt
hash fails closed. Wrong password and unknown email return identical messages.
Tokens carry `sub`, `iat`, `exp` and nothing else — no name, no email — because a
JWT payload is readable by anyone holding it. `get_current_user` distinguishes
expired from invalid, and rejects a token whose account no longer exists.

Every endpoint except signup, signin and `/` resolves its caller from the token,
and **no endpoint anywhere accepts a user identifier from the client**. Ownership
is enforced in the query, not after the fetch, and asking for another user's
record returns the same 404 as asking for one that does not exist.

Configuration is environment-only. `MONGODB_URI` (Atlas `mongodb+srv://` works
unchanged), `JWT_SECRET` (required, minimum 32 characters), `JWT_EXPIRES_MINUTES`,
`CORS_ORIGINS`, the report storage and upload-limit settings, and the AI provider
settings. A missing or weak secret stops startup with a message that says how to
generate one. CORS is limited to the configured origins, never `*`, with
credentials disabled and methods and headers listed explicitly. `.env` is
ignored, `.env.example` holds placeholders only, and the sole build-time variable
the frontend reads is `VITE_API_URL`.

## 15. Tests and checks actually run

Every number here came from a command executed in this session.

```
cd backend && python3 -m unittest discover -s tests -t .   → Ran 200 tests, OK
npm test                                                    → 104 pass, 0 fail
outputs/verify_backend.py                                   → 28/28
outputs/verify_flow.py                                      → 20/20
outputs/verify_assessments.py                               → 32/32
outputs/verify_reports.py                                   → 59/59
outputs/verify_agents.py                                    → 39/39
outputs/verify_security.py                                  → 40/40
outputs/verify_frontend.mjs                                 → 17/17
```

That is 304 unit tests and 235 harness checks. The harnesses are not in the
repository; they live in my working folder and execute the project's **real**
modules against hand-written stubs for fastapi, pydantic, pymongo, bson and the
database, because those packages cannot be installed here. `bcrypt` and `PyJWT`
happen to be present, so password hashing and token signing are tested for real,
not imitated. `verify_frontend.mjs` runs the actual service and measurement
modules under Node with stubs for `fetch`, `localStorage` and the camera.

Also run: a dependency audit confirming every backend import is declared in
`requirements.txt` and every frontend package imported is declared in
`package.json`; a navigation audit confirming no link or `navigate()` call in
`src/` points at an undeclared route; and the git scope analysis in item 4.

## 16. What could not be tested

`npm install` fails with **HTTP 403** from the npm registry, so there is no
`node_modules`. Consequently `npm run build` and `npm run lint` never ran, **no
React component has ever been rendered or compiled**, and no JSX file has been
parsed by a real parser. Everything asserted about the pages and components is
from reading them, and item 15's frontend numbers cover plain JavaScript modules
only.

`pip install -r requirements.txt` fails with **HTTP 403** from PyPI, so fastapi,
uvicorn, pymongo and pydantic are absent, the server was never started, and no
HTTP request was ever served. There is no MongoDB here, so no query has run
against a real database and no index has been created.

No real call was made to the Anthropic API — every AI interaction was tested
through an injected transport. No webcam and no browser exist here, so MoveNet
has never actually run, and the measurement logic was verified against synthetic
keypoint sequences rather than a real recording of a real person.

The first time this application talks to a real database, a real browser and a
real model will be on your machine. Expect to find integration problems that no
amount of stubbing can predict.

## 17. Not implemented for want of credentials

Nothing was left out. Both AI-dependent features — report extraction and agent
guidance — are fully implemented and behave correctly with no key: they report
themselves unavailable, explain why, and offer the manual path. What is untested
is their behaviour against the real provider: prompt quality, whether the model
respects the tool schema in practice, and how often the guardrails fire on real
output. Only local file storage is implemented; the abstraction for a cloud
backend exists but no cloud backend was written, since there are no credentials
to write one against.

## 18. Known limitations

The measurements come from a single 2D camera. They are affected by where the
user stands, how the room is lit, what they wear and how the phone or laptop is
propped. Two sessions recorded differently are not strictly comparable, which is
why setup metadata is stored alongside the numbers. MoveNet SinglePose Lightning
is used, which assumes one person in frame and trades accuracy for speed.
Rotation out of the camera plane is invisible to it, so a shoulder angle is the
angle *as seen*, not the anatomical angle — the interface says so.

Only final measurements and minimal quality metadata are stored; full keypoint
sequences are not, so a stored result cannot be re-scored under a future
algorithm beyond what `protocol_version` and the recorded measurements allow.
There are no clinical norms anywhere in this codebase and nothing compares a user
against a population, because inventing thresholds would be worse than having
none. Guidance quality depends on a provider that has never been called.

## 19. Running it locally

```
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env                                 # then fill it in
uvicorn main:app --reload --port 8000

# Frontend, in a second terminal
npm install
npm run dev                                            # http://localhost:5173
```

`backend/.env` needs at minimum `MONGODB_URI` and a `JWT_SECRET` of 32+
characters — generate one with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`. Add
`OPENROUTER_API_KEY` to enable extraction and guidance; leave it empty and both
features will say so rather than fabricate. The webcam needs `localhost` or
HTTPS. To run the checks: `cd backend && python -m unittest discover -s tests -t .`
and `npm test`.

**Two git items need you, and one is time-sensitive.** `backend/.env` is staged
as deleted from the index and is now gitignored, but **it is still in `HEAD`'s
tree** (commits `a3f6044` and `6907387`), so the secret is in your history —
untracking does not unpublish it. Rotate any credential that file ever held, then
commit the staged deletion. Separately, `backend/__pycache__/*.pyc` and
`backend/routes/__pycache__/*.pyc` are still tracked despite being ignored:
`git rm -r --cached backend/__pycache__ backend/routes/__pycache__`. There is
also a leftover `backend/.env.backup-before-claude` you may want to delete; this
sandbox is not permitted to delete files, so it is still there.

## 20. Decisions made where the specification was ambiguous

**Configuration compatibility.** `config.py` accepts legacy `MONGO_URL` and
`MONGO_DB` names as a fallback so your teammate's existing `.env` keeps working
rather than breaking on pull.

**A contradictory measurement resolves to invalid.** `measuredResult` was
accepting `valid: true` alongside reasons the attempt was invalid. It now returns
an invalid result. Of the two ways to resolve the contradiction only this one
errs harmlessly: a real measurement withheld is a nuisance, a bad measurement
presented as real is precisely what this application must not do. It coerces
rather than throwing, because an exception there would discard an assessment the
user had already performed.

**The no-imagery promise is now enforced, not just kept.** `toStoredPayload`
forwarded each test's `measurements` verbatim, so a future change that hung a
keypoint series or a debug frame off a result would have quietly become an
upload. It now filters anything imagery-shaped — names like `keypoints` or
`debugFrames`, `data:` URIs, long runs of numbers — at the single point where
assessment data leaves the browser. Removal is silent, because refusing the whole
payload would lose a real assessment over data the user never wanted sent.

**A failure message that was not true.** The orchestrator reported "could not
reach the AI provider" for a case that also covers a provider that answered with
unusable prose. It now says the previous step did not get a usable response.

**Frontend route protection is a courtesy, not a boundary.** `RequireAuth` checks
only that a token is *present*, because validity is the server's to judge. The
comment in that file says so, so nobody later mistakes it for the security
boundary — every protected endpoint identifies its user from the token
regardless.

**Credentialed cross-origin requests are off.** Authentication is a bearer token
in a header, not a cookie, so there is nothing for a browser to attach on another
site's behalf; enabling credentials would widen what browsers will do for no
gain.

**Signing in continues where the visitor was going**, via `location.state.from`,
restricted to in-app paths so a crafted link cannot bounce anyone off-site.
