import { useEffect, useState } from "react";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  CloseIcon,
  DashboardIcon,
  LogoutIcon,
  MenuIcon,
  SearchIcon,
  SettingsIcon,
  UploadIcon,
} from "../ui/Icons.jsx";
import Logo from "../ui/Logo.jsx";
import "./layout.css";

const NAV_ITEMS = [
  { page: "dashboard", label: "Prehlad", icon: DashboardIcon },
  { page: "search", label: "Hladanie", icon: SearchIcon },
  { page: "upload", label: "Nahrat", icon: UploadIcon },
  { page: "settings", label: "Nastavenia", icon: SettingsIcon },
];

export default function Sidebar({ currentPage, onNavigate, user, onLogout }) {
  const [slim, setSlim] = useState(() => localStorage.getItem("muninn-sidebar-slim") === "1");
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem("muninn-sidebar-slim", slim ? "1" : "0");
  }, [slim]);

  function go(page) {
    onNavigate(page);
    setMobileOpen(false);
  }

  return (
    <>
      <div className="mobile-topbar">
        <button className="btn btn-ghost" onClick={() => setMobileOpen(true)} aria-label="Otvorit menu" style={{ padding: 6, minHeight: "auto" }}>
          <MenuIcon />
        </button>
        <Logo size={22} style={{ color: "var(--color-blue-light)" }} />
        <span style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>Muninn</span>
      </div>

      <div className={`sidebar-backdrop ${mobileOpen ? "visible" : ""}`} onClick={() => setMobileOpen(false)} />

      <aside className={`sidebar ${slim ? "slim" : ""} ${mobileOpen ? "mobile-open" : ""}`}>
        <div className="sidebar-header">
          <Logo size={24} style={{ color: "var(--color-blue-light)", flex: "none" }} />
          <span className="brand-name">Muninn</span>
          {mobileOpen && (
            <button
              className="btn btn-ghost"
              onClick={() => setMobileOpen(false)}
              style={{ marginLeft: "auto", padding: 4, minHeight: "auto" }}
              aria-label="Zavriet menu"
            >
              <CloseIcon width={18} height={18} />
            </button>
          )}
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ page, label, icon: Icon }) => (
            <button key={page} className={`sidebar-link ${currentPage === page ? "active" : ""}`} onClick={() => go(page)}>
              <Icon />
              <span className="nav-label">{label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="nav-label" style={{ fontSize: 13, color: "var(--color-text-secondary)", marginBottom: 8, padding: "0 4px" }}>
            {user.username}
          </div>
          <button className="sidebar-link" onClick={onLogout}>
            <LogoutIcon />
            <span className="nav-label">Odhlasit</span>
          </button>
          <button className="sidebar-collapse-btn" onClick={() => setSlim((s) => !s)} aria-label={slim ? "Rozbalit menu" : "Zbalit menu"}>
            {slim ? <ChevronRightIcon /> : <ChevronLeftIcon />}
          </button>
        </div>
      </aside>
    </>
  );
}
