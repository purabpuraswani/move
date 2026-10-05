/**
 * The application shell: one top bar, one bottom navigation, one place the
 * product's four sections live.
 *
 * The navigation is deliberately four items — Today, Plan, Progress, You.
 * Everything else (assessment, nutrition check-in, a specialist's page, reports)
 * is reached from inside those four, because a top-level list of every module is
 * what made the previous interface read as a set of screens rather than a
 * product. Reports, past sessions and the historical screens still exist: they
 * live under You.
 *
 * The bottom bar is the mobile navigation and is hidden on wide screens, where
 * the same four items are in the top bar. Focus order and labels are identical
 * in both, so a screen reader hears one navigation, not two.
 */

import { Link, useLocation, useNavigate } from "react-router-dom";

import { clearSession, getToken } from "../../services/auth";

import "./AppShell.css";

function IconToday() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M4 12.5 12 5l8 7.5" />
      <path d="M6.5 11v8h11v-8" />
    </svg>
  );
}

function IconPlan() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M7 4.5h7.5L19 9v10.5H7z" />
      <path d="M14 4.5V9h4.5" />
      <path d="M9.5 13.5h6M9.5 16.5h4" />
    </svg>
  );
}

function IconProgress() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M4.5 18.5h15" />
      <path d="M7.5 18.5v-5M12 18.5V8M16.5 18.5v-7.5" />
    </svg>
  );
}

function IconYou() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="9" r="3.4" />
      <path d="M5.5 19.5c1.3-3.2 3.7-4.8 6.5-4.8s5.2 1.6 6.5 4.8" />
    </svg>
  );
}

const NAV_ITEMS = [
  { label: "Today", to: "/today", icon: IconToday, match: (path) => path === "/today" || path === "/dashboard" },
  { label: "Plan", to: "/plan", icon: IconPlan, match: (path) => path.startsWith("/plan") || path.startsWith("/specialist") || path.startsWith("/exercise") },
  { label: "Progress", to: "/progress", icon: IconProgress, match: (path) => path.startsWith("/progress") },
  { label: "You", to: "/you", icon: IconYou, match: (path) => path.startsWith("/you") || path.startsWith("/profile") || path.startsWith("/reports") || path.startsWith("/history") },
];

export default function AppShell({ children, backTo = null, backLabel = "Back" }) {
  const location = useLocation();
  const navigate = useNavigate();
  const signedIn = Boolean(getToken());
  const path = location.pathname;

  function handleLogout() {
    clearSession();
    navigate("/login");
  }

  return (
    <div className="shell">
      <header className="shell-bar">
        <div className="shell-bar-inner">
          <Link to="/today" className="shell-brand" aria-label="MoveWell — Today">
            <span className="shell-brand-mark" aria-hidden="true">
              M
            </span>
            <span className="shell-brand-name">MoveWell</span>
          </Link>

          <nav className="shell-nav" aria-label="Main">
            {NAV_ITEMS.map((item) => {
              const active = item.match(path);
              const Icon = item.icon;

              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`shell-nav-link${active ? " is-active" : ""}`}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="shell-bar-actions">
            {backTo ? (
              <Link to={backTo} className="shell-back">
                ← {backLabel}
              </Link>
            ) : null}

            {signedIn ? (
              <button type="button" className="shell-logout" onClick={handleLogout}>
                Log out
              </button>
            ) : null}
          </div>
        </div>
      </header>

      <main className="shell-main" id="main">
        {children}
      </main>

      <nav className="shell-tabbar" aria-label="Main">
        {NAV_ITEMS.map((item) => {
          const active = item.match(path);
          const Icon = item.icon;

          return (
            <Link
              key={item.to}
              to={item.to}
              className={`shell-tab${active ? " is-active" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              <Icon />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
