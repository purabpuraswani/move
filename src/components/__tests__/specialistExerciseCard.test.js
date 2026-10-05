/**
 * Where exercise EXECUTION is allowed to live, and where it is not.
 *
 * There is one camera session in this product and it belongs to
 * `pages/ExercisePage.jsx`, which owns the pose engine and the recording
 * lifecycle. Everything else — the plan screen, a specialist's page, a
 * reference card — may only *point at* it.
 *
 * The distinction changed shape when the plan was rebuilt around the server's
 * unified plan. The plan's exercise items now carry their own action, and that
 * action is a button ("Start exercise") whose route the SERVER supplies. So a
 * plan card does navigate to the camera page — that is the required behaviour,
 * not a leak — while still containing no camera code of its own. These tests
 * assert exactly that split:
 *
 *   * no plan module embeds a pose engine, a camera view or getUserMedia;
 *   * no plan module constructs an exercise URL itself (the server does);
 *   * the plan modules read the plan rather than building one;
 *   * ExercisePage is still the one place with the full session.
 *
 * These are STRUCTURAL tests over the source files, not render tests: this
 * project has no React render infrastructure (`node --test` on pure JS), so
 * they assert which identifiers appear in which module rather than what a
 * mounted component does. Comments are stripped first, so the comment
 * explaining a rule cannot satisfy the test that checks it.
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
  "RawCameraView",
  "getUserMedia",
  "createExerciseAssessmentEngine",
  "Begin recording",
];

// Screens and cards that show the plan. None of them may own a camera
// session; starting one is ExercisePage's job and they link to it.
const REFERENCE_ONLY = [
  "components/PlanActionItem.jsx",
  "components/PlanSectionPanel.jsx",
  "components/SpecialistTeamCard.jsx",
  "pages/SpecialistDetailPage.jsx",
  "pages/PlanPage.jsx",
];

for (const file of REFERENCE_ONLY) {
  test(`${file} carries no camera session of its own`, () => {
    const code = codeOf(file);

    for (const marker of EXECUTION_MARKERS) {
      assert.ok(
        !code.includes(marker),
        `${file} references ${marker}: a second camera session has leaked in`,
      );
    }
  });
}

test("no plan module builds an exercise URL itself", () => {
  // The route comes from the server (item.action.route). A module that
  // assembles its own `/exercise/...` path has started second-guessing where
  // an action should go, which is how two routes into one recording system
  // begin.
  for (const file of REFERENCE_ONLY) {
    const code = codeOf(file);

    assert.ok(
      !/["'`]\/exercise\//.test(code),
      `${file} constructs an exercise URL instead of following the server's action`,
    );
    assert.ok(
      !/navigate\(`\/exercise/.test(code),
      `${file} navigates to a hand-built exercise URL`,
    );
  }
});

test("the plan card follows the action the server put on the item", () => {
  const code = codeOf("components/PlanActionItem.jsx");

  assert.match(code, /actionOf/, "the card no longer reads the item's own action");
  assert.match(code, /getExerciseImage/, "the exercise diagram was dropped");
  assert.match(code, /exerciseIdOf/, "the image is no longer keyed to the item's own id");
});

test("PlanPage composes no plan of its own", () => {
  const code = codeOf("pages/PlanPage.jsx");

  // It must read the server's plan, its selection and its cards.
  assert.match(code, /unifiedPlan/, "PlanPage does not read the server's unified plan");
  assert.match(code, /actionSections/, "PlanPage does not use the server's action list");
  assert.match(code, /teamCards/, "PlanPage does not use the server's specialist cards");
  assert.match(code, /planSummary/, "PlanPage does not use the server's plan summary");
  assert.match(code, /collaboration/, "PlanPage does not use the server's collaboration flow");

  // And it must not carry its own programme, dosage or specialist config.
  for (const forbidden of [
    "SPECIALIST_CONFIGS",
    "defaultRecommendations",
    "defaultEvidence",
    "defaultReason",
    "targetRepetitions",
  ]) {
    assert.ok(
      !code.includes(forbidden),
      `PlanPage still holds locally written plan content: ${forbidden}`,
    );
  }
});

test("the plan's reading order puts actions before reasoning", () => {
  // The redesign's whole point: a person sees what to do first, and the audit
  // trail second. This asserts the order in the source, so a later edit cannot
  // quietly put the reasoning back on top.
  const code = codeOf("components/PlanSectionPanel.jsx");

  const actionsAt = code.indexOf("plan-item-list");
  const reasonAt = code.indexOf("plan-section-reason");
  const detailsAt = code.indexOf("plan-section-details");

  assert.ok(actionsAt > -1, "the actions list was dropped");
  assert.ok(reasonAt > -1, "the short reason was dropped");
  assert.ok(detailsAt > -1, "the details block was dropped");
  assert.ok(actionsAt < reasonAt, "the reason now comes before the actions");
  assert.ok(reasonAt < detailsAt, "the details now come before the reason");

  // And the old leading fields are inside the details block, not above it.
  const focusAt = code.indexOf("Current focus");

  assert.ok(focusAt > detailsAt, "current focus is presented before the actions");
});

test("the plan card keeps a self-report path with an un-tick", () => {
  // Removing camera execution from the cards must not remove the other honest
  // way to record an exercise: a manual confirmation, which is the only route
  // for a movement the camera cannot measure. It has to stay distinguishable
  // from a measurement, and only it can be undone.
  const card = codeOf("components/PlanActionItem.jsx");

  assert.match(card, /type="checkbox"/, "the self-report control was dropped");
  assert.match(card, /completion\.markCompleted/, "the tick no longer writes a result");
  assert.match(card, /completion\.undoCompletion/, "the tick can no longer be undone");
  assert.match(
    card,
    /manual_confirmation/,
    "a camera-measured session must not be removable from a checkbox",
  );
  assert.match(
    card,
    /!withheld \?/,
    "a withheld item must not offer a second way to record it as done",
  );

  const hook = codeOf("hooks/useExerciseCompletion.js");

  assert.match(hook, /confirmExerciseManually/, "the tick must record a manual confirmation");
  assert.match(
    hook,
    /planId = null, itemId = null/,
    "the manual confirmation must be linkable to its plan item",
  );
});

test("the exercise page still owns the full camera session", () => {
  // The other half of the split: pointing at ExercisePage is only correct
  // while ExercisePage is the module that actually runs the session.
  const code = codeOf("pages/ExercisePage.jsx");

  for (const marker of ["usePoseEngine", "CameraStage", "RawCameraView"]) {
    assert.ok(code.includes(marker), `ExercisePage lost ${marker}`);
  }
});

test("the exercise page preserves the plan item it is performing", () => {
  // exerciseId, planId and itemId are what tie a finished session back to the
  // action that asked for it. Losing either one breaks adaptation, not just
  // bookkeeping.
  const code = codeOf("pages/ExercisePage.jsx");

  assert.match(code, /useSearchParams/, "the page no longer reads the plan ids from the URL");
  assert.match(code, /planIdFromUrl/, "the plan id from the URL is dropped");
  assert.match(code, /itemIdFromUrl/, "the item id from the URL is dropped");
  assert.match(code, /planId: recordingPlanId/, "the result is not linked to its plan");
  assert.match(code, /itemId: recordingItemId/, "the result is not linked to its item");
  assert.match(
    code,
    /source: "manual_confirmation"/,
    "a ticked box must be stored as a self-report, not as a camera measurement",
  );
});
