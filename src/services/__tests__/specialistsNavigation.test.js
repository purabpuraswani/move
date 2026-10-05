import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { SPECIALIST_ALIASES } from "../unifiedPlan.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../../..");

/**
 * The five specialists, as the product presents them.
 *
 * This file is the client half of a two-sided contract. The server half is
 * backend/orchestration/specialists.py, which is the single place the five are
 * defined; the assertions below read that file and check this client agrees
 * with it, so a rename on one side cannot quietly leave the other pointing at
 * a specialist that no longer exists.
 */
const EXPECTED_SPECIALISTS = [
  {
    id: "exercise_movement",
    slug: "exercise-movement",
    title: "Exercise & Movement",
    route: "/specialist/exercise-movement",
    icon: "🏃",
  },
  {
    id: "nutrition_lifestyle",
    slug: "nutrition-lifestyle",
    title: "Nutrition & Lifestyle",
    route: "/specialist/nutrition-lifestyle",
    icon: "🍎",
  },
  {
    id: "behaviour_adherence",
    slug: "behaviour-adherence",
    title: "Behaviour & Adherence",
    route: "/specialist/behaviour-adherence",
    icon: "🧠",
  },
  {
    id: "recovery_care",
    slug: "recovery-care",
    title: "Recovery & Care",
    route: "/specialist/recovery-care",
    icon: "🌙",
  },
  {
    id: "safety_practitioner",
    slug: "safety-practitioner",
    title: "Safety & Practitioner Recommendation",
    route: "/specialist/safety-practitioner",
    icon: "🛡️",
  },
];

function backendRegistrySource() {
  return readFileSync(
    path.join(repoRoot, "backend/orchestration/specialists.py"),
    "utf8",
  );
}

/** The SPECIALISTS dict entries the backend defines, in file order. */
function backendSpecialistInfo() {
  const source = backendRegistrySource();

  const ids = [...source.matchAll(/^([A-Z_]+) = "([a-z_]+)"$/gm)].map(
    ([, , value]) => value,
  );
  const slugs = [...source.matchAll(/"slug": "([a-z-]+)"/g)].map(([, value]) => value);
  const names = [...source.matchAll(/"name": "([^"]+)"/g)].map(([, value]) => value);

  return { ids, slugs, names, source };
}

test("exactly five specialists are presented", () => {
  assert.equal(EXPECTED_SPECIALISTS.length, 5);

  const routes = EXPECTED_SPECIALISTS.map((s) => s.route);

  for (const specialist of EXPECTED_SPECIALISTS) {
    assert.ok(routes.includes(specialist.route));
  }
});

test("the two removed specialists are gone from the user-facing list", () => {
  const titles = EXPECTED_SPECIALISTS.map((s) => s.title).join(" | ");

  // Exercise and physiotherapy are ONE specialist now, and safety is a
  // practitioner recommendation rather than a "clinical escalation" desk.
  assert.ok(!titles.includes("Physiotherapy"));
  assert.ok(!titles.includes("Physical Activity"));
  assert.ok(!titles.includes("Clinical Escalation"));
  assert.ok(titles.includes("Safety & Practitioner Recommendation"));
});

test("each specialist has a unique id, route, and title", () => {
  const ids = new Set(EXPECTED_SPECIALISTS.map((s) => s.id));
  const titles = new Set(EXPECTED_SPECIALISTS.map((s) => s.title));
  const routes = new Set(EXPECTED_SPECIALISTS.map((s) => s.route));

  assert.equal(ids.size, 5);
  assert.equal(titles.size, 5);
  assert.equal(routes.size, 5);
});

test("the client's specialist list matches the backend registry", () => {
  const { slugs, names } = backendSpecialistInfo();

  for (const specialist of EXPECTED_SPECIALISTS) {
    assert.ok(
      slugs.includes(specialist.slug),
      `backend registry has no slug ${specialist.slug}`,
    );
    assert.ok(
      names.includes(specialist.title),
      `backend registry has no specialist named ${specialist.title}`,
    );
  }

  assert.equal(slugs.length, 5, "the backend must define exactly five specialists");
});

