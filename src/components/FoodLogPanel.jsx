/**
 * Recording what you actually ate.
 *
 * Four fields, one of them optional, and no arithmetic. The user is never
 * asked for grams, calories or macros: nutrient values in this project come
 * from defined sources (IFCT 2017 for Indian food composition, ICMR-NIN 2024
 * for dietary guidance, with Open Food Facts and USDA FoodData Central as
 * secondary), and a number typed into a browser field is not one of them.
 * Quantity is free text — "1 bowl", "2 rotis", "half a plate" — because that
 * is how people actually remember meals.
 *
 * An empty log is never presented as a failure. The server distinguishes
 * NOT_LOGGED from NOT_ADHERED, and this panel keeps that distinction in the
 * words it uses: nothing here tells a user they did badly because they did not
 * write something down.
 */

import { useCallback, useEffect, useState } from "react";

import { MEALS, MEAL_LABELS, fetchFoodLog, logFood } from "../services/foodLog";

import "./FoodLogPanel.css";

function formatWhen(value) {
  if (!value) return "";

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) return "";

  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function FoodLogPanel({ planAvailable = false, planId = null, onMealLogged = null, className = "" }) {
  const [meal, setMeal] = useState("breakfast");
  const [foodName, setFoodName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [notes, setNotes] = useState("");

  const [entries, setEntries] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    if (typeof window !== "undefined" && window.__mockFoodEntries) {
      setEntries(window.__mockFoodEntries);
      return;
    }

    try {
      const page = await fetchFoodLog({ limit: 8 });

      setEntries(page.entries || []);
    } catch {
      // A failure to load history must not stop the user recording something
      // new — the form below is independently useful.
      setEntries([]);
    }
  }, []);

  useEffect(() => {
    let ignore = false;

    if (typeof window !== "undefined" && window.__mockFoodEntries) {
      setEntries(window.__mockFoodEntries);
      return;
    }

    fetchFoodLog({ limit: 8 })
      .then((page) => {
        if (!ignore) {
          setEntries(page.entries || []);
        }
      })
      .catch(() => {
        if (!ignore) {
          setEntries([]);
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    window.__setMockFoodEntries = (mockList) => {
      window.__mockFoodEntries = mockList;
      setEntries(mockList);
    };
    return () => {
      delete window.__setMockFoodEntries;
    };
  }, []);

  const submit = useCallback(
    async (event) => {
      event.preventDefault();

      if (!foodName.trim()) {
        setError("Please say what you ate.");

        return;
      }

      setSaving(true);
      setError(null);
      setSaved(false);

      try {
        await logFood({
          meal,
          foodName: foodName.trim(),
          quantity: quantity.trim(),
          notes,
          planId,
        });

        setFoodName("");
        setQuantity("");
        setNotes("");
        setSaved(true);

        if (typeof onMealLogged === "function") {
          onMealLogged({ meal, foodName: foodName.trim(), quantity: quantity.trim() });
        }

        await load();
      } catch (saveError) {
        setError(saveError.message);
      } finally {
        setSaving(false);
      }
    },
    [meal, foodName, quantity, notes, planId, load, onMealLogged],
  );

  return (
    <section className={`foodlog ${className}`}>
      <div className="foodlog-head">
        <h3 className="foodlog-title">Log your food</h3>
        <p className="foodlog-blurb">
          {planAvailable
            ? "Record what you eat to help your Nutrition specialist understand your daily habits and calibrate recommendations."
            : "Record meals whenever you like to track your eating pattern."}
        </p>
      </div>

      <div className="foodlog-coaching-notice">
        <span className="foodlog-notice-icon">ℹ</span>
        <span className="foodlog-notice-text">
          Logged meals provide real evidence for your Nutrition specialist to review meal regularity and dietary variety over time. MoveWell does not invent calories or macros from rough descriptions; nutritional analysis will calibrate as verified data is available.
        </span>
      </div>

      <form className="foodlog-form" onSubmit={submit}>
        <div className="foodlog-meals" role="group" aria-label="Meal">
          {MEALS.map((option) => (
            <button
              key={option}
              type="button"
              className={
                option === meal
                  ? "foodlog-meal foodlog-meal--on"
                  : "foodlog-meal"
              }
              onClick={() => setMeal(option)}
              aria-pressed={option === meal}
            >
              {MEAL_LABELS[option]}
            </button>
          ))}
        </div>

        <div className="foodlog-field">
          <label className="foodlog-label" htmlFor="foodlog-food">
            What did you eat?
          </label>
          <input
            id="foodlog-food"
            className="foodlog-input"
            value={foodName}
            onChange={(event) => setFoodName(event.target.value)}
            placeholder="Poha, dal and rice, two eggs…"
            maxLength={200}
          />
        </div>

        <div className="foodlog-field">
          <label className="foodlog-label" htmlFor="foodlog-quantity">
            Roughly how much?
          </label>
          <input
            id="foodlog-quantity"
            className="foodlog-input"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            placeholder="1 bowl, 2 rotis, half a plate…"
            maxLength={200}
          />
        </div>

        <div className="foodlog-field">
          <label className="foodlog-label" htmlFor="foodlog-notes">
            Anything to add? <span className="foodlog-optional">Optional</span>
          </label>
          <input
            id="foodlog-notes"
            className="foodlog-input"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Ate late, was travelling…"
            maxLength={500}
          />
        </div>

        {error ? <p className="foodlog-error">{error}</p> : null}
        {saved && !error ? (
          <p className="foodlog-saved">
            ✓ Meal recorded! Added to your nutrition timeline for your specialist's review.
          </p>
        ) : null}

        <button type="submit" className="foodlog-submit" disabled={saving}>
          {saving ? "Saving…" : "Add to log"}
        </button>
      </form>

      {entries.length > 0 ? (
        <div className="foodlog-recent">
          <h4 className="foodlog-recent-title">Recently logged meals</h4>
          <ul className="foodlog-list">
            {entries.map((entry) => (
              <li key={entry.id || entry.entry_id} className="foodlog-entry">
                <div className="foodlog-entry-primary">
                  <span className="foodlog-entry-meal">
                    {MEAL_LABELS[entry.meal] || entry.meal}
                  </span>
                  <span className="foodlog-entry-food">{entry.food_name}</span>
                  {entry.quantity ? (
                    <span className="foodlog-entry-quantity">({entry.quantity})</span>
                  ) : null}
                </div>
                <div className="foodlog-entry-meta">
                  <span className="foodlog-entry-when">
                    {formatWhen(entry.recorded_at)}
                  </span>
                  <span className="foodlog-entry-status">Recorded for review</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="foodlog-empty-box">
          <p className="foodlog-none">
            Nothing logged yet. There is no catching up to do — start whenever
            you like.
          </p>
        </div>
      )}
    </section>
  );
}

export default FoodLogPanel;
