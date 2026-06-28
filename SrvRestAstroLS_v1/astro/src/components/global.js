export const APP_NAME = "TebaAI";
export const APP_PUBLIC_NAME = "Teba AI";

// -- Backend REST endpoint --
// All API clients must import API_BASE_URL from here, not hardcode URLs.
// Uses the Astro proxy (/api -> backend) for development.
// Override via PUBLIC_TEBAAI_API_BASE_URL env for custom backend URLs.
const BACKEND_DEV = "http://127.0.0.1:7008";
const envUrl = typeof import.meta !== "undefined" && import.meta.env?.PUBLIC_TEBAAI_API_BASE_URL;
// @lat: [[global-configuration-facade-policy]]
export const API_BASE_URL = envUrl || BACKEND_DEV;

export const DEFAULT_LOCALE = "es";
export const SUPPORTED_LOCALES = ["es", "en", "he"];
export const LOCALE_DIRECTION = {
  es: "ltr",
  en: "ltr",
  he: "rtl",
};
export const DEFAULT_DIRECTION = LOCALE_DIRECTION[DEFAULT_LOCALE];

export const AUTH_ENABLED = true;

export const BRAND = {
  name: APP_NAME,
  publicName: APP_PUBLIC_NAME,
  tagline: "Generic content platform",
};

export const ROUTES = {
  home: "/",
  login: "/login",
  librarySearch: "/library/search",
};

export const API_ROUTES = {
  health: "/health",
  ready: "/ready",
  login: "/auth/login",
  me: "/auth/me",
  refresh: "/auth/refresh",
  logout: "/auth/logout",
  users: "/users",
  librarySearch: "/library/search",
};
