/**
 * One line chart for one recorded series.
 *
 * Draws nothing unless the series is plottable. A single recorded point
 * is shown as a stated figure with a short note, never as a line — a
 * line through one point implies a direction of travel the data does
 * not contain.
 *
 * The SVG uses a fixed viewBox and `width: 100%`, so it scales to the
 * container on phone and desktop without measuring anything.
 */

import {
  VIEWBOX_HEIGHT,
  VIEWBOX_WIDTH,
  PADDING,
  axisLabels,
  isPlottable,
  linePath,
  plotPoints,
} from "./chartGeometry.js";

function valuesOf(series) {
  return (series.points || []).map((point) =>
    typeof point.value === "number" ? point.value : point.total,
  );
}

export default function ProgressLineChart({ series, title, unit = "", emptyNote }) {
  const points = series?.points || [];
  const values = series ? valuesOf(series) : [];

  if (!points.length) {
    return (
      <div className="progress-chart">
        <h3 className="progress-chart-title">{title}</h3>
        <p className="progress-chart-empty">
          {emptyNote || "Nothing recorded yet."}
        </p>
      </div>
    );
  }

  if (!isPlottable(series)) {
    const only = points[points.length - 1];

    return (
      <div className="progress-chart">
        <h3 className="progress-chart-title">{title}</h3>
        <p className="progress-chart-single">
          <strong>
            {values[values.length - 1]}
            {unit ? ` ${unit}` : ""}
          </strong>
          {only.date ? <span className="progress-chart-single-date"> on {only.date}</span> : null}
        </p>
        <p className="progress-chart-empty">
          Your progress trend will appear after more sessions are recorded.
        </p>
      </div>
    );
  }

  const plotted = plotPoints(values);
  const path = linePath(values);
  const labels = axisLabels(series);

  return (
    <div className="progress-chart">
      <h3 className="progress-chart-title">{title}</h3>

      <svg
        className="progress-chart-svg"
        viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`${title}: ${points.length} recorded points from ${labels.firstDate} to ${labels.lastDate}`}
      >
        {/* Baseline and top rule, so the line has something to read against. */}
        <line
          className="progress-chart-axis"
          x1={PADDING.left}
          y1={VIEWBOX_HEIGHT - PADDING.bottom}
          x2={VIEWBOX_WIDTH - PADDING.right}
          y2={VIEWBOX_HEIGHT - PADDING.bottom}
        />
        <line
          className="progress-chart-gridline"
          x1={PADDING.left}
          y1={PADDING.top}
          x2={VIEWBOX_WIDTH - PADDING.right}
          y2={PADDING.top}
        />

        <path className="progress-chart-line" d={path} />

        {plotted.map((point, index) => (
          <circle
            key={index}
            className="progress-chart-dot"
            cx={point.x}
            cy={point.y}
            r="4"
          />
        ))}
      </svg>

      <div className="progress-chart-scale">
        <span>
          {labels.min}
          {unit ? ` ${unit}` : ""} – {labels.max}
          {unit ? ` ${unit}` : ""}
        </span>
        <span>
          {labels.firstDate} → {labels.lastDate}
        </span>
      </div>
    </div>
  );
}
