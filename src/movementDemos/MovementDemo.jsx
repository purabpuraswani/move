/**
 * MovementDemo — the one renderer for every movement demonstration.
 *
 * Phase 0 foundation: this component proves the data-driven interface works
 * (steps through `phases`, shows instructions/keyPoints/commonMistakes) and
 * draws a deliberately simple, abstract figure for the one pose shape it
 * currently understands (a symmetric or per-side arm angle). It does not yet
 * contain the polished, reviewed demonstrations for the three baseline tests
 * or any of the ten exercises — those are authored later as data (see
 * registry.js) once a healthcare/physio reviewer has signed off on the
 * technique each one shows, per the project's safety principle.
 *
 * Extending this component to draw a sit-to-stand transition or a
 * single-leg stance is later-phase work. The interface it should keep
 * satisfying is the one in schema.js: read `phases`, render whatever a
 * phase's `pose` describes, advance on `holdSeconds`. Adding a new pose
 * shape means adding a new small drawing function here, not a new
 * component and not a new consumer-facing API.
 *
 * Deliberately absent from this file, and from everything it renders:
 * MoveNet, TensorFlow, "pose estimation", "keypoints", "AI", "agent", "MCP",
 * or any other implementation detail. A user watching this sees a clean
 * illustration and plain-language text, nothing about how the assessment
 * that follows is measured.
 */

import { useEffect, useMemo, useState } from "react";

import { validateMovementDemo } from "./schema.js";
import "./MovementDemo.css";

// 0deg = at rest, 90deg = perpendicular to the body. Every "pivot from a
// joint by an angle" helper below shares this convention so the numbers in
// a phase's pose read the same way regardless of which limb they describe.
function pointFrom(originX, originY, deg, length, direction = 1) {
  const rad = (deg * Math.PI) / 180;
  return {
    x: originX + Math.sin(rad) * length * direction,
    y: originY + Math.cos(rad) * length,
  };
}

/**
 * A minimal, abstract figure. Style lives in MovementDemo.css.
 *
 * Draws additively from whichever fields a phase's pose provides (see the
 * vocabulary documented in schema.js) — an unfamiliar field is simply
 * ignored, so a demo authored with a subset of fields still renders a valid,
 * if plainer, figure instead of failing.
 */
function StickFigure({ pose }) {
  const p = pose || {};
  const sitting = p.stance === "sitting";
  const lean = p.leanDeg ?? 0;

  // Hip position moves down and the torso shortens/leans when sitting or
  // leaning (a squat's low point, a push-up's lean into a wall).
  const hip = sitting
    ? { x: 50, y: 62 }
    : pointFrom(50, 27, lean, 35, 1);
  const shoulder = { x: 50, y: 27 };

  const leftArmDeg = p.armAngleDeg?.left ?? p.armBendDeg?.left ?? 0;
  const rightArmDeg = p.armAngleDeg?.right ?? p.armBendDeg?.right ?? 0;
  const armLength = p.armBendDeg ? 20 : 32;
  const leftArmEnd = pointFrom(shoulder.x, shoulder.y + 19, leftArmDeg, armLength, -1);
  const rightArmEnd = pointFrom(shoulder.x, shoulder.y + 19, rightArmDeg, armLength, 1);

  // Legs: a plain standing pair by default, replaced by whichever
  // single-leg variant the pose describes. Only one of these fields is
  // expected on a given phase; the first one present wins.
  let legs = (
    <>
      <line className="movement-demo__figure-limb" x1={hip.x} y1={hip.y} x2={hip.x - 12} y2={sitting ? hip.y + 4 : 112} />
      {sitting && (
        <line className="movement-demo__figure-limb" x1={hip.x - 12} y1={hip.y + 4} x2={hip.x - 12} y2={112} />
      )}
      <line className="movement-demo__figure-limb" x1={hip.x} y1={hip.y} x2={hip.x + 12} y2={sitting ? hip.y + 4 : 112} />
      {sitting && (
        <line className="movement-demo__figure-limb" x1={hip.x + 12} y1={hip.y + 4} x2={hip.x + 12} y2={112} />
      )}
    </>
  );

  if (p.legLift) {
    const raised = p.legLift.side === "left" ? -1 : 1;
    const knee = pointFrom(hip.x, hip.y, 40 * raised, 18, 1);
    const foot = pointFrom(knee.x, knee.y, p.legLift.liftAngleDeg ?? 40, 16, raised);
    const standingSide = raised === 1 ? -12 : 12;
    legs = (
      <>
        <line className="movement-demo__figure-limb" x1={hip.x} y1={hip.y} x2={hip.x + standingSide} y2={112} />
        <line className="movement-demo__figure-limb" x1={hip.x} y1={hip.y} x2={knee.x} y2={knee.y} />
        <line className="movement-demo__figure-limb" x1={knee.x} y1={knee.y} x2={foot.x} y2={foot.y} />
      </>
    );
  } else if (p.sideLegLift) {
    const raised = p.sideLegLift.side === "left" ? -1 : 1;
    const foot = pointFrom(hip.x, hip.y, p.sideLegLift.liftAngleDeg ?? 30, 30, raised);
    const standingSide = raised === 1 ? -12 : 12;
    legs = (
      <>
        <line className="movement-demo__figure-limb" x1={hip.x} y1={hip.y} x2={hip.x + standingSide} y2={112} />
        <line className="movement-demo__figure-limb" x1={hip.x} y1={hip.y} x2={foot.x} y2={foot.y} />
      </>
    );
  } else if (p.hipExtension) {
    const raised = p.hipExtension.side === "left" ? -1 : 1;
    const foot = pointFrom(hip.x, hip.y, p.hipExtension.liftAngleDeg ?? 25, 30, raised * -1);
    const standingSide = raised === 1 ? -12 : 12;
    legs = (
      <>
        <line className="movement-demo__figure-limb" x1={hip.x} y1={hip.y} x2={hip.x + standingSide} y2={112} />
        <line className="movement-demo__figure-limb" x1={hip.x} y1={hip.y} x2={foot.x} y2={foot.y} />
      </>
    );
  } else if (p.tandemStance) {
    legs = (
      <>
        <line className="movement-demo__figure-limb" x1={hip.x} y1={hip.y} x2={hip.x - 2} y2={98} />
        <line className="movement-demo__figure-limb" x1={hip.x} y1={hip.y} x2={hip.x + 2} y2={112} />
      </>
    );
  } else if (p.heelRaiseDeg) {
    const lift = Math.min(p.heelRaiseDeg, 30) / 30;
    legs = (
      <>
        <line className="movement-demo__figure-limb" x1={hip.x} y1={hip.y} x2={hip.x - 12} y2={112 - lift * 6} />
        <line className="movement-demo__figure-limb" x1={hip.x} y1={hip.y} x2={hip.x + 12} y2={112 - lift * 6} />
      </>
    );
  }

  return (
    <svg
      className="movement-demo__figure"
      viewBox="0 0 100 120"
      role="img"
      aria-label="Illustration of the movement"
    >
      <circle className="movement-demo__figure-head" cx={shoulder.x} cy="18" r="9" />
      <line className="movement-demo__figure-torso" x1={shoulder.x} y1={shoulder.y} x2={hip.x} y2={hip.y} />
      <line className="movement-demo__figure-limb" x1={shoulder.x} y1={shoulder.y + 19} x2={leftArmEnd.x} y2={leftArmEnd.y} />
      <line className="movement-demo__figure-limb" x1={shoulder.x} y1={shoulder.y + 19} x2={rightArmEnd.x} y2={rightArmEnd.y} />
      {sitting && (
        <line className="movement-demo__figure-chair" x1="30" y1={hip.y + 4} x2="70" y2={hip.y + 4} />
      )}
      {legs}
    </svg>
  );
}

