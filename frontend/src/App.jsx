import { useEffect, useState } from "react";
import api from "./api/client";
import "./components/ui/ui.css";
import "./components/layout/layout.css";
import Sidebar from "./components/layout/Sidebar.jsx";
import Dashboard from "./pages/Dashboard/Dashboard.jsx";
import DocumentDetail from "./pages/DocumentDetail/DocumentDetail.jsx";
import Login from "./pages/Login/Login.jsx";
import Search from "./pages/Search/Search.jsx";
import Settings from "./pages/Settings/Settings.jsx";
import Upload from "./pages/Upload/Upload.jsx";

const PATH_BY_PAGE = {
  dashboard: "/",
  search: "/hladanie",
  upload: "/nahrat",
  settings: "/nastavenia",
};

function parsePath(path) {
  if (path.startsWith("/dokumenty/")) {
    return { page: "document", id: path.slice("/dokumenty/".length) };
  }
  if (path === "/hladanie") return { page: "search" };
  if (path === "/nahrat") return { page: "upload" };
  if (path === "/nastavenia") return { page: "settings" };
  return { page: "dashboard" };
}

function navigate(page, id) {
  const path = page === "document" ? `/dokumenty/${id}` : PATH_BY_PAGE[page] || "/";
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
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
    <div className="app-shell">
      <Sidebar currentPage={route.page} onNavigate={navigate} user={user} onLogout={logout} />
      <main className="app-main">
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
          {route.page === "dashboard" && (
            <Dashboard onOpenDocument={(id) => navigate("document", id)} onNavigate={navigate} />
          )}
          {route.page === "search" && <Search onOpenDocument={(id) => navigate("document", id)} />}
          {route.page === "upload" && <Upload />}
          {route.page === "document" && <DocumentDetail documentId={route.id} onBack={() => navigate("dashboard")} />}
          {route.page === "settings" && <Settings />}
        </div>
      </main>
    </div>
  );
}
