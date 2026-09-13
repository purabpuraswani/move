/**
 * Pure data normalization helpers for MoveWell-AI 6-Specialist System.
 * Ensures structured agent output (recommendations, evidence, dosages, actions)
 * is safely formatted without leaking raw objects into React child rendering.
 */

/**
 * Safely normalizes evidence into an array of human-readable strings.
 * Handles: null, undefined, strings, numbers, arrays of strings, arrays of objects,
 * or single objects. Never returns non-renderable objects.
 */
export function normalizeEvidence(rawEvidence) {
  if (!rawEvidence) return [];

  if (typeof rawEvidence === "string") {
    const trimmed = rawEvidence.trim();
    return trimmed ? [trimmed] : [];
  }

  if (typeof rawEvidence === "number") {
    return [String(rawEvidence)];
  }

  if (Array.isArray(rawEvidence)) {
    return rawEvidence
      .map((item) => {
        if (!item) return null;
        if (typeof item === "string") return item.trim();
        if (typeof item === "number") return String(item);

        if (typeof item === "object") {
          // Object with capability + finding (e.g. from need profile findings)
          if (item.capability && item.finding) {
            const evDetails =
              Array.isArray(item.evidence) && item.evidence.length > 0
                ? ` (${item.evidence.join("; ")})`
                : "";
            return `${item.capability}: ${item.finding}${evDetails}`;
          }
          if (item.headline) return String(item.headline);
          if (item.text) return String(item.text);
          if (item.description) return String(item.description);
          if (item.reason) return String(item.reason);
          if (item.name) return String(item.name);
          if (item.label && item.value) return `${item.label}: ${item.value}`;
          if (item.headline) return safeDisplayValue(item.headline);
          if (item.text) return safeDisplayValue(item.text);
          if (item.description) return safeDisplayValue(item.description);
          if (item.reason) return safeDisplayValue(item.reason);
          if (item.name) return safeDisplayValue(item.name);
          if (item.label && item.value) {
            const label = safeDisplayValue(item.label);
            const val = safeDisplayValue(item.value);
            return label && val ? `${label}: ${val}` : label || val;
          }

          // Generic key-value object
          const entries = Object.entries(item)
            .filter(([, v]) => typeof v === "string" || typeof v === "number")
            .map(([k, v]) => `${k}: ${v}`);
          if (entries.length > 0) return entries.join(", ");

          return safeDisplayValue(item);
        }
        return null;
      })
      .filter(Boolean);
  }

  if (typeof rawEvidence === "object") {
    if (rawEvidence.headline) return [String(rawEvidence.headline)];
    if (rawEvidence.text) return [String(rawEvidence.text)];
    if (rawEvidence.description) return [String(rawEvidence.description)];
    if (rawEvidence.reason) return [String(rawEvidence.reason)];
    if (rawEvidence.headline) return [safeDisplayValue(rawEvidence.headline)].filter(Boolean);
    if (rawEvidence.text) return [safeDisplayValue(rawEvidence.text)].filter(Boolean);
    if (rawEvidence.description) return [safeDisplayValue(rawEvidence.description)].filter(Boolean);
    if (rawEvidence.reason) return [safeDisplayValue(rawEvidence.reason)].filter(Boolean);

    const entries = Object.entries(rawEvidence)
      .filter(([, v]) => typeof v === "string" || typeof v === "number")
      .map(([k, v]) => `${k}: ${v}`);
    return entries.length > 0 ? entries : [];
    if (entries.length > 0) return entries;

    const fallback = safeDisplayValue(rawEvidence);
    return fallback ? [fallback] : [];
  }

  return [];
}

/**
 * Converts any value into an array safely.
 * null / undefined -> []
 * array -> shallow copy
 * single item -> [item]
 */
export function toArray(value) {
  if (value == null) return [];
  if (Array.isArray(value)) return [...value];
  return [value];
}

/**
 * Returns a React-safe primitive string or number for display.
 * NEVER returns an object or array.
 * - null / undefined -> null
 * - string -> trimmed string (or null if empty)
 * - number -> number
 * - boolean -> "Yes" / "No"
 * - array -> recursively safe values joined by ", " (or null if empty)
 * - object -> extracts display text using a priority list of common fields
 */
export function safeDisplayValue(value) {
  if (value == null) return null;

  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }

  if (typeof value === "number") {
    return isNaN(value) ? null : value;
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (Array.isArray(value)) {
    const safeItems = value
      .map((v) => safeDisplayValue(v))
      .filter((v) => v != null && v !== "");
    return safeItems.length > 0 ? safeItems.join(", ") : null;
  }

  if (typeof value === "object") {
    // If object has a direct custom string representation or known fields
    const priority = [
      "displayText",
      "title",
      "action",
      "text",
      "label",
      "name",
      "headline",
      "description",
      "message",
      "reason",
      "why",
      "recommendation",
      "value",
      "summary",
    ];

    for (const key of priority) {
      if (key in value && value[key] != null) {
        // Prevent circular recursion if value[key] is the same object
        if (value[key] !== value) {
          const safe = safeDisplayValue(value[key]);
          if (safe != null && safe !== "") return safe;
        }
      }
    }

    // Fallback: extract primitive key-value pairs
    const primitiveEntries = Object.entries(value)
      .filter(([, v]) => typeof v === "string" || typeof v === "number" || typeof v === "boolean")
      .map(([k, v]) => `${k}: ${v}`);

    if (primitiveEntries.length > 0) {
      return primitiveEntries.join(", ");
    }

    return "Additional information available";
  }

  return String(value);
}

