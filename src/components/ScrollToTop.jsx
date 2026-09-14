import { useLayoutEffect } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

/**
 * Opens every newly navigated-to screen at the top, or at its #fragment.
 *
 * The app scrolls the window itself (no page uses an inner scroll container),
 * and <BrowserRouter> leaves the window's scroll offset alone when the route
 * changes. So a link near the bottom of a long screen -- the dashboard's
 * "Meet your specialists" cards, or the team cards at the foot of a specialist
 * page -- rendered the next screen at that same offset, i.e. at its bottom.
 *
 * A browser only jumps to a #fragment on a full page load, never on a
 * client-side navigation, so a link such as /dashboard#specialists is scrolled
 * to its target here. An unknown fragment falls back to the top.
 *
 * Only PUSH and REPLACE navigations scroll. Back/Forward (POP) is left to the
 * browser, which restores the position the user left that screen at.
 *
 * `behavior: "instant"` is deliberate: index.css sets `scroll-behavior: smooth`
 * on <html>, which would otherwise animate this jump from the old offset.
 */
function ScrollToTop() {
  const { pathname, hash } = useLocation();
  const navigationType = useNavigationType();

  useLayoutEffect(() => {
    if (navigationType === "POP") return;

    const target = hash ? document.getElementById(decodeURIComponent(hash.slice(1))) : null;

    if (target) {
      target.scrollIntoView({ block: "start", behavior: "instant" });
    } else {
      window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    }
  }, [pathname, hash, navigationType]);

  return null;
}

export default ScrollToTop;
