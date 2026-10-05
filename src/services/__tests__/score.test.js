/**
 * The MoveWell Score, as the client reads it.
 *
 * The score is computed server-side. These tests exist to pin the one rule that
 * matters on this side of the wire: the client shows what it is given and never
 * fills a gap. A client that can produce a number when the server did not send
 * one will eventually show somebody a score they do not have.
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  changeWording,
  domainChanges,
  focusStatement,
  hasScore,
  movewellScore,
  scoreChange,
  scoreFocus,
  scoreMessage,
  scoreMethod,
  scoredDomains,
  unscoredDomains,
} from "../score.js";

const WORKFLOW = {
  movewell_score: {
    available: true,
    value: 72,
    band: "STEADY",
    message: "You're doing well overall, with a couple of areas worth working on.",
    focus: { key: "stability_need", label: "Stability", level: "MEDIUM" },
    focus_statement: "Stability came out as a focus area in your latest assessment, so MoveWell has built your plan around it.",
    method: "Worked out from your own results: … It is a way of following your own progress, not a medical measurement.",
    previous: { value: 64, recorded_at: "2026-09-01T09:00:00+00:00" },
    change: 8,
    domains: [
      {
        key: "mobility_need",
        label: "Mobility",
        source: "measured",
        assessed: true,
        value: 76,
        previous_value: 74,
        change: 2,
        level: "LOW",
        evidence: ["…"],
      },
      {
        key: "stability_need",
        label: "Stability",
        source: "measured",
        assessed: true,
        value: 64,
        previous_value: 53,
        change: 11,
        level: "MEDIUM",
        evidence: ["…"],
      },
      {
        key: "nutrition_need",
        label: "Nutrition",
        source: "answered",
        assessed: false,
        value: null,
        previous_value: null,
        change: null,
        level: "NOT_ASSESSED",
        evidence: ["This user has not answered the optional nutrition questions."],
      },
    ],
  },
};

const EMPTY = {
  movewell_score: {
    available: false,
    value: null,
    band: null,
    message: null,
    focus: null,
    focus_statement: null,
    domains: [],
    previous: null,
    change: null,
    method: "Worked out from your own results.",
  },
};

test("the score block is read from the workflow response", () => {
  assert.equal(movewellScore(WORKFLOW).value, 72);
  assert.equal(movewellScore({}), null);
  assert.equal(movewellScore(null), null);
  assert.equal(movewellScore({ movewell_score: "72" }), null);
});

test("a score exists only when the server says it does", () => {
  assert.equal(hasScore(WORKFLOW), true);
  assert.equal(hasScore(EMPTY), false);
  assert.equal(hasScore({}), false);
});

test("no score means no number anywhere, not a zero", () => {
  // The whole point of this module. Nothing here invents a 0 to fill space.
  assert.equal(hasScore(EMPTY), false);
  assert.equal(scoreMessage(EMPTY), null);
  assert.equal(scoreFocus(EMPTY), null);
  assert.equal(focusStatement(EMPTY), null);
  assert.equal(scoreChange(EMPTY), null);
  assert.deepEqual(scoredDomains(EMPTY), []);
  assert.deepEqual(domainChanges(EMPTY), []);
});

test("the message, focus and method are the server's words", () => {
  assert.match(scoreMessage(WORKFLOW), /doing well overall/);
  assert.equal(scoreFocus(WORKFLOW).label, "Stability");
  assert.match(focusStatement(WORKFLOW), /focus area/);
  assert.match(scoreMethod(WORKFLOW), /not a medical measurement/);
});

test("the change is the server's arithmetic, with the previous value", () => {
  const change = scoreChange(WORKFLOW);

  assert.equal(change.value, 8);
  assert.equal(change.from, 64);
  assert.equal(change.at, "2026-09-01T09:00:00+00:00");
});

test("no previous score means no change, not a change of zero", () => {
  const withoutPrevious = {
    movewell_score: { ...WORKFLOW.movewell_score, previous: null, change: null },
  };

  assert.equal(scoreChange(withoutPrevious), null);
});

test("a measured zero change is a real answer and is kept", () => {
  const unchanged = {
    movewell_score: {
      ...WORKFLOW.movewell_score,
      previous: { value: 72, recorded_at: "2026-09-01T09:00:00+00:00" },
      change: 0,
    },
  };

  const change = scoreChange(unchanged);

  assert.ok(change);
  assert.equal(change.value, 0);
  assert.equal(changeWording(0), "unchanged");
});

test("only assessed domains with a real value count as scored", () => {
  const scored = scoredDomains(WORKFLOW);

  assert.deepEqual(
    scored.map((domain) => domain.key),
    ["mobility_need", "stability_need"],
  );

  // The unassessed domain is reported separately, with its own reason, so a
  // screen can ask for the missing information instead of showing a zero.
  const unscored = unscoredDomains(WORKFLOW);

  assert.equal(unscored.length, 1);
  assert.equal(unscored[0].label, "Nutrition");
  assert.ok(unscored[0].evidence.length);
});

test("domain changes are ordered by size and skip the ones that did not move", () => {
  const changes = domainChanges(WORKFLOW);

  assert.equal(changes.length, 2);
  assert.equal(changes[0].label, "Stability");
  assert.equal(changes[0].change, 11);

  const withAStillDomain = {
    movewell_score: {
      ...WORKFLOW.movewell_score,
      domains: [
        ...WORKFLOW.movewell_score.domains,
        {
          key: "behaviour_need",
          label: "Behaviour",
          source: "answered",
          assessed: true,
          value: 80,
          previous_value: 80,
          change: 0,
          level: "LOW",
          evidence: ["…"],
        },
      ],
    },
  };

  assert.deepEqual(
    domainChanges(withAStillDomain).map((entry) => entry.label),
    ["Stability", "Mobility"],
  );
});

test("the wording for a change never judges the person", () => {
  assert.equal(changeWording(4), "up");
  assert.equal(changeWording(-4), "down");
  assert.equal(changeWording(0), "unchanged");
  assert.equal(changeWording(null), null);
  assert.equal(changeWording(undefined), null);
});

test("a malformed score block never throws", () => {
  for (const broken of [
    { movewell_score: {} },
    { movewell_score: { available: true } },
    { movewell_score: { available: true, domains: "nope" } },
    { movewell_score: { available: true, value: "72", domains: [null, 3] } },
  ]) {
    assert.doesNotThrow(() => {
      hasScore(broken);
      scoreMessage(broken);
      scoredDomains(broken);
      domainChanges(broken);
      scoreChange(broken);
    });
  }
});
