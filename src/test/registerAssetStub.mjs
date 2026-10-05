/**
 * Lets `node --test` import the application's components.
 *
 * Components import their own stylesheet (`import "./X.css"`), which Node
 * cannot parse. This registers a loader that answers those imports with an
 * empty module, so a component's rendering can be exercised in a plain Node
 * test — no bundler, no jsdom, no browser.
 *
 * Only `.css` (and the image formats a component might import) are
 * intercepted; every other import is resolved normally, so a test still fails
 * loudly if a module it needs is broken.
 */

import { register } from "node:module";

register("./assetStubLoader.mjs", import.meta.url);
