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
import { useI18n } from "../../i18n.jsx";
import "./layout.css";

const NAV_ITEMS = [
  { page: "dashboard", labelKey: "nav.dashboard", icon: DashboardIcon },
  { page: "search", labelKey: "nav.search", icon: SearchIcon },
  { page: "upload", labelKey: "nav.upload", icon: UploadIcon },
  { page: "settings", labelKey: "nav.settings", icon: SettingsIcon },
];

export default function Sidebar({ currentPage, onNavigate, user, onLogout }) {
  const { language, setLanguage, t } = useI18n();
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
        <button className="btn btn-ghost" onClick={() => setMobileOpen(true)} aria-label={t("nav.openMenu")} style={{ padding: 6, minHeight: "auto" }}>
          <MenuIcon />
        </button>
        <button className="brand-button compact" onClick={() => go("dashboard")} aria-label={t("nav.home")}>
          <Logo size={22} style={{ color: "var(--color-blue-light)" }} />
          <span>Muninn</span>
        </button>
      </div>

      <div className={`sidebar-backdrop ${mobileOpen ? "visible" : ""}`} onClick={() => setMobileOpen(false)} />

      <aside className={`sidebar ${slim ? "slim" : ""} ${mobileOpen ? "mobile-open" : ""}`}>
        <div className="sidebar-header">
          <button className="brand-button compact" onClick={() => go("dashboard")} aria-label={t("nav.home")}>
            <Logo size={24} style={{ color: "var(--color-blue-light)", flex: "none" }} />
            <span className="brand-name">Muninn</span>
          </button>
          {mobileOpen && (
            <button
              className="btn btn-ghost"
              onClick={() => setMobileOpen(false)}
              style={{ marginLeft: "auto", padding: 4, minHeight: "auto" }}
              aria-label={t("nav.closeMenu")}
            >
              <CloseIcon width={18} height={18} />
            </button>
          )}
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ page, labelKey, icon: Icon }) => (
            <button key={page} className={`sidebar-link ${currentPage === page ? "active" : ""}`} onClick={() => go(page)}>
              <Icon />
              <span className="nav-label">{t(labelKey)}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <label className="language-switcher">
            <span className="nav-label">{t("common.language")}</span>
            <select value={language} onChange={(e) => setLanguage(e.target.value)} aria-label={t("common.language")}>
              <option value="sk">SK</option>
              <option value="en">EN</option>
            </select>
          </label>
          <div className="nav-label" style={{ fontSize: 13, color: "var(--color-text-secondary)", marginBottom: 8, padding: "0 4px" }}>
            {user.username}
          </div>
          <button className="sidebar-link" onClick={onLogout}>
            <LogoutIcon />
            <span className="nav-label">{t("nav.logout")}</span>
          </button>
          <button className="sidebar-collapse-btn" onClick={() => setSlim((s) => !s)} aria-label={slim ? t("nav.expand") : t("nav.collapse")}>
            {slim ? <ChevronRightIcon /> : <ChevronLeftIcon />}
          </button>
        </div>
      </aside>
    </>
  );
}
