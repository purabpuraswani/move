/**
 * The assessment workspace's layout contract.
 *
 * The UX requirement behind these tests: when the user clicks "I'm
 * ready · Start test" they must be able to perform the movement while
 * still seeing their own camera. That broke because the camera and the
 * demonstration had heights fixed against the page while the readiness
 * panel sat below them, pushing the Start button under the fold.
 *
 * These are STRUCTURAL tests over the stylesheet and the components --
 * this project runs `node --test` over plain JS with no DOM, so they
 * assert which rules exist, not what a browser paints. They cannot
 * tell you the page looks right. They can tell you that nobody has
 * reintroduced the fixed heights, the sticky camera, an automatic
 * scroll, a clipped page, or a hard-coded guess at the panel's height.
 * Those are the regressions this layout has actually suffered.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.resolve(here, "../..");

/** Source with comments stripped, so prose about a rule is not read as one. */
function codeOf(relativePath) {
  return readFileSync(path.join(src, relativePath), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/^\s*\/\/.*$/gm, " ");
}

const cssRules = codeOf("pages/AssessmentPage.css");

/**
 * Every declaration block in the stylesheet, as {selector, body} --
 * including the ones nested inside @media.
 *
 * A naive /[^{}]*\{[^}]*\}/ split cannot see into a media query: it
 * treats "@media (...) {" as the selector and swallows the first rule
 * inside it. Most of this layout lives in media queries, so that split
 * made several assertions below pass without ever reading the rule
 * they named. This walks braces instead.
 */
function declarationBlocks(css) {
  const blocks = [];
  let depth = 0;
  let start = 0;

  for (let i = 0; i < css.length; i += 1) {
    if (css[i] === "{") {
      if (depth === 0) start = i;
      depth += 1;
    } else if (css[i] === "}") {
      depth -= 1;

      if (depth === 0) {
        const selector = css.slice(blocks.lastEnd ?? 0, start);
        const body = css.slice(start + 1, i);

        if (body.includes("{")) {
          // An at-rule wrapper: recurse into its contents.
          blocks.push(...declarationBlocks(body));
        } else {
          blocks.push({ selector: selector.split("}").pop().trim(), body });
        }

        blocks.lastEnd = i + 1;
      }
    }
  }

  return blocks;
}

const ALL_BLOCKS = declarationBlocks(cssRules);

/** Every declaration block whose selector mentions `needle`. */
function blocksMentioning(needle) {
  return ALL_BLOCKS.filter((block) => block.selector.includes(needle)).map(
    (block) => `${block.selector} {${block.body}}`,
  );
}

// ---------------------------------------------------------------- heading

test("there is no DEMONSTRATION heading above the video", () => {
  // Removed at source, not hidden with CSS: the component no longer
  // takes a title and the stylesheet no longer has a rule for one.
  const component = codeOf("assessment/components/DemonstrationVideo.jsx");

  assert.ok(!/title/.test(component), "the demonstration title prop came back");
  assert.ok(!/<h3/.test(component), "the demonstration heading came back");
  assert.ok(
    !cssRules.includes("assess-demo-title"),
    "the heading's styling is still present",
  );
  assert.ok(
    !codeOf("pages/AssessmentPage.jsx").includes('title="Demonstration"'),
    "the assessment page still passes a Demonstration title",
  );
});

test("the demonstration starts level with the camera", () => {
  // Its 16px block margin is for sitting inline in the instruction
  // prose; beside the camera it would start the video lower.
  const blocks = blocksMentioning(".assess-workspace > .assess-demo-container--video");

  assert.ok(blocks.length > 0, "the workspace rule for the demonstration is gone");
  assert.ok(
    blocks.some((block) => /margin:\s*0/.test(block)),
    "the demonstration keeps its inline-prose top margin beside the camera",
  );
});

// ------------------------------------------------------------ the layout

test("the camera is never sticky", () => {
  // A sticky camera is the banned patch: in a single-column flow it
  // floats over the readiness panel instead of sitting above it.
  const blocks = blocksMentioning(".assess-camera");

  assert.ok(blocks.length > 0, "no .assess-camera rules found at all");

  for (const block of blocks) {
    assert.ok(
      !/position:\s*sticky/.test(block),
      `a sticky camera was reintroduced:\n${block}`,
    );
  }
});