/**
 * Renders one movement demonstration: a looping, steppable sequence of
 * phases with plain-language instructions alongside it.
 *
 * `demo` must satisfy the shape in schema.js. `autoPlay` (default true)
 * advances through phases on their own `holdSeconds`; a viewer can always
 * step manually with the Previous/Next controls regardless.
 */
export default function MovementDemo({ demo, autoPlay = true }) {
  useMemo(() => validateMovementDemo(demo), [demo]);

  const [phaseIndex, setPhaseIndex] = useState(0);
  const [renderedMovementId, setRenderedMovementId] = useState(demo.movementId);

  // Reset to the first phase when the demo being shown changes, without a
  // separate effect: adjusting state during render, keyed on a value derived
  // from props, is the pattern React recommends for "state that resets when
  // a prop changes" instead of synchronising it after the fact in an effect.
  if (demo.movementId !== renderedMovementId) {
    setRenderedMovementId(demo.movementId);
    setPhaseIndex(0);
  }

  const phase = demo.phases[phaseIndex];

  useEffect(() => {
    if (!autoPlay) {
      return undefined;
    }

    const timer = setTimeout(() => {
      setPhaseIndex((current) => (current + 1) % demo.phases.length);
    }, phase.holdSeconds * 1000);

    return () => clearTimeout(timer);
  }, [autoPlay, phase, demo.phases.length]);

  return (
    <div className="movement-demo">
      <div className="movement-demo__stage">
        <StickFigure pose={phase.pose} />
      </div>

      <div className="movement-demo__phase-label">{phase.label}</div>

      <div className="movement-demo__dots" role="tablist" aria-label="Movement phases">
        {demo.phases.map((step, index) => (
          <button
            key={step.id}
            type="button"
            role="tab"
            aria-selected={index === phaseIndex}
            className={
              index === phaseIndex
                ? "movement-demo__dot movement-demo__dot--active"
                : "movement-demo__dot"
            }
            onClick={() => setPhaseIndex(index)}
          >
            <span className="movement-demo__dot-sr">{step.label}</span>
          </button>
        ))}
      </div>

      {demo.instructions.length > 0 && (
        <ol className="movement-demo__list">
          {demo.instructions.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ol>
      )}

      {demo.keyPoints.length > 0 && (
        <ul className="movement-demo__list movement-demo__list--key-points">
          {demo.keyPoints.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