/**
 * Normalizes a single recommendation entry into a safe, uniform object with
 * primitive string/number/null fields.
 * Handles:
 *  - string: "Target 6,000 steps"
 *  - standard object: { id, title, action, why }
 *  - exercise object: { id, name, target, sets, repetitions, why, instructions }
 *  - habit object: { topic_id, name, action, why, adherence }
 *  - complex nested objects (e.g. { recommendation: { ... } })
 */
export function normalizeRecommendation(item, index = 0) {
  if (!item) return null;

  if (typeof item === "string" || typeof item === "number" || typeof item === "boolean") {
    const text = safeDisplayValue(item);
    if (!text) return null;
    return {
      id: `rec_${index}`,
      title: String(text),
      action: null,
      why: null,
      target: null,
      difficulty: null,
      sets: null,
      repetitions: null,
      durationSeconds: null,
      instructions: null,
      adherence: null,
      safetyNotes: [],
      isSimpleString: true,
    };
  }

  if (typeof item === "object") {
    let source = item;
    if (item.recommendation && typeof item.recommendation === "object") {
      source = { ...item.recommendation, ...item };
    }

    const id = String(source.id || source.topic_id || source.exercise_id || item.id || `rec_${index}`);

    const rawTitle =
      source.title ||
      source.name ||
      source.recommendation ||
      source.topic ||
      source.action ||
      item.title ||
      item.name ||
      `Recommendation ${index + 1}`;
    const safeTitle = safeDisplayValue(rawTitle);
    const title = safeTitle ? String(safeTitle) : `Recommendation ${index + 1}`;

    const rawAction = source.action || source.instructions || item.action || item.instructions || null;
    const safeAction = safeDisplayValue(rawAction);
    const action = safeAction ? String(safeAction) : null;

    const rawWhy =
      source.why ||
      source.reason ||
      source.rationale ||
      (source.recommendation && typeof source.recommendation === "object" ? source.recommendation.why : null) ||
      item.why ||
      item.reason ||
      item.rationale ||
      null;
    const safeWhy = safeDisplayValue(rawWhy);
    const why = safeWhy ? String(safeWhy) : null;

    const rawTarget = source.target || source.target_need || item.target || item.target_need || null;
    const safeTarget = safeDisplayValue(rawTarget);
    const target = safeTarget ? String(safeTarget) : null;

    const difficulty =
      typeof source.difficulty === "number"
        ? source.difficulty
        : typeof item.difficulty === "number"
        ? item.difficulty
        : null;

    const sets =
      typeof source.sets === "number"
        ? source.sets
        : typeof item.sets === "number"
        ? item.sets
        : null;

    const repetitions =
      typeof source.repetitions === "number"
        ? source.repetitions
        : typeof item.repetitions === "number"
        ? item.repetitions
        : null;

    const durationSeconds =
      typeof source.duration_seconds === "number"
        ? source.duration_seconds
        : typeof source.durationSeconds === "number"
        ? source.durationSeconds
        : typeof item.duration_seconds === "number"
        ? item.duration_seconds
        : typeof item.durationSeconds === "number"
        ? item.durationSeconds
        : null;

    const rawAdherence = source.adherence || item.adherence || null;
    const safeAdherence = safeDisplayValue(rawAdherence);
    const adherence = safeAdherence ? String(safeAdherence) : null;

    let safetyNotes = [];
    const rawSafety = source.safety || source.safetyNotes || item.safety || item.safetyNotes;
    if (Array.isArray(rawSafety)) {
      safetyNotes = rawSafety.map((s) => safeDisplayValue(s)).filter(Boolean);
    } else if (rawSafety != null) {
      const safeSingle = safeDisplayValue(rawSafety);
      if (safeSingle) safetyNotes = [safeSingle];
    }

    return {
      id,
      title,
      action,
      why,
      target,
      difficulty,
      sets,
      repetitions,
      durationSeconds,
      adherence,
      safetyNotes,
      isSimpleString: false,
    };
  }

  return null;
}

/**
 * Normalizes an array of recommendations.
 */
export function normalizeRecommendations(list) {
  if (!list) return [];
  const array = Array.isArray(list) ? list : [list];
  return array.map((item, idx) => normalizeRecommendation(item, idx)).filter(Boolean);
}

/**
 * Tests whether a value is safe to directly render as a primitive React child.
 */
export function isPlainRenderable(value) {
  return typeof value === "string" || typeof value === "number";
}

export const helpers = {
  toArray,
  safeDisplayValue,
  normalizeRecommendation,
  normalizeEvidence,
  normalizeRecommendations,
  isPlainRenderable,
};

