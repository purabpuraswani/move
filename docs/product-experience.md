# The MoveWell product experience

How the interface is put together after the product remodel: the four sections, the
design language, the journey a person actually walks, and the one number the app is
organised around.

This document is about the **user-facing layer**. The backend it sits on is
described in `docs/architecture.md`, the specialists and the plan contract in
`docs/five-specialists-and-unified-plan.md`. Nothing here changes what any of them
compute.

## 1. Four sections

The navigation is four items, and nothing else is a section:

| Section | Route | Answers |
| --- | --- | --- |
| **Today** | `/today` | How am I doing? What matters now? What do I do today? |
| **Plan** | `/plan` | What do I need to do? |
| **Progress** | `/progress` | Am I improving? What changed? |
| **You** | `/you` | My information, health, reports, past sessions |

Everything that used to be a top-level item now lives inside one of those four:
the assessment is part of the journey (`/assessment` → `/results`), the nutrition
check-in appears where nutrition is missing (`/nutrition-check-in`), a specialist's
own screen is reached from the team or the plan (`/specialist/:id`), and reports,
past sessions and the internal dashboard sit under **You**.

`/dashboard` and `/profile` are kept as aliases of `/today` and `/you`, so every
existing link, bookmark and redirect still lands somewhere real. The internal
dashboard (`/internal/dashboard`) is not part of the product and is not linked from
it. The legacy two-agent guidance page and the old dashboard component were deleted
rather than left reachable: they described a product that no longer exists.

## 2. The design language

`src/index.css` holds it. One warm off-white background, white cards, near-black
text, exactly one accent colour, generous spacing, large radii, shadows used for
lift rather than decoration, and motion that is short and switched off entirely
under `prefers-reduced-motion`.

The previous identity was a dark green console. It read as engineering rather than
health, so the tokens were replaced rather than adjusted — but the old token names
(`--dark`, `--green`, `--mint`, `--surface-soft` …) are kept and **re-pointed** at
the light values, so the older stylesheets land on the new identity instead of each
needing a rewrite.

Shared building blocks live in `src/components/ui/`:

| File | What it owns |
| --- | --- |
| `AppShell.jsx` | the top bar, the four sections, the mobile tab bar |
| `ScoreDial.jsx` | the score dial, and nothing about what a score means |
| `primitives.jsx` | `PageHeader`, `SectionHeader`, `PrimaryButton`, `StatusBadge`, `EmptyState`, `DetailDrawer`, `Field` |

A page built from these cannot invent a second page header, a second empty state or
a second button style — which is what makes the product look like one product.

## 3. The MoveWell Score

Every other number in MoveWell is a measurement: an arm elevation in degrees, a
sit-to-stand time, a hold in seconds. The score exists because nobody can hold six
of those in their head and tell whether they are getting better.

`backend/workflow/score.py` builds it, and it is a **restatement**, not a new
assessment:

```
need score 0.00 -> 100   (nothing in this domain needs attention)
need score 1.00 ->   0   (this domain is at the far end of MoveWell's own markers)
```

Each domain's need score is already computed by `need_assessment` from a real
measurement or a real answer. The score inverts it for presentation and averages
the domains that were actually assessed. It introduces no threshold of its own.

The rules that keep it honest, each with a test:

* **An unassessed domain has no value at all** — `null`, not zero. "We do not know"
  must never look like "you scored badly".
* **The headline number needs a measurement.** A score built only from
  questionnaire answers would read as a health score while being a summary of what
  somebody typed, so it is not shown; the answered domains still show their own
  values, and the dial says the assessment is what is missing.
* **The band wording comes from the levels**, not from new cut points on 0–100.
* **The change is null when there is nothing to compare**, and a genuine zero is
  kept as a zero. "No change measured" and "no previous measurement" are different
  statements.
* **The method travels with the number**, because a number a person is asked to
  follow should come with where it came from.

The previous score is not stored. It is rebuilt from the previous assessment
session through the same machinery (`routes/workflow.py::previous_score_for_user`),
so it can never drift from what that same evidence would produce today.

## 4. The journey

```
YOU (profile)                    /you, /onboarding
  -> three movement checks       /assessment
  -> YOUR MOVEWELL SCORE         /results      score, domains, what matters most
  -> YOUR TEAM                   /results      the specialists the results called for
  -> ONE PLAN                    /plan         actions first
  -> ACT                         /exercise/:id, habits, food log
  -> TRACK                       /progress     what you completed, what moved
  -> REASSESS                    /assessment   again, later
  -> the plan updates            /results      and says whether it changed
```

`/results` is where the loop closes visibly: it reports the score, what it means,
which specialists the results brought in, and — only when the server itself
recorded an adaptation reason — that the plan has been updated. When nothing
changed, it says so, because "your plan was updated" printed unconditionally would
be a claim the backend did not make.

Moving between screens is the only place the client decides anything. Every value,
status, reason and sentence comes from the server; the client chooses how to show
it.

## 5. What the user never sees

The interface shows value, not implementation. Not rendered anywhere in the
product: orchestrator or agent vocabulary, MCP, workflow/plan/item identifiers, raw
need scores, keypoints, angles, confidence values, prompts, model reasoning, JSON,
or evidence structures in a primary view. Secondary detail is real and available —
behind a `View details` disclosure that is a plain `<details>` element, so it is
keyboard-operable and announced without any JavaScript of ours.

Honesty rules the screens are built to:

* An empty state says what is missing, why it matters, and what to do. The
  `EmptyState` primitive takes all three, so a screen cannot ship only the first.
* No fabricated trend, participation, focus or score. A specialist that was not
  selected renders as not selected, with the action that would assess it if the
  person wants it.
* Safety stays visible and never diagnoses: ALLOW is a quiet line, MODIFY a clear
  explanation, PAUSE and REFER prominent, and MoveWell never claims to replace a
  doctor, physiotherapist or nutritionist.

## 6. Verifying it

```bash
cd backend && python -m unittest discover -s tests -t .   # 1182 tests
cd backend && python verify_adaptive_loop.py              # 118 live checks
npm test                                                  # 417 frontend tests
npm run build
npm run test:render                                       # real SSR render
```

`verify_adaptive_loop.py` section 10 is the score: that a measured account has one
and on the right scale, that its focus is the domain with the lowest value, that
the number is the average of what was assessed, that a first assessment reports no
change rather than a zero, that a second assessment produces a real previous value
and a real difference, and that an account which has measured nothing has no score
at all.
