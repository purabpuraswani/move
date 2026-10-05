/**
 * The MoveWell Score dial.
 *
 * One number, drawn once, in SVG. It shows whatever value it is given and
 * nothing when there is no value — it has no idea what "good" means, so it
 * cannot flatter anybody.
 *
 * The arc is drawn from the top clockwise in proportion to the value, with a
 * short reveal animation that is skipped entirely when the reader has asked for
 * reduced motion.
 */

import { useEffect, useState } from "react";

import { safeDisplayValue } from "../../services/specialistData.js";

import "./ScoreDial.css";

const SIZE = 216;
const STROKE = 14;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export default function ScoreDial({
  value = null,
  label = "Your MoveWell Score",
  caption = null,
  size = "large",
}) {
  const hasValue = typeof value === "number" && Number.isFinite(value);
  const clamped = hasValue ? Math.max(0, Math.min(100, value)) : 0;

  // The reveal: start at zero and grow to the real value on mount. Never the
  // other way round — a dial that animates down to a real score would read as a
  // loss the user never had.
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (!hasValue) return undefined;

    const frame = requestAnimationFrame(() => setShown(clamped));

    return () => cancelAnimationFrame(frame);
  }, [hasValue, clamped]);

  const progress = hasValue ? shown / 100 : 0;

  return (
    <figure className={`score-dial score-dial--${size}${hasValue ? "" : " score-dial--empty"}`}>
      <div className="score-dial-ring">
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          role="img"
          aria-label={
            hasValue
              ? `${label}: ${clamped} out of 100`
              : `${label}: not available yet`
          }
        >
          <circle
            className="score-dial-track"
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            strokeWidth={STROKE}
            fill="none"
          />
          {hasValue ? (
            <circle
              className="score-dial-arc"
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              strokeWidth={STROKE}
              fill="none"
              strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={CIRCUMFERENCE * (1 - progress)}
            />
          ) : null}
        </svg>

        <div className="score-dial-centre">
          {hasValue ? (
            <>
              <span className="score-dial-value">{clamped}</span>
              <span className="score-dial-scale">/ 100</span>
            </>
          ) : (
            <span className="score-dial-none">Not measured yet</span>
          )}
        </div>
      </div>

      <figcaption className="score-dial-caption">
        <span className="score-dial-label">{safeDisplayValue(label)}</span>
        {caption ? <span className="score-dial-note">{safeDisplayValue(caption)}</span> : null}
      </figcaption>
    </figure>
  );
}
