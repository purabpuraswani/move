/**
 * Two things the profile and check-in work had to add to a surface that does
 * not exist in a unit test any other way: a way in, and a route to land on.
 *
 * These are STRUCTURAL tests over the source files — this project's test runner
 * is `node --test` on plain JavaScript with no React renderer — so they assert
 * that the navigation entry and the routes exist and are protected. A page with
 * no way to reach it is the failure they prevent.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.resolve(here, "../..");

function codeOf(relativePath) {
  return readFileSync(path.join(src, relativePath), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/^\s*\/\/.*$/gm, " ");
}

test("the product has exactly four sections, and the profile lives under You", () => {
  const shell = codeOf("components/ui/AppShell.jsx");

  for (const label of ["Today", "Plan", "Progress", "You"]) {
    assert.match(shell, new RegExp(`label: "${label}"`), `the navigation has no ${label} entry`);
  }

  for (const route of ['"/today"', '"/plan"', '"/progress"', '"/you"']) {
    assert.ok(shell.includes(`to: ${route}`), `the navigation does not link to ${route}`);
  }

  // The profile is reached through You, which is what the test above this one
  // cared about before the navigation was simplified to four sections.
  const youItem = shell.slice(shell.indexOf('label: "You"'));

  assert.match(youItem.slice(0, 260), /\/you/, "You does not lead to the profile experience");
});

test("no technical module is a top-level navigation item", () => {
  const shell = codeOf("components/ui/AppShell.jsx");

  for (const technical of [
    "/reports",
    "/history",
    "/guidance",
    "/internal/dashboard",
    "/onboarding",
    "/nutrition-check-in",
  ]) {
    assert.ok(
      !shell.includes(`to: "${technical}"`),
      `${technical} is exposed as a top-level section`,
    );
  }
});

test("the profile and check-in routes exist and require a session", () => {
  const app = codeOf("App.jsx");

  for (const route of [
    "/profile",
    "/you",
    "/today",
    "/dashboard",
    "/results",
    "/nutrition-check-in",
  ]) {
    assert.match(
      app,
      new RegExp(`path="${route}"`),
      `App.jsx does not register ${route}`,
    );
  }

  // Every protected page in this app is wrapped; the new ones must be too.
  for (const route of ["/you", "/today", "/results", "/nutrition-check-in"]) {
    const block = app.slice(app.indexOf(`path="${route}"`));

    assert.match(block.slice(0, 400), /RequireAuth/, `${route} is not protected`);
  }
});

test("the profile page reads and writes the server, never a local copy", () => {
  const page = codeOf("pages/ProfilePage.jsx");

  assert.match(page, /fetchProfile/, "the profile page does not load from the server");
  assert.match(page, /updateProfile/, "the profile page does not save to the server");
  // A profile kept in the browser would be exactly the "frontend-only profile
  // data" the brief forbids.
  assert.ok(
    !/localStorage\.setItem\(\s*["'`]movewell_profile/.test(page),
    "the profile page caches the profile in the browser",
  );
  assert.match(
    page,
    /Future plan reviews will use the new information/,
    "the save confirmation no longer says when the change takes effect",
  );
});

test("the check-in page renders the questions the server sends", () => {
  const page = codeOf("pages/NutritionCheckInPage.jsx");

  assert.match(page, /fetchNutritionCheckIn/, "the check-in does not load its questions");
  assert.match(page, /saveNutritionCheckIn/, "the check-in does not save answers");
  // It must not hold its own copy of the questions or their options: the
  // vocabulary lives in backend/nutrition_library/check_in.py.
  for (const hardcoded of ["meals_per_day", "water_glasses_per_day", "almost_daily"]) {
    assert.ok(
      !page.includes(hardcoded),
      `the check-in page hard-codes a question or option: ${hardcoded}`,
    );
  }
});