test("specialist route aliases resolve consistently", () => {
  assert.equal(SPECIALIST_ALIASES["exercise-movement"], "exercise_movement");
  assert.equal(SPECIALIST_ALIASES.exercise, "exercise_movement");
  assert.equal(SPECIALIST_ALIASES.exercise_activity, "exercise_movement");
  assert.equal(SPECIALIST_ALIASES.physio, "exercise_movement");
  assert.equal(SPECIALIST_ALIASES.movement, "exercise_movement");
  assert.equal(SPECIALIST_ALIASES.nutrition, "nutrition_lifestyle");
  assert.equal(SPECIALIST_ALIASES.behaviour, "behaviour_adherence");
  assert.equal(SPECIALIST_ALIASES.habits, "behaviour_adherence");
  assert.equal(SPECIALIST_ALIASES.recovery, "recovery_care");
  assert.equal(SPECIALIST_ALIASES.sleep, "recovery_care");
  assert.equal(SPECIALIST_ALIASES.safety, "safety_practitioner");
  assert.equal(SPECIALIST_ALIASES.clinical, "safety_practitioner");
});

test("every retired specialist id the backend knows is known here too", () => {
  // The alias table exists so an old link or a stored id still lands on the
  // one specialist that absorbed it. If the backend learns a new alias and
  // the client does not, an old URL starts 404-ing in the browser only.
  const { source } = backendSpecialistInfo();

  const block = source.match(/LEGACY_ID_ALIASES = \{([\s\S]*?)\n\}/);

  assert.ok(block, "could not find LEGACY_ID_ALIASES in the backend registry");

  const backendAliases = [...block[1].matchAll(/"([a-z_]+)":/g)].map(([, key]) => key);

  assert.ok(backendAliases.length > 0);

  for (const alias of backendAliases) {
    assert.ok(
      Object.prototype.hasOwnProperty.call(SPECIALIST_ALIASES, alias),
      `the client does not know the backend alias ${alias}`,
    );
  }
});

import {
  normalizeEvidence,
  normalizeRecommendation,
  normalizeRecommendations,
  isPlainRenderable,
} from "../specialistData.js";

test("normalizeRecommendation handles Behaviour specialist object without returning raw object children", () => {
  const behaviourRaw = {
    id: "habit-1",
    title: "Take Regular Movement Breaks",
    action: "Stand up and stretch for 2 minutes every hour",
    why: "Reduces prolonged sedentary time and joint stiffness",
  };

  const normalized = normalizeRecommendation(behaviourRaw, 0);
  assert.ok(normalized);
  assert.equal(normalized.id, "habit-1");
  assert.equal(normalized.title, "Take Regular Movement Breaks");
  assert.equal(normalized.action, "Stand up and stretch for 2 minutes every hour");
  assert.equal(normalized.why, "Reduces prolonged sedentary time and joint stiffness");
  assert.equal(typeof normalized.title, "string");
  assert.equal(typeof normalized.action, "string");
  assert.equal(typeof normalized.why, "string");
});

test("normalizeRecommendation handles Exercise specialist object", () => {
  const exerciseRaw = {
    id: "daily_walking_routine",
    title: "Progressive Daily Walking Routine",
    action: "Aim for 20-30 minutes of brisk walking 4-5 days per week",
    why: "Builds cardiovascular endurance and functional capacity",
  };

  const normalized = normalizeRecommendation(exerciseRaw, 0);
  assert.ok(normalized);
  assert.equal(normalized.id, "daily_walking_routine");
  assert.equal(normalized.title, "Progressive Daily Walking Routine");
  assert.equal(typeof normalized.action, "string");
  assert.equal(typeof normalized.why, "string");
});

