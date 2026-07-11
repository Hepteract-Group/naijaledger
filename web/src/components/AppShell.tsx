import { NavLink, Outlet } from "react-router-dom";
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

  return (
    <div className="shell">
      <header className="site-header">
        <div className="site-header__inner">
          <NavLink to="/" className="brand" end>
            NaijaLedger
          </NavLink>
          <nav className="nav" aria-label="Primary">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) => (isActive ? "active" : undefined)}
              >
                {link.label}
              </NavLink>
            ))}
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
          <span>Open civic accountability for Nigeria</span>
          <NavLink to="/status">Engine status</NavLink>
        </div>
      </footer>
    </div>
  );
}
