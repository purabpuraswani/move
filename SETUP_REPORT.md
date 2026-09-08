# MoveWell AI — local setup report

Written 2026-08-26. Covers the inspection, the one blocking defect found and
fixed, every command run, and exactly what you need to provide.

---

## The constraint, stated up front

My shell is not your PC. It is an isolated Ubuntu 22.04 VM with your project
folder mounted, and I confirmed it has no PowerShell and that both the npm
registry and PyPI return HTTP 403 from it. There is no tool in this session that
executes commands on the Windows host.

So I could not run `npm install`, create your virtual environment, run
`pip install`, or start uvicorn and Vite on your machine. Attempting it would
also have been destructive rather than merely futile: your `node_modules`
contains `@rolldown/binding-win32-x64-msvc` and `lightningcss-win32-x64-msvc`,
which are Windows-only native binaries. Installing Linux packages into that
mounted folder would have overwritten them and broken your tree.

What I did instead: inspected everything, found and fixed a defect that would
have stopped the backend from starting on Atlas, and wrote `setup.ps1` to do the
Windows-side work with real diagnostics. That script is the deliverable.

---

## Run this

```
cd C:\Users\PURAB\Downloads\Projects\MoveWell-AI
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

`-ExecutionPolicy Bypass` applies to that one process only and changes nothing
about your machine's configuration — it is the safe form of the workaround you
mentioned. Separately, the script calls `npm.cmd` rather than `npm` throughout,
because bare `npm` resolves to `npm.ps1`, which is what a restrictive policy
actually refuses to load. That avoids the problem rather than relaxing a setting.

Add `-Launch` to start both servers and probe them once the checks pass. Add
`-SkipTests` to skip the suites, though they are the strongest signal the install
worked.

The script never writes a real credential and never prints the value of one.

---

## What you need to provide

**One required change.** Your `backend/.env` currently points at
`mongodb://localhost:27017`. For Atlas, replace that one line with your
connection string from Atlas > Connect > Drivers:

```
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
```

URL-encode any special characters in the password — an unencoded `@`, `:`, `/`
or `#` will produce an authentication failure that looks like a wrong password.
Two things in the Atlas console also matter, and neither is in your repo: the
database user needs `readWrite` on the `movewell` database, and your current IP
has to be in Network Access, which starts closed. A missing IP entry presents as
a connection timeout, and the script says so explicitly if it hits one.

I did not touch `backend/.env`. That edit is yours.

**Already set, but rotate it.** `JWT_SECRET` is present at 64 characters, over
the 32 minimum. It still needs rotating, because `backend/.env` remains in your
git history at commits `a3f6044` and `6907387` — untracking a file does not
unpublish it. Generate a replacement with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`. Rotating it
invalidates existing tokens, which in development means signing in again.

**Optional.** `OPENROUTER_API_KEY` enables report reading and AI guidance. Leave
it empty and both features report themselves unavailable and offer manual entry;
they never invent values. Everything else works without it.

**Nothing for the frontend.** No `.env` at the project root, and none needed.
The services fall back to `http://localhost:8000`, and the backend's CORS
default is `http://localhost:5173,http://127.0.0.1:5173`, so the defaults align
with Vite's default port. `VITE_API_URL` is the only build-time variable, and
only matters if you move the API off port 8000.

---

## Issues found

**1. Atlas connection strings would have crashed the backend at startup.
Severity: blocking. Fixed.**

`requirements.txt` pinned `pymongo==4.10.1` with no `dnspython`. pymongo needs
dnspython to resolve the SRV records in a `mongodb+srv://` URI, and raises
`ConfigurationError` without it. Because `database.py` constructs `MongoClient`
at module import time and `main.py` imports it, this would not have surfaced as
a failed query — uvicorn would have refused to start at all, with a message
about dnspython that gives no hint it came from your choice of Atlas over local.

Fixed by changing the pin to `pymongo[srv]==4.10.1`, with a comment explaining
why. This is the only change I made to your project code. It is inert for local
MongoDB, so it costs nothing and makes the two configurations interchangeable,
which is the entire point of having a single `MONGODB_URI`.

**2. `node_modules\.bin` is not visible from here. Severity: possible. Handled.**

All 12 declared dependencies are installed and Windows-native, but the mount
shows no `.bin` directory and no `.package-lock.json`, both of which npm
normally creates. This may be an artifact of how the folder is mounted rather
than a real gap. If it is real, `npm run dev` fails with "vite is not
recognized". Either way `setup.ps1` runs `npm.cmd install`, which is idempotent
and recreates `.bin`, then checks for `node_modules\.bin\vite.cmd` specifically
and tells you to delete `node_modules` and reinstall if it is still absent.

**3. Duplicate legacy keys in `backend/.env`. Severity: cosmetic.**

It carries `MONGO_URL` and `MONGO_DB` alongside `MONGODB_URI` and
`MONGODB_DB_NAME`, all four set. `config.py` prefers the newer names, so
behaviour is correct, but once you paste the Atlas URI you will have a file where
one Mongo setting says Atlas and another still says localhost. That is a trap for
whoever reads it next. Delete the `MONGO_URL` and `MONGO_DB` lines after the
switch.

**4. A bug in my own preflight script. Fixed before shipping.**

The first draft imported pymongo's exception classes inside the `try` block that
used them, so on a machine without pymongo the `except ConfigurationError`
clause raised `NameError` and buried the real problem. Found by running it here,
where pymongo genuinely is absent. Restructured so the import failure reports
itself plainly.

**5. Carried over from before, still outstanding. Severity: security.**

