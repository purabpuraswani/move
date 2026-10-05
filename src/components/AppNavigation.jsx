import { Link, useLocation, useNavigate } from "react-router-dom";
import { clearSession, getToken } from "../services/auth";
import "./AppNavigation.css";

/**
 * The navigation for the secondary screens — reports, past sessions, the
 * internal dashboard, the legacy guidance page.
 *
 * The product's own navigation lives in `components/ui/AppShell.jsx` and is four
 * items: Today, Plan, Progress, You. This one is kept only for the screens that
 * sit underneath You, and it deliberately lists the same four sections so the
 * product never presents two different maps of itself. The back link is what
 * those screens actually use.
 */
const NAV_ITEMS = [
  { label: "Today", to: "/today", match: (p) => p === "/today" || p === "/dashboard" },
  { label: "Plan", to: "/plan", match: (p) => p.startsWith("/plan") },
  { label: "Progress", to: "/progress", match: (p) => p.startsWith("/progress") },
  { label: "You", to: "/you", match: (p) => p.startsWith("/you") || p.startsWith("/profile") },
];

export default function AppNavigation({
  backTo = "/you",
  backLabel = "← You",
  showBack = true,
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const currentPath = location.pathname;
  const signedIn = Boolean(getToken());

  function handleLogout() {
    clearSession();
    navigate("/login");
  }

  return (
    <header className="app-nav-header" role="banner">
      <div className="app-nav-inner">
        <div className="app-nav-left">
          <Link to="/today" className="app-nav-logo" aria-label="MoveWell — Today">
            <div className="app-nav-logo-mark" aria-hidden="true">
              M
            </div>
            <span>
              MoveWell
            </span>
          </Link>
        </div>

        <nav className="app-nav-menu" aria-label="Main">
          {NAV_ITEMS.map((item) => {
            const isActive = item.match(currentPath);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`app-nav-link ${isActive ? "active" : ""}`}
                aria-current={isActive ? "page" : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="app-nav-right">
          {showBack && (
            <Link to={backTo} className="app-nav-back-action" aria-label={backLabel}>
              {backLabel}
            </Link>
          )}

          {signedIn && (
            <button
              type="button"
              className="app-nav-logout-btn"
              onClick={handleLogout}
              aria-label="Log out"
            >
              Log out
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
