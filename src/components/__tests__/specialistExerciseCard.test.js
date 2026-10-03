/**
 * Where exercise EXECUTION is allowed to live.
 *
 * A specialist card is a reference: the diagram, the prescription, and a
 * tick. Starting a camera-guided session belongs to the Movement panel
 * and the exercise page, because that is the one place that owns the
 * pose engine and the recording lifecycle. Two routes into one recording
 * system is the bug this guards against, and it is the kind of thing a
 * later edit reintroduces by copying a button.
 *
 * These are STRUCTURAL tests over the source files, not render tests:
 * this project has no React render infrastructure (`node --test` on pure
 * JS), so they assert which identifiers appear in which module rather
 * than what a mounted component does. They catch a Start button being
 * pasted back into a card; they do not prove the card renders. Comments
 * are stripped first, so the comment explaining the removal cannot
 * satisfy the test that checks for the removal.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.resolve(here, "../..");

/** Source with comments removed, so prose about code is not read as code. */
function codeOf(relativePath) {
  return readFileSync(path.join(src, relativePath), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/^\s*\/\/.*$/gm, " ");
}

// Identifiers that only exist to run a camera-guided session.
const EXECUTION_MARKERS = [
  "usePoseEngine",
  "CameraStage",
  "getUserMedia",
  "onStartExercise",
  "Start exercise",
  "Begin Recording",
];

// My Plan is recommendation + reference + completion. None of these
// modules may launch a camera session. SpecialistPanel joined this list
// when the Movement panel's own "Start exercise" button was removed.
const REFERENCE_ONLY = [
  "components/SpecialistExerciseList.jsx",
  "pages/SpecialistDetailPage.jsx",
  "components/SpecialistPanel.jsx",
  "pages/PlanPage.jsx",
];

for (const file of REFERENCE_ONLY) {
  test(`${file} carries no exercise-execution control`, () => {
    const code = codeOf(file);

    for (const marker of EXECUTION_MARKERS) {
      assert.ok(
        !code.includes(marker),
        `${file} references ${marker}: execution has leaked back into a reference card`,
      );
    }
  });
}

test("the specialist card still shows the diagram and the completion control", () => {
  const code = codeOf("components/SpecialistExerciseList.jsx");

  assert.match(code, /getExerciseImage/, "the exercise diagram was dropped");
  assert.match(code, /type="checkbox"/, "the completion control was dropped");
  assert.match(code, /markCompleted/, "the tick no longer writes a result");
  assert.match(code, /undoCompletion/, "a tick can no longer be undone");
});

test("only a manual confirmation can be un-ticked", () => {
  // A camera session is a measurement. The card must decide this from
  // the result's own source, not from whether a box looks checked.
  const code = codeOf("components/SpecialistExerciseList.jsx");

  assert.match(code, /manual_confirmation/);
  assert.match(
    code,
    /disabled=\{lockedByCamera\}/,
    "a camera-measured result must not be removable from a checkbox",
  );
});

test("no My Plan module navigates to the camera exercise page", () => {
  // The marker list above missed a bare "Start" button in a legacy plan
  // section that still routed to /exercise/:id. Navigation is the thing
  // that actually matters, so assert on that directly.
  for (const file of REFERENCE_ONLY) {
    assert.ok(
      !/\/exercise\/\$\{/.test(codeOf(file)),
      `${file} still navigates to the camera exercise page`,
    );
  }
});

test("the exercise page still owns the full camera session", () => {
  // The other half of the split: removing execution from the cards must
  // not have removed it from the page that is supposed to have it.
  const code = codeOf("pages/ExercisePage.jsx");

  for (const marker of ["usePoseEngine", "CameraStage", "RawCameraView"]) {
    assert.ok(code.includes(marker), `ExercisePage lost ${marker}`);
  }
});

test("the movement panel keeps the reference and completion controls", () => {
  // Removing execution must not have removed the things My Plan is FOR.
  const code = codeOf("components/SpecialistPanel.jsx");

  assert.match(code, /getExerciseImage/, "the exercise diagram was dropped");
  assert.match(code, /View demonstration preview/, "the demonstration preview was dropped");
  assert.match(code, /type="checkbox"/, "the completion control was dropped");
  assert.match(code, /Make it harder:/, "the progression guidance was dropped");
  assert.match(code, /Make it easier:/, "the regression guidance was dropped");
});
