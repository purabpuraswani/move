/**
 * A second view of the camera the pose engine is already using.
 *
 * This does NOT open a camera. It attaches the engine's existing
 * MediaStream to a second <video> element, which the browser renders from
 * the same source — so there is one permission prompt, one stream, one
 * pose model, and the raw and keypoint panels are showing the same live
 * frame rather than two slightly different ones.
 *
 * The engine owns the stream's lifecycle entirely; this component only
 * borrows a reference to it and drops it on unmount.
 */

import { useEffect, useRef } from "react";

export default function RawCameraView({ engine, label = "Live camera" }) {
  const videoRef = useRef(null);

  const sourceVideo = engine?.videoRef?.current ?? null;
  const engineState = engine?.state;
  // Derived from the engine rather than tracked in local state: the engine
  // already knows when the stream is live, and a second copy of that fact
  // could only ever disagree with it.
  const live = Boolean(engine?.isLive);

  useEffect(() => {
    const target = videoRef.current;

    if (!target) return undefined;

    // The engine's own <video> is the authority on the stream. It may not
    // have one yet (the model is still loading, or permission is still
    // pending), so this re-checks as the engine's state changes rather
    // than polling.
    const source = engine?.videoRef?.current;
    const stream = source?.srcObject ?? null;

    if (!stream) {
      target.srcObject = null;
      return undefined;
    }

    if (target.srcObject !== stream) {
      target.srcObject = stream;
    }

    const play = target.play();

    if (play && typeof play.catch === "function") {
      // Autoplay can be refused; the stream is still attached and the
      // engine's own preview is unaffected, so this is not an error worth
      // showing the user.
      play.catch(() => {});
    }

    return () => {
      target.srcObject = null;
    };
  }, [engine, sourceVideo, engineState]);

  return (
    <div className="raw-camera">
      <video
        ref={videoRef}
        className="raw-camera__video"
        playsInline
        muted
        autoPlay
        aria-label={label}
      />
      {live ? null : (
        <div className="raw-camera__cover">
          <span className="raw-camera__spinner" aria-hidden="true" />
          <p>Waiting for the camera…</p>
        </div>
      )}
    </div>
  );
}