test("the workspace is sized from the viewport, not from a constant", () => {
  // The browser decides the height: the page is one viewport tall, the
  // panel takes its natural height and the row takes what is left. An
  // earlier version reserved an ESTIMATED panel height and overflowed
  // by ~50px at 1366x768 because the estimate was wrong. There must be
  // no such constant left to be wrong.
  assert.match(
    cssRules,
    /\.assess-page:has\(\.assess-main--split\)[^{]*\{[^}]*height:\s*100vh/,
    "the assessment page is no longer sized to the viewport",
  );
  assert.ok(
    !cssRules.includes("--assess-reserved"),
    "a hard-coded reserve for the panel's height came back",
  );
});

test("the page is sized, never clipped", () => {
  // overflow:hidden on a viewport-tall page would cut the Start button
  // off on a short laptop rather than reveal it.
  for (const block of blocksMentioning(".assess-page")) {
    assert.ok(
      !/overflow:\s*hidden/.test(block),
      `the assessment page clips its content:\n${block}`,
    );
  }
});

test("the row takes the leftover height and the panel keeps its own", () => {
  assert.ok(
    blocksMentioning(".assess-workspace").some((block) => /flex:\s*1 1 auto/.test(block)),
    "the media row no longer absorbs the leftover height",
  );
  assert.match(
    cssRules,
    /\.assess-main--split > \.assess-panel\s*\{[^}]*flex:\s*0 0 auto/,
    "the readiness panel can be squeezed, which would hide its controls",
  );
});

test("the row keeps a floor so the camera cannot be squeezed away", () => {
  const floors = blocksMentioning(".assess-workspace")
    .map((block) => block.match(/min-height:\s*(\d+)px/))
    .filter(Boolean)
    .map((match) => Number(match[1]));

  assert.ok(floors.length > 0, "the workspace has no minimum height");
  assert.ok(
    Math.max(...floors) >= 240,
    `the camera floor fell to ${Math.max(...floors)}px, too short for a full-body check`,
  );
});

test("the row has a ceiling so it cannot dominate a tall monitor", () => {
  assert.ok(
    blocksMentioning(".assess-workspace").some((block) => /max-height:\s*\d+px/.test(block)),
  );
});

// ------------------------------------------------------------ the camera

test("the camera keeps its native ratio so nothing is cropped", () => {
  // Sized by height at 4/3. Stretched to the column's width it would be
  // ~2.3:1 on a laptop, and object-fit: cover would then crop away the
  // head and feet that a sit-to-stand or one-leg stand must show.
  const blocks = blocksMentioning(".assess-workspace > .assess-camera > .assess-camera__frame");

  assert.ok(blocks.length > 0, "the workspace rule for the camera frame is gone");

  const sized = blocks.find((block) => /aspect-ratio/.test(block)) || "";

  assert.match(sized, /aspect-ratio:\s*4\s*\/\s*3/);
  assert.match(sized, /width:\s*auto/);
  assert.match(sized, /max-height:\s*none/);
});

test("the camera and demonstration are stretched to equal heights", () => {
  const workspace = cssRules.match(/\.assess-workspace\s*\{[^}]*\}/)?.[0] || "";

  assert.match(workspace, /align-items:\s*stretch/);
  assert.ok(
    !/align-items:\s*start/.test(workspace),
    "align-items: start lets the two columns end at different heights",
  );
});

test("the camera preview still fills its frame without distortion", () => {
  assert.match(cssRules, /\.assess-camera__video[\s\S]{0,300}?object-fit:\s*cover/);
});

test("the demonstration is letterboxed rather than cropped", () => {
  const blocks = cssRules.match(/[^{}]*assess-demo-video[^{]*\{[^}]*\}/g) || [];

  assert.ok(
    blocks.some((block) => /object-fit:\s*contain/.test(block)),
    "the demonstration could be cropped to fill its box",
  );
  assert.ok(
    blocks.some((block) => /aspect-ratio:\s*auto/.test(block)),
    "the demo video still has a fixed aspect ratio in the workspace",
  );
});

test("the privacy note is never hidden to save space", () => {
  // It tells the user no camera frame leaves their device. That is a
  // disclosure, not decoration, and a short viewport is not a reason
  // to drop it.
  const blocks = blocksMentioning(".assess-camera__note");

  assert.ok(blocks.length > 0, "the privacy note's styling is gone");

  for (const block of blocks) {
    assert.ok(!/display:\s*none/.test(block), `the privacy note was hidden:\n${block}`);
  }
});

// ------------------------------------------------------------- behaviour

test("nothing in the assessment scrolls the page on its own", () => {
  for (const file of [
    "pages/AssessmentPage.jsx",
    "assessment/components/AssessmentFlow.jsx",
    "assessment/components/CameraStage.jsx",
    "assessment/components/DemonstrationVideo.jsx",
  ]) {
    const code = codeOf(file);

    for (const marker of ["scrollIntoView", "window.scrollTo", "scrollTop ="]) {
      assert.ok(
        !code.includes(marker),
        `${file} scrolls the page automatically (${marker})`,
      );
    }
  }
});

test("the countdown stays inside the camera frame", () => {
  // Rendered as an overlay, it cannot push the camera down the page.
  const camera = codeOf("assessment/components/CameraStage.jsx");
  const frameStart = camera.indexOf("assess-camera__frame");
  const countdown = camera.indexOf("assess-camera__countdown-overlay");

  assert.ok(countdown > frameStart && frameStart > -1, "the countdown left the frame");
  assert.match(cssRules, /\.assess-camera__countdown-overlay[\s\S]{0,200}?position:\s*absolute/);
});

test("all three baseline checks still have their own demonstration", () => {
  const videos = codeOf("movementDemos/exerciseVideos.js");

  for (const file of ["shoulder-raise.mp4", "sit-to-stand.mp4", "one-leg-stand.mp4"]) {
    assert.ok(videos.includes(file), `${file} is no longer mapped`);
  }
});