`backend/.env` is staged as deleted and gitignored but remains in `HEAD`'s tree,
so rotate `JWT_SECRET` as above. `backend/__pycache__/*.pyc` and
`backend/routes/__pycache__/*.pyc` are still tracked despite being ignored:
`git rm -r --cached backend/__pycache__ backend/routes/__pycache__`. And
`backend/.env.backup-before-claude` is still sitting there; this sandbox cannot
delete files, so removing it is yours.

**Two things that looked like issues and are not.** `backend/uploads` does not
exist, but `reports/storage.py` creates it with `makedirs(..., exist_ok=True)` on
first write, so nothing is needed. And `.gitignore` already covers `.venv/`,
`venv/`, `backend/uploads/`, `.env` and `__pycache__/`, so the venv the script
creates and any uploaded medical document are already un-committable.

**One thing I cannot check.** Your Python version. The pins were chosen against
3.11/3.12. On 3.13 or newer, `pydantic==2.10.4` or `bcrypt==4.2.1` may have no
matching wheel and pip will try to build from source. The script prints your
version, warns if it is 3.13+, and tells you to install 3.12 if a build fails.

---

## Every command run

All in the Linux VM. Inspection and verification only, except the two edits
noted.

**Inspecting the tree.** `ls -a`, `ls -a backend`, `find -name .venv` (none),
`du -sh node_modules` (416M, 171 entries), a presence check for all 12
dependencies (all found), `ls node_modules/.bin` (absent), `find node_modules
-maxdepth 1 -name ".*"` (nothing), `node -e` on `vite/package.json` (8.2.2,
depends on rolldown not rollup), `ls node_modules/@rolldown/`
(`binding-win32-x64-msvc`), `cat package.json`.

**Environment.** `uname -srm` and `/etc/os-release` (Ubuntu 22.04.5, Linux
6.8.0), `node -v` (v22.23.2), `npm -v` (10.9.8), `python3 -V` (3.10.12),
`command -v pwsh powershell` (neither). `npm view vite version` returned
`403 Forbidden`. `pip download fastapi` returned
`ProxyError ... Tunnel connection failed: 403 Forbidden`.

**Configuration.** `cat backend/.env.example`, `cat backend/config.py`,
`cat backend/database.py`, `cat vite.config.js`, `cat .gitignore`, a grep for
`VITE_API_URL` across `src/services/`, and a keys-only dump of `backend/.env`
that printed names and value lengths and never a value.

**Finding the defect.** `grep -rn "dnspython\|srv" requirements.txt` — not
declared.

**The two edits.** `requirements.txt`, `pymongo==4.10.1` to
`pymongo[srv]==4.10.1` with an explanatory comment. Then `setup.ps1`, created.
Line endings checked after each: `requirements.txt` still LF with 0 CR,
`setup.ps1` converted to CRLF via `sed`, which is the right convention for a
Windows-only file and is a new untracked file so it adds no diff noise.

**Validating the script without PowerShell.** Confirmed pure ASCII with
`grep '[^ -~\t]'`, so PowerShell 5.1 cannot mis-decode it. Extracted the
embedded Python preflight with `awk` and compiled it with `python3 -m py_compile`
(clean). Checked the here-string delimiters balance (1 open, 1 close). Then ran
the extracted preflight against a fake Atlas URI carrying a fake password, three
times across the fix: it correctly reported the missing dnspython and pymongo,
and `grep -c` for the password in its output returned **0** both before and
after. Also ran it with no `MONGODB_URI` to confirm the config error path prints
the actionable message rather than a traceback.

**Change scope.** `git status --short`, `git diff --ignore-cr-at-eol --
backend/requirements.txt`, and `git diff --ignore-cr-at-eol --numstat | wc -l` —
still 14 files with real content changes, unchanged from before, since
`requirements.txt` was already among them. `setup.ps1` shows as untracked.

**Regression sweep, all passing.**

```
backend: python3 -m unittest discover -s tests -t .   Ran 200 tests, OK
frontend: npm test                                    104 pass, 0 fail
verify_backend.py         28/28      verify_agents.py     39/39
verify_flow.py            20/20      verify_security.py   40/40
verify_assessments.py     32/32      verify_frontend.mjs  17/17
verify_reports.py         59/59
```

`npm test` runs without `node_modules` because the pose engine imports
TensorFlow dynamically inside a function, so the measurement modules have no
third-party imports at load time.

One process note: my first sweep reported four harnesses as `ERROR`. That was my
`grep` pattern not matching their summary wording, not a real failure. I checked
the raw output rather than trusting the wrapper, and all four were passing.

---

## What is still unverified

Everything that requires executing on Windows. No `npm run build` or
`npm run lint` has run, so **no React component has been compiled or rendered**
and no JSX has been through a real parser. The server has never started, no HTTP
request has been served, and nothing has touched a real MongoDB. `setup.ps1`
closes all of that in one run: it installs, connects to Atlas for real, imports
the FastAPI app and counts its routes, runs both suites, and with `-Launch`
probes `http://localhost:8000/` and `http://localhost:5173/`.

Expect first-run integration problems that no amount of stubbing here could
predict. Paste the script's output and I'll work through whatever it reports.

---

## Manual equivalent

If you would rather not run the script:

```
cd C:\Users\PURAB\Downloads\Projects\MoveWell-AI
npm.cmd install

cd backend
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

REM edit backend\.env: set MONGODB_URI to your Atlas mongodb+srv:// string

.venv\Scripts\python.exe -c "import config, database; database.client.admin.command('ping'); print('MongoDB OK')"
.venv\Scripts\python.exe -m unittest discover -s tests -t .
.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Then in a second terminal, from the project root, `npm.cmd run dev` and open
http://localhost:5173. API docs are at http://localhost:8000/docs.
