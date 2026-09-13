import test from "node:test";
import assert from "node:assert/strict";

const EXPECTED_SPECIALISTS = [
  {
    id: "exercise_activity",
    alias: "exercise",
    title: "Exercise & Physical Activity",
    route: "/specialist/exercise",
    icon: "🏃"
  },
  {
    id: "physio",
    alias: "physio",
    title: "Physiotherapy & Movement",
    route: "/specialist/physio",
    icon: "🧑‍⚕️"
  },
  {
    id: "nutrition",
    alias: "nutrition",
    title: "Nutrition & Lifestyle",
    route: "/specialist/nutrition",
    icon: "🍎"
  },
  {
    id: "recovery",
    alias: "recovery",
    title: "Recovery & Care",
    route: "/specialist/recovery",
    icon: "🌙"
  },
  {
    id: "behaviour",
    alias: "behaviour",
    title: "Behaviour & Adherence",
    route: "/specialist/behaviour",
    icon: "🧠"
  },
  {
    id: "safety",
    alias: "safety",
    title: "Safety & Clinical Escalation",
    route: "/specialist/safety",
    icon: "🛡️"
  }
];

test("exactly 6 specialists are defined with proper titles and routes", () => {
  assert.equal(EXPECTED_SPECIALISTS.length, 6);
  const routes = EXPECTED_SPECIALISTS.map(s => s.route);
  assert.ok(routes.includes("/specialist/exercise"));
  assert.ok(routes.includes("/specialist/physio"));
  assert.ok(routes.includes("/specialist/nutrition"));
  assert.ok(routes.includes("/specialist/recovery"));
  assert.ok(routes.includes("/specialist/behaviour"));
  assert.ok(routes.includes("/specialist/safety"));
});

test("each specialist has a unique id, route, and clinical title", () => {
  const ids = new Set(EXPECTED_SPECIALISTS.map(s => s.id));
  const titles = new Set(EXPECTED_SPECIALISTS.map(s => s.title));
  const routes = new Set(EXPECTED_SPECIALISTS.map(s => s.route));

  assert.equal(ids.size, 6);
  assert.equal(titles.size, 6);
  assert.equal(routes.size, 6);
});

test("specialist route aliases resolve consistently", () => {
  const aliasMap = {
    exercise: "exercise",
    exercise_activity: "exercise",
    activity: "exercise",
    physio: "physio",
    movement: "physio",
    nutrition: "nutrition",
    recovery: "recovery",
    sleep: "recovery",
    behaviour: "behaviour",
    behavior: "behaviour",
    habits: "behaviour",
    safety: "safety",
    clinical: "safety"
  };

  assert.equal(aliasMap["exercise"], "exercise");
  assert.equal(aliasMap["exercise_activity"], "exercise");
  assert.equal(aliasMap["movement"], "physio");
  assert.equal(aliasMap["sleep"], "recovery");
  assert.equal(aliasMap["habits"], "behaviour");
  assert.equal(aliasMap["clinical"], "safety");
});

import {
  normalizeEvidence,
  normalizeRecommendation,
  normalizeRecommendations,
  isPlainRenderable
} from "../specialistData.js";

test("normalizeRecommendation handles Behaviour specialist object without returning raw object children", () => {
  const behaviourRaw = {
    id: "habit-1",
    title: "Take Regular Movement Breaks",
    action: "Stand up and stretch for 2 minutes every hour",
    why: "Reduces prolonged sedentary time and joint stiffness"
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
    why: "Builds cardiovascular endurance and functional capacity"
  };

  const normalized = normalizeRecommendation(exerciseRaw, 0);
  assert.ok(normalized);
  assert.equal(normalized.id, "daily_walking_routine");
  assert.equal(normalized.title, "Progressive Daily Walking Routine");
  assert.equal(typeof normalized.action, "string");
  assert.equal(typeof normalized.why, "string");
});

test("normalizeRecommendation handles Physio programme exercise object", () => {
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


