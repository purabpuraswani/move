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

function FoodLogPanel({ planAvailable = false, planId = null }) {
  const [meal, setMeal] = useState("breakfast");
  const [foodName, setFoodName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [notes, setNotes] = useState("");

  const [entries, setEntries] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
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

        await load();
      } catch (saveError) {
        setError(saveError.message);
      } finally {
        setSaving(false);
      }
    },
    [meal, foodName, quantity, notes, planId, load],
  );

  return (
    <section className="foodlog">
      <h2 className="foodlog-title">Food log</h2>
      <p className="foodlog-blurb">
        {planAvailable
          ? "Recording meals is what makes the nutrition side of your plan able to change with you."
          : "You can record meals whenever you like, whether or not you have a nutrition plan."}
      </p>

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

        {error ? <p className="foodlog-error">{error}</p> : null}
        {saved && !error ? <p className="foodlog-saved">Saved.</p> : null}

        <button type="submit" className="foodlog-submit" disabled={saving}>
          {saving ? "Saving…" : "Add to log"}
        </button>
      </form>

      {entries.length > 0 ? (
        <div className="foodlog-recent">
          <h3 className="foodlog-recent-title">Recently logged</h3>
          <ul className="foodlog-list">
            {entries.map((entry) => (
              <li key={entry.id || entry.entry_id} className="foodlog-entry">
                <span className="foodlog-entry-meal">
                  {MEAL_LABELS[entry.meal] || entry.meal}
                </span>
                <span className="foodlog-entry-food">{entry.food_name}</span>
                {entry.quantity ? (
                  <span className="foodlog-entry-quantity">{entry.quantity}</span>
                ) : null}
                <span className="foodlog-entry-when">
                  {formatWhen(entry.recorded_at)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="foodlog-none">
          Nothing logged yet. There is no catching up to do — start whenever
          you like.
        </p>
      )}
    </section>
  );
}

export default FoodLogPanel;
