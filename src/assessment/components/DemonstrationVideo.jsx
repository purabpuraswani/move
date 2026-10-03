/**
 * The recorded demonstration of a baseline check.
 *
 * One component, used in two places, so the two can never drift:
 *  - beside the live camera during a check (AssessmentPage), which is what
 *    lets a user watch the movement while performing it; and
 *  - on the instruction screen before the camera starts (AssessmentFlow).
 *
 * It renders nothing when there is no recording for that movement, so a
 * check without a video simply shows the existing demonstration instead.
 */

/*
 * No heading. Beside the live camera the video IS the demonstration, and
 * a "DEMONSTRATION" label above it only pushed the video down so that it
 * no longer started level with the camera next to it. The caption below
 * still says which movement is being shown.
 */
export default function DemonstrationVideo({ video, compact = false }) {
  if (!video) return null;

  return (
    <div
      className={`assess-demo-container assess-demo-container--video${
        compact ? " assess-demo-container--compact" : ""
      }`}
    >
      <video
        className="assess-demo-video"
        src={video.src}
        controls
        loop
        muted
        playsInline
        preload="metadata"
      />
      <p className="assess-demo-caption">{video.caption}</p>
    </div>
  );
}
