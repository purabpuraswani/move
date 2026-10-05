/**
 * Module loader hooks that stub non-JavaScript assets.
 *
 * Registered by src/test/registerAssetStub.mjs, which the `test` script loads
 * with `--import`. A stylesheet or an image resolves to an empty module; it
 * contributes no behaviour to a component's markup, so stubbing it changes
 * nothing about what the test is asserting.
 */

const STUBBED = /\.(css|png|jpe?g|svg|webp|gif|mp4)$/i;

export async function load(url, context, nextLoad) {
  if (STUBBED.test(url)) {
    return {
      format: "module",
      shortCircuit: true,
      source: "export default {};",
    };
  }

  return nextLoad(url, context);
}
