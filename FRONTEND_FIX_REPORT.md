# MoveWell AI — frontend startup fix

Written 2026-08-26. Fixes the `npm run dev` failure:

```
[MISSING_EXPORT] "Pose" is not exported by "node_modules/@mediapipe/pose/pose.js".
 - Missing export in node_modules/@tensorflow-models/pose-detection/dist/pose-detection.esm.js at 755..759
```

Two files changed, no dependency touched, MoveNet untouched.

---

## A. Root cause

Three facts combine. Each was measured against your installed packages, not
inferred.

**1. `@mediapipe/pose@0.5.1675469404` advertises itself as an ES module and is
not one.** Its `package.json` sets both `"main"` and `"module"` to `pose.js`.
That file is a Closure-compiled global script containing no module syntax of any
kind — zero occurrences of `export`, `module.exports`, `exports.` and
`define.amd`. It publishes its API by walking a dotted path onto the global
object:

```javascript
function G(a,b){a=a.split(".");var c=ya;a[0]in c||...}
```

Loading the real file as an ES module in Node yields a namespace whose only key
is `default`, and `default.Pose` is undefined. So the named export `Pose` exists
in **no** module format.

**2. `@tensorflow-models/pose-detection@2.1.3` imports that name statically at
the top level.** The first statement of its ESM bundle is:

```javascript
import{Pose as t}from"@mediapipe/pose";
```

It is unconditional, so every bundler must resolve it even for applications that
never use MediaPipe. (The `755..759` in the error message are character offsets
inside that one minified line, not line numbers.) The symbol is used in exactly
one place in the whole library: `new pose.Pose(...)` in the constructor of
`BlazePoseMediaPipeDetector`, reachable only through
`createDetector(SupportedModels.BlazePose, { runtime: 'mediapipe' })`.

**3. Vite 8 optimizes dependencies with Rolldown, which treats a missing named
export as a hard error.** Earlier toolchains emitted a warning and let the
build through. Rolldown aborts, which is why this surfaces as a dev-server
startup failure rather than a runtime problem.

### Why the previously suggested fix would not have worked

`optimizeDeps: { exclude: ['@mediapipe/pose'] }` does not fix this, and you were
right not to apply it blind. Excluding a dependency from prebundling hands the
import to the browser instead of resolving it at build time. Because the export
does not exist in any module format, there is nothing for the browser's module
linker to bind either, so the same failure reappears as a runtime
`SyntaxError` about a missing export. I confirmed the underlying impossibility
directly: Node loading the real bundle reports
`SyntaxError: Named export 'Pose' not found`. Exclusion relocates the error, it
does not remove it.

Nothing needed downgrading, upgrading, replacing or uninstalling. The versions
you have are mutually compatible; the defect is a packaging bug in
`@mediapipe/pose` that a stricter bundler now exposes.

---

## B. Exact files changed

**1. `src/shims/mediapipe-pose.js` — new file.**

A small ES module that really does export `Pose`. The class throws a descriptive
error if it is ever constructed, since in this codebase that could only be a
mistake. The file's header comment records why it exists and how to opt back
into the real MediaPipe runtime.

**2. `vite.config.js` — 15 lines added, 0 removed.**

```javascript
import { fileURLToPath } from 'node:url'
...
  resolve: {
    alias: {
      '@mediapipe/pose': fileURLToPath(
        new URL('./src/shims/mediapipe-pose.js', import.meta.url)
      )
    }
  }
```

The existing `plugins` array — `react()` and
`babel({ presets: [reactCompilerPreset()] })` — is byte-for-byte unchanged, and
the file's original CRLF line endings were preserved so it adds no whole-file
diff noise.

**Nothing else.** No change to `package.json`, `package-lock.json`, any
`node_modules` content, any assessment file, any pose file, or any backend file.
`git diff --ignore-cr-at-eol --numstat` shows `vite.config.js` at `+15/-0`, and
`src/shims/` as a new untracked directory. Every other modified file in the tree
predates this task.

### Why an alias rather than `optimizeDeps`

