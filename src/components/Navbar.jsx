import { Link } from "react-router-dom";
import "./Navbar.css";

function Navbar() {
  return (
    <nav className="navbar">
      <div className="nav-container">

        <Link to="/" className="brand">
          <div className="brand-icon">
            M
          </div>

          <span>
            Move<span>Well</span> AI
          </span>
        </Link>

        <div className="nav-links">
          <a href="#features">Features</a>
          <a href="#how-it-works">How it works</a>
          <a href="#about">About</a>
        </div>

        <div className="nav-actions">
          <Link to="/login" className="nav-login">
            Log in
          </Link>

          <Link to="/signup" className="nav-signup">
            Get Started
          </Link>
        </div>

      </div>
    </nav>
  );
}

export default Navbar;