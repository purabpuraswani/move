/**
 * One specialist, as the user meets them.
 *
 * This component renders what a specialist actually found, decided and is
 * watching — and it writes none of it. Every sentence here comes from the
 * server's `specialists` block (backend/workflow/response.py), which is
 * itself assembled from the persisted agent output: Need Assessment's own
 * evidence strings, the Physio Agent's own per-exercise rationale, the
 * exercise library's own progression and safety text, and the decision
 * types the agent recorded. The only strings this file contributes are
 * section headings.
 *
 * That constraint is the point. The previous Movement section was three
 * cards with a set count, and the only way to make it say more would have
 * been to write the explanation in React — which would have meant the app
 * telling the user a reason no agent ever gave. A field the server did not
 * send is omitted here rather than filled in.
 *
 * The same component renders all three specialists. Movement has a
 * programme of exercises to perform; Nutrition and Daily habits have a
 * focus list instead, because that is genuinely what those agents record —
 * shaping the UI around what exists rather than around what would look
 * symmetrical.
 */

import "./SpecialistPanel.css";

function Section({ title, children }) {
  if (!children) return null;

  return (
    <section className="specialist-block">
      <h3 className="specialist-block-title">{title}</h3>
      {children}
    </section>
  );
}

/**
 * One assessment finding: what was looked at, what came back, and the
 * measurement behind it. "Not measured" is shown as its own state, never as
 * a low score — the distinction the whole system is built to preserve.
 */