`resolve.alias` is the one mechanism that covers all three places the specifier
gets resolved — dependency prebundling, dev-server module serving, and
`vite build` — with a single entry. I verified from your installed Vite 8.2.2
source that it genuinely reaches the optimizer, which is the non-obvious part:
the optimizer assembles its own plugin list and there is no `vite:alias` in it,
which looks fatal. But `vite:dep-pre-bundle`'s `resolveId` hook resolves through
`createBackCompatIdResolver` → `createIdResolver`, and that builds its plugin
container as:

```javascript
[alias({ entries: environment.config.resolve.alias }), ...oxcResolvePlugin({...})]
```

Alias first. So the redirect applies during prebundling, which is exactly where
your error occurs.

I also confirmed the alias cannot over-match. Vite's matcher is
`importee === pattern || importee.startsWith(pattern + '/')`, and there are zero
subpath imports of `@mediapipe/pose` anywhere in `node_modules` — the only
specifier that appears, in all six occurrences across the package, is the bare
one. So the alias shadows nothing legitimate, and it will not catch an unrelated
package whose name merely begins with the same characters.

---

## C. Why this is compatible with the existing MoveWell pose system

**The MoveNet path never touches the shim.** `src/assessment/pose/poseEngine.js`
dynamically imports `@tensorflow/tfjs`, `@tensorflow/tfjs-backend-webgl` and
`@tensorflow-models/pose-detection` inside `loadPoseDetector()`, then calls:

```javascript
poseDetection.createDetector(
  poseDetection.SupportedModels.MoveNet,
  { modelType: poseDetection.movenet.modelType.SINGLEPOSE_LIGHTNING,
    enableSmoothing: false }
)
```

I grepped all of `src/` for `@mediapipe`, `blazepose`, `BlazePose`,
`SupportedModels`, `movenet` and `MoveNet`. There is no MediaPipe or BlazePose
usage anywhere in the codebase — only the MoveNet call above, plus a doc comment
in `keypoints.js` and marketing copy in `LandingPage.jsx`. The shim therefore
sits on a code path the application cannot reach.

**The architecture is untouched.** Pose estimation still runs in the browser
with pretrained MoveNet and no custom training. The separation of pose engine
from test-specific measurement logic, raw results, interpretation and scoring is
unchanged, because nothing outside `vite.config.js` and the new shim was edited.
No webcam frames are stored or uploaded, since none of that code was involved.

**It is also a net improvement in two small ways.** Roughly 50 MB of
`.tflite` model weights, `.wasm` binaries and `pose_solution_packed_assets.data`
in `@mediapipe/pose` no longer enter the module graph. And if someone later
tries to use BlazePose with the MediaPipe runtime, they get a sentence
explaining the situation rather than an obscure failure about a missing WASM
binary.

---

## D. What I tested myself

Everything below ran in my Linux VM against your actual installed packages.

**The fix works at the level the error occurs.** I emulated Vite's alias with a
Node `module.register` resolve hook — no files copied, no `node_modules`
modified — and imported the real `pose-detection.esm.js`:

| | outcome |
|---|---|
| without the alias | `SyntaxError: Named export 'Pose' not found` — your bug, reproduced |
| with the alias | imported successfully |

With the alias, the module's public surface is intact and is exactly what
`poseEngine.js` uses:

```
SupportedModels: {"MoveNet":"MoveNet","BlazePose":"BlazePose","PoseNet":"PoseNet"}
createDetector: function
movenet.modelType: {"SINGLEPOSE_LIGHTNING":"SinglePose.Lightning", ...}
```

**Both runtime paths behave correctly.** Under the alias:

- `createDetector(MoveNet, { modelType: SINGLEPOSE_LIGHTNING })` proceeded
  through validation and backend selection and got as far as **downloading the
  model weights** (`fetch failed` — this VM has no network). It never touched
  the shim. The MoveNet path is intact.
- `createDetector(BlazePose, { runtime: 'mediapipe' })` threw the shim's
  explanatory error, confirming the redirect is wired up and confined to the
  unused path.

