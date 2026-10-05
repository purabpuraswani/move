/**
 * Temporary render-check prelude: the app shell reads localStorage for the
 * session token, which does not exist under Node. Stubbed here only so this
 * throwaway check can render.
 */

const store = new Map();

globalThis.localStorage = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, value) => store.set(key, String(value)),
  removeItem: (key) => store.delete(key),
  clear: () => store.clear(),
};

globalThis.sessionStorage = globalThis.localStorage;

globalThis.matchMedia = () => ({
  matches: false,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {},
});
