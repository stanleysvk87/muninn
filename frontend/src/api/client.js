import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
  timeout: 30000,
});

function readCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

const UNSAFE_METHODS = new Set(["post", "put", "patch", "delete"]);

api.interceptors.request.use((config) => {
  if (UNSAFE_METHODS.has((config.method || "").toLowerCase())) {
    const token = readCookie("muninn_csrf");
    if (token) {
      config.headers["X-CSRF-Token"] = token;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error;
    if (response?.status === 401) {
      if (!window.location.pathname.startsWith("/login")) {
        window.dispatchEvent(new CustomEvent("muninn:unauthorized"));
      }
    }
    return Promise.reject(error);
  },
);

export default api;