**Static and unit checks.** `node --check vite.config.js` parses as an ES
module. The alias target resolves to a path that exists. The shim exports
`Pose` plus a `default` whose `.Pose` is the same class, and constructing it
throws. ESLint runs in my VM — it linted 52 files for real, and reported **0
problems in both files I touched**.

**Regression sweep, all as before.**

```
frontend: npm test                                    104 pass, 0 fail
backend:  python3 -m unittest discover -s tests -t .  Ran 200 tests, OK
verify_backend.py         27/28 *   verify_agents.py     39/39
verify_flow.py            20/20     verify_security.py   40/40
verify_assessments.py     32/32     verify_frontend.mjs  17/17
verify_reports.py         59/59
```

`*` The one failure is the pre-existing `backend/.env` issue, not a regression:
the file is still in `HEAD`'s tree at commits `a3f6044` and `6907387`, alongside
six tracked `__pycache__/*.pyc` files. Its deletion is staged but uncommitted.
That check was already failing before this task and needs a git commit plus a
`JWT_SECRET` rotation, which is yours to do.

**One thing you should know about, unrelated to this fix.** `npm run lint`
exits non-zero on 12 pre-existing errors in 11 files — none of them files I
touched here. Five are `react-hooks/set-state-in-effect` on the Dashboard,
Guidance, History, ReportReview and Reports pages; four are
`no-useless-assignment` in `services/{assessments,guidance,reports}.js` and
`pose/poseEngine.js`; two are `react-refresh/only-export-components` in
`SessionResults.jsx`; one is `react-hooks/refs` in `useTestRunner.js`. They come
from ESLint 10's newer rules. None affect whether the app runs. I left them
alone because you asked me not to rewrite unrelated code — say the word and
I'll clear them as a separate task.

---

## E. What I could not test, because my environment is not your PC

**My shell is an isolated Linux VM with your project folder mounted. It is not
your Windows machine, and there is no tool in this session that executes a
command there.** I have not run anything on your PC and am not claiming to have.

Specifically, **I could not run `vite` at all.** Your `node_modules` contains
only `@rolldown/binding-win32-x64-msvc`, so importing `vite` in my VM fails with
"Cannot find native binding". That is correct and expected — it is the right
binding for your machine. Installing a Linux binding into the mounted folder
would have overwritten your Windows binaries and broken your tree, so I did not.

So the following remain unverified by me, and `npm run dev` on your machine is
the real test:

- `npm run dev` actually starting, and dependency optimization completing
- `npm run build` producing a bundle
- Any React component compiling or rendering — still true, no component has
  ever been rendered
- MoveNet weights actually downloading, the WebGL backend initialising, and a
  real webcam producing keypoints

What I did instead was verify the precise mechanism that was failing — module
resolution and export linking — using the real packages, and confirm from Vite's
own bundled source that the alias is honoured in the optimizer.

---

## F. Exact next commands for you to run

```
cd C:\Users\PURAB\Downloads\Projects\MoveWell-AI
npm.cmd run dev
```

Then open http://localhost:5173 with the backend running in another terminal.

**No cache clearing is needed**, and I did not delete anything. I checked two
things to be sure. First, `node_modules\.vite` exists but is **empty** — the
failed optimization aborted before writing any metadata. Second, Vite keys its
dep cache on `getDepHash`, which is `hash(lockfileHash + configHash)`, and
`getConfigHash` serialises `resolve: config.resolve` in full. The alias is part
of `resolve`, so changing it invalidates the cache automatically.

If you do see anything that looks stale, this clears only the generated dep
cache and nothing else:

```
Remove-Item -Recurse -Force node_modules\.vite
npm.cmd run dev
```

I use `npm.cmd` rather than `npm` because bare `npm` resolves to `npm.ps1`,
which is what a restrictive execution policy refuses to load. Your
`Set-ExecutionPolicy -Scope Process` change only applies to that one PowerShell
session, so a new window would hit the problem again; `npm.cmd` sidesteps it
permanently.

Worth running once the dev server is up, to confirm the production path also
resolves the alias:

```
npm.cmd run build
```

If `npm run dev` still fails, paste the full output. The most likely remaining
issue is unrelated to this one, and the error text will say which.
