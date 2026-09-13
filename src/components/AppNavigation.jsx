import { Link, useLocation, useNavigate } from "react-router-dom";
import { clearSession, getToken } from "../services/auth";
import "./AppNavigation.css";

const NAV_ITEMS = [
  { label: "Dashboard", to: "/dashboard", match: (p) => p === "/dashboard" },
  { label: "Assessment", to: "/assessment", match: (p) => p === "/assessment" || p === "/assess" },
  { label: "My plan", to: "/plan", match: (p) => p === "/plan" },
  { label: "My progress", to: "/progress", match: (p) => p === "/progress" },
  { label: "Past sessions", to: "/history", match: (p) => p === "/history" },
  { label: "Reports", to: "/reports", match: (p) => p.startsWith("/reports") },
];

export default function AppNavigation({
  backTo = "/dashboard",
  backLabel = "← Dashboard",
  showBack = true,
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const currentPath = location.pathname;
  const isDashboard = currentPath === "/dashboard";
  const signedIn = Boolean(getToken());

  function handleLogout() {
    clearSession();
    navigate("/login");
  }

  return (
    <header className="app-nav-header" role="banner">
      <div className="app-nav-inner">
        <div className="app-nav-left">
          <Link
            to="/dashboard"
            className="app-nav-logo"
            aria-label="MoveWell AI Dashboard"
            onClick={(e) => {
              if (isDashboard) e.preventDefault();
            }}
          >
            <div className="app-nav-logo-mark" aria-hidden="true">
              M
            </div>
            <span>
              MoveWell<small>AI</small>
            </span>
          </Link>
        </div>

        <nav className="app-nav-menu" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => {
            const isActive = item.match(currentPath);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`app-nav-link ${isActive ? "active" : ""}`}
                aria-current={isActive ? "page" : undefined}
                onClick={(e) => {
                  if (isActive) {
                    e.preventDefault();
                  }
                }}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="app-nav-right">
          {showBack && !isDashboard && (
            <Link
              to={backTo}
              className="app-nav-back-action"
              aria-label={backLabel}
            >
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
