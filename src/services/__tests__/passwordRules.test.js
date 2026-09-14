import { test } from "node:test";
import assert from "node:assert/strict";

import {
  MIN_PASSWORD_LENGTH,
  validateEmail,
  validateNewPassword,
} from "../passwordRules.js";

test("validateEmail accepts a normal address and trims whitespace", () => {
  assert.equal(validateEmail("sam@example.com"), "");
  assert.equal(validateEmail("  sam@example.com  "), "");
});

test("validateEmail rejects empty and malformed addresses", () => {
  assert.match(validateEmail(""), /enter your email/i);
  assert.match(validateEmail("   "), /enter your email/i);
  assert.match(validateEmail("sam"), /valid email/i);
  assert.match(validateEmail("sam@example"), /valid email/i);
  assert.match(validateEmail("sam @example.com"), /valid email/i);
});

test("validateNewPassword requires a password", () => {
  assert.match(validateNewPassword("", ""), /enter a new password/i);
});

test("validateNewPassword enforces the minimum length", () => {
  const short = "a".repeat(MIN_PASSWORD_LENGTH - 1);
  assert.match(validateNewPassword(short, short), /at least 8/);

  const ok = "a".repeat(MIN_PASSWORD_LENGTH);
  assert.equal(validateNewPassword(ok, ok), "");
});

test("validateNewPassword enforces bcrypt's 72-byte limit in bytes, not characters", () => {
  const ascii72 = "a".repeat(72);
  assert.equal(validateNewPassword(ascii72, ascii72), "");

  const ascii73 = "a".repeat(73);
  assert.match(validateNewPassword(ascii73, ascii73), /too long/i);

  // 25 three-byte characters = 75 bytes, though only 25 characters.
  const multibyte = "€".repeat(25);
  assert.match(validateNewPassword(multibyte, multibyte), /too long/i);
});

test("validateNewPassword requires the confirmation to match", () => {
  assert.match(validateNewPassword("correct-horse", "correct-horsf"), /do not match/i);
  assert.equal(validateNewPassword("correct-horse", "correct-horse"), "");
});
