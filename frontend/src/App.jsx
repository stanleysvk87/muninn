import { useEffect, useState } from "react";
import api from "./api/client";
import "./components/ui/ui.css";
import Button from "./components/ui/Button.jsx";
import DocumentDetail from "./pages/DocumentDetail/DocumentDetail.jsx";
import Login from "./pages/Login/Login.jsx";
import Search from "./pages/Search/Search.jsx";
import Settings from "./pages/Settings/Settings.jsx";
import Upload from "./pages/Upload/Upload.jsx";

function parsePath(path) {
  if (path.startsWith("/documents/")) {
    return { page: "document", id: path.slice("/documents/".length) };
  }
  if (path === "/upload") return { page: "upload" };
  if (path === "/settings") return { page: "settings" };
  return { page: "search" };
}

function navigate(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

const navStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "16px 24px",
  borderBottom: "1px solid var(--color-border)",
  background: "var(--color-ink-secondary)",
};

function NavLink({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className="btn btn-ghost"
      style={{
        color: active ? "var(--color-text-primary)" : "var(--color-text-secondary)",
        borderBottom: active ? "2px solid var(--color-blue-light)" : "2px solid transparent",
        borderRadius: 0,
      }}
    >
      {label}
    </button>
  );
}

export default function App() {
  const [user, setUser] = useState(undefined); // undefined = loading, null = not logged in
  const [route, setRoute] = useState(() => parsePath(window.location.pathname));

  useEffect(() => {
    function onPop() {
      setRoute(parsePath(window.location.pathname));
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    function onUnauthorized() {
      setUser(null);
    }
    window.addEventListener("muninn:unauthorized", onUnauthorized);
    return () => window.removeEventListener("muninn:unauthorized", onUnauthorized);
  }, []);

  useEffect(() => {
    api
      .get("/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => setUser(null));
  }, []);

  if (user === undefined) {
    return <div style={{ minHeight: "100vh" }} />;
  }

  if (!user) {
    return <Login onLoggedIn={setUser} />;
  }

  async function logout() {
    await api.post("/auth/logout");
    setUser(null);
  }

  return (
    <div>
      <nav style={navStyle}>
        <div className="eyebrow" style={{ fontSize: 14, letterSpacing: "0.1em" }}>
          MUNINN
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          <NavLink label="Hladanie" active={route.page === "search"} onClick={() => navigate("/")} />
          <NavLink label="Nahrat" active={route.page === "upload"} onClick={() => navigate("/upload")} />
          <NavLink label="Nastavenia" active={route.page === "settings"} onClick={() => navigate("/settings")} />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ color: "var(--color-text-secondary)", fontSize: 13 }}>{user.username}</span>
          <Button variant="ghost" onClick={logout}>
            Odhlasit
          </Button>
        </div>
      </nav>
      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
        {route.page === "search" && <Search onOpenDocument={(id) => navigate(`/documents/${id}`)} />}
        {route.page === "upload" && <Upload />}
        {route.page === "document" && <DocumentDetail documentId={route.id} onBack={() => navigate("/")} />}
        {route.page === "settings" && <Settings />}
      </main>
    </div>
  );
}