function Finding({ finding }) {
  return (
    <li
      className={
        finding.measured
          ? "specialist-finding"
          : "specialist-finding specialist-finding--unmeasured"
      }
    >
      <div className="specialist-finding-head">
        <span className="specialist-finding-name">{finding.capability}</span>
        <span className="specialist-finding-verdict">{finding.finding}</span>
      </div>
      {finding.evidence?.length ? (
        <ul className="specialist-evidence">
          {finding.evidence.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function prescriptionOf(exercise) {
  const parts = [];

  if (exercise.sets) parts.push(`${exercise.sets} sets`);
  if (exercise.repetitions) parts.push(`${exercise.repetitions} reps`);
  if (exercise.duration_seconds) {
    parts.push(`${exercise.duration_seconds} seconds`);
  }

  return parts.join(" · ") || null;
}

function ExerciseCard({ exercise, onStart }) {
  return (
    <li className="specialist-exercise">
      <div className="specialist-exercise-head">
        <div>
          <span className="specialist-exercise-name">{exercise.name}</span>
          {exercise.target ? (
            <span className="specialist-exercise-target">{exercise.target}</span>
          ) : null}
        </div>
        {exercise.change && exercise.change !== "Added" ? (
          <span className="specialist-tag">{exercise.change}</span>
        ) : null}
      </div>

      {exercise.why ? (
        <p className="specialist-exercise-why">{exercise.why}</p>
      ) : null}

      <dl className="specialist-exercise-facts">
        {prescriptionOf(exercise) ? (
          <div>
            <dt>Do</dt>
            <dd>{prescriptionOf(exercise)}</dd>
          </div>
        ) : null}
        {exercise.difficulty ? (
          <div>
            <dt>Level</dt>
            <dd>{exercise.difficulty}</dd>
          </div>
        ) : null}
        {exercise.watching?.length ? (
          <div>
            <dt>Watched</dt>
            <dd>{exercise.watching.join(", ")}</dd>
          </div>
        ) : null}
      </dl>

      {exercise.safety?.length ? (
        <ul className="specialist-safety">
          {exercise.safety.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}

      {exercise.progression || exercise.regression ? (
        <div className="specialist-steps">
          {exercise.progression ? (
            <p>
              <span className="specialist-step-label">To make it harder</span>
              {exercise.progression}
            </p>
          ) : null}
          {exercise.regression ? (
            <p>
              <span className="specialist-step-label">To make it easier</span>
              {exercise.regression}
            </p>
          ) : null}
        </div>
      ) : null}

      {/* The demonstration lives on the exercise page itself, ahead of the
          camera step, so this is one button rather than two that land in
          the same place. */}
      <button
        type="button"
        className="specialist-start"
        onClick={() => onStart(exercise.id)}
      >
        Watch and start
      </button>
    </li>
  );
}

function SpecialistPanel({
  specialist,
  onStartExercise = null,
  // Rendered directly under "Today". Used by the habits specialist to put
  // the record-an-action control where the action itself is described,
  // rather than in a separate place the user has to go and find.
  actionSlot = null,
}) {
  if (!specialist) return null;

  const {
    title,
    goal,
    what_i_found: findings = [],
    working_on: workingOn = [],
    why_this_programme: whyProgramme,
    why_involved: whyInvolved,
    programme = [],
    focus_items: focusItems = [],
    today = [],
    need_from_you: needFromYou = [],
    learning = [],
    watching = [],
    changes = [],
    plan_version: planVersion,
    next_review: nextReview,
  } = specialist;

  return (
    <article className="specialist">
      <header className="specialist-head">
        <div>
          <span className="specialist-eyebrow">Specialist</span>
          <h2 className="specialist-title">{title}</h2>
        </div>
        {planVersion ? (
          <span className="specialist-version">v{planVersion}</span>
        ) : null}
      </header>

      {goal ? <p className="specialist-goal">{goal}</p> : null}

      <Section title="What I found">
        {findings.length ? (
          <ul className="specialist-findings">
            {findings.map((finding) => (
              <Finding key={finding.capability} finding={finding} />
            ))}
          </ul>
        ) : null}
      </Section>

      <Section title="What we're working on">
        {workingOn.length ? (
          <ul className="specialist-chips">
            {workingOn.map((item) => (
              <li key={item} className="specialist-chip">
                {item}
              </li>
            ))}
          </ul>
        ) : null}
      </Section>

      <Section title="Why this">
        {whyProgramme || whyInvolved ? (
          <p className="specialist-text">{whyProgramme || whyInvolved}</p>
        ) : null}
      </Section>

      <Section title="Your programme">
        {programme.length ? (
          <ul className="specialist-exercises">
            {programme.map((exercise) => (
              <ExerciseCard
                key={exercise.id}
                exercise={exercise}
                onStart={onStartExercise || (() => {})}
              />
            ))}
          </ul>
        ) : null}
      </Section>

      {/* Nutrition and habits have goals to follow rather than exercises
          to perform, so they show the action, the reason, and what is known
          about following it -- including, explicitly, when nothing is
          known. */}
      <Section title="Your focus">
        {focusItems.length ? (
          <ul className="specialist-goals">
            {focusItems.map((item) => (
              <li key={item.name} className="specialist-goal">
                <span className="specialist-goal-name">{item.name}</span>
                {item.action ? (
                  <span className="specialist-goal-action">{item.action}</span>
                ) : null}
                {item.why ? (
                  <span className="specialist-goal-why">{item.why}</span>
                ) : null}
                {item.adherence ? (
                  <span className="specialist-goal-status">{item.adherence}</span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </Section>

      {/* The concrete thing to do now. Taken from the goals' own practical
          wording, so it is the same sentence the library and the agent
          used -- not a restatement written here. */}
      <Section title="Today">
        {today.length ? (
          <ul className="specialist-today">
            {today.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}
      </Section>

      {actionSlot}

      {/* What the specialist is missing. This is how a user learns that
          "not enough evidence" is about what has been recorded, not about
          them. */}
      <Section title="What I need from you">
        {needFromYou.length ? (
          <ul className="specialist-asks">
            {needFromYou.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}
      </Section>

      <Section title="What I'm watching">
        {watching.length ? (
          <ul className="specialist-watching">
            {watching.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}
      </Section>

      {/* What it has actually learned. When nothing has been recorded the
          section says so, rather than being filled with something that
          sounds like a finding. */}
      <Section title="What I'm learning">
        {learning.length ? (
          <ul className="specialist-learning">
            {learning.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="specialist-text specialist-text--quiet">
            Nothing recorded for this yet.
          </p>
        )}
      </Section>

      <Section title="What changed">
        {changes.length ? (
          <ul className="specialist-changes">
            {changes.map((change, index) => (
              <li key={`${change.exercise}-${index}`}>
                <span className="specialist-change-what">
                  {change.exercise
                    ? `${change.exercise} — ${change.change}`
                    : change.change}
                </span>
                {change.reason ? (
                  <span className="specialist-change-why">{change.reason}</span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </Section>

      <Section title="What happens next">
        {nextReview ? <p className="specialist-text">{nextReview}</p> : null}
      </Section>
    </article>
  );
}

export default SpecialistPanel;
