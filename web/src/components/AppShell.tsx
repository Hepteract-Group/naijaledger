import { useEffect, useId, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useTheme } from "../hooks/useTheme";

const links = [
  { to: "/explore", label: "Explore" },
  { to: "/graph", label: "Graph" },
  { to: "/map", label: "Map" },
  { to: "/stories", label: "Stories" },
  { to: "/sources", label: "Sources" },
] as const;

export function AppShell() {
  const { theme, onToggle } = useTheme();
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();
  const navId = useId();

  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname]);

  return (
    <div className="shell">
      <header className="site-header">
        <div className="site-header__inner">
          <NavLink to="/" className="brand" end>
            <span className="brand__mark" aria-hidden />
            NaijaLedger
          </NavLink>
          <button
            type="button"
            className="nav-toggle"
            aria-expanded={navOpen}
            aria-controls={navId}
            onClick={() => setNavOpen((open) => !open)}
          >
            {navOpen ? "Close" : "Menu"}
          </button>
          <nav id={navId} className={`nav${navOpen ? " nav--open" : ""}`} aria-label="Primary">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) => (isActive ? "active" : undefined)}
              >
                {link.label}
              </NavLink>
            ))}
            <NavLink
              to="/methodology"
              className={({ isActive }) => (isActive ? "active" : undefined)}
            >
              Method
            </NavLink>
            <button
              type="button"
              className="theme-toggle"
              onClick={onToggle}
              aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
            >
              {theme === "light" ? "Dark" : "Light"}
            </button>
          </nav>
        </div>
      </header>
      <main className="site-main">
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="site-footer__inner">
          <div>
            <p className="site-footer__brand">NaijaLedger</p>
            <p>
              Open civic accountability for Nigeria. Lawful. Nonpartisan. Built for citizens who
              keep receipts.
            </p>
          </div>
          <div>
            <p className="site-footer__label">Investigate</p>
            <div className="site-footer__links">
              <NavLink to="/explore">Explore</NavLink>
              <NavLink to="/map">Map</NavLink>
              <NavLink to="/graph">Graph</NavLink>
              <NavLink to="/stories">Stories</NavLink>
            </div>
          </div>
          <div>
            <p className="site-footer__label">Trust</p>
            <div className="site-footer__links">
              <NavLink to="/sources">Sources</NavLink>
              <NavLink to="/methodology">Methodology</NavLink>
              <NavLink to="/status">Engine status</NavLink>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