test("normalizeRecommendation handles a movement programme exercise object", () => {
  const physioRaw = {
    id: "wall_slide",
    name: "Wall Slide",
    why: "Improves shoulder flexion and scapular upward rotation",
    target: "shoulder",
    difficulty: 2,
    sets: 2,
    repetitions: 10,
    safety: ["Maintain gentle abdominal brace", "Stop if sharp pain occurs"]
  };

  const normalized = normalizeRecommendation(physioRaw, 1);
  assert.ok(normalized);
  assert.equal(normalized.id, "wall_slide");
  assert.equal(normalized.title, "Wall Slide");
  assert.equal(normalized.target, "shoulder");
  assert.equal(normalized.sets, 2);
  assert.equal(normalized.repetitions, 10);
  assert.equal(normalized.safetyNotes.length, 2);
  assert.equal(normalized.safetyNotes[0], "Maintain gentle abdominal brace");
});

test("normalizeRecommendation safely handles plain strings, nulls, and malformed inputs", () => {
  assert.equal(normalizeRecommendation(null), null);
  assert.equal(normalizeRecommendation(undefined), null);

  const stringNorm = normalizeRecommendation("Prioritize 7-8 hours of sleep", 0);
  assert.ok(stringNorm);
  assert.equal(stringNorm.title, "Prioritize 7-8 hours of sleep");
  assert.equal(stringNorm.isSimpleString, true);
});

test("normalizeRecommendations array never contains nested un-renderable objects", () => {
  const mixedList = [
    "Simple string recommendation",
    {
      id: "rec_1",
      title: "Structured card",
      action: "Do action",
      why: "Good reason"
    },
    {
      id: "physio_1",
      name: "Chair Squat",
      target: "knee",
      sets: 3,
      repetitions: 8
    },
    null,
    undefined
  ];

  const normalizedList = normalizeRecommendations(mixedList);
  assert.equal(normalizedList.length, 3);

  for (const item of normalizedList) {
    // None of the core rendered properties should be non-string/non-number objects
    assert.ok(typeof item.id === "string");
    assert.ok(typeof item.title === "string");
    if (item.action !== null) assert.ok(typeof item.action === "string");
    if (item.why !== null) assert.ok(typeof item.why === "string");
    if (item.target !== null) assert.ok(typeof item.target === "string");
    if (item.sets !== null) assert.ok(typeof item.sets === "number");
    if (item.repetitions !== null) assert.ok(typeof item.repetitions === "number");
  }
});

test("normalizeEvidence parses various input types into displayable strings", () => {
  // Array of strings
  const stringArray = ["Evidence 1", "Evidence 2"];
  assert.deepEqual(normalizeEvidence(stringArray), ["Evidence 1", "Evidence 2"]);

  // Single string
  assert.deepEqual(normalizeEvidence("Single evidence line"), ["Single evidence line"]);

  // Capability/finding objects
  const findingObjects = [
    { capability: "Shoulder Range", finding: "Reduced flexion", evidence: ["140 deg", "mild stiffness"] },
    { capability: "Chair Rise", finding: "Good power" }
  ];
  const normalizedFindings = normalizeEvidence(findingObjects);
  assert.equal(normalizedFindings.length, 2);
  assert.equal(normalizedFindings[0], "Shoulder Range: Reduced flexion (140 deg; mild stiffness)");
  assert.equal(normalizedFindings[1], "Chair Rise: Good power");

  // Null / undefined / empty
  assert.deepEqual(normalizeEvidence(null), []);
  assert.deepEqual(normalizeEvidence(undefined), []);
  assert.deepEqual(normalizeEvidence([]), []);
});

test("isPlainRenderable accurately guards React child values", () => {
  assert.equal(isPlainRenderable("Hello"), true);
  assert.equal(isPlainRenderable(42), true);
  assert.equal(isPlainRenderable({ id: 1 }), false);
  assert.equal(isPlainRenderable([1, 2, 3]), false);
  assert.equal(isPlainRenderable(null), false);
  assert.equal(isPlainRenderable(undefined), false);
});
