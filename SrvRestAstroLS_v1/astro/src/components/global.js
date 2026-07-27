export const APP_NAME = "TebaAI";
export const APP_PUBLIC_NAME = "Teba AI";

// -- Backend REST endpoint (manual DEV/PRO selection) --
// All API clients must import API_BASE_URL from here, not hardcode URLs.
// PRO uses the same-origin /api reverse-proxy path.
const URL_REST_DEV = "http://127.0.0.1:7008";
const URL_REST_PRO = "";
const IS_REST_PRO = false; // Manual toggle: true for a production build.

const REST_BASE_URL = IS_REST_PRO ? URL_REST_PRO : URL_REST_DEV;
// @lat: [[global-configuration-facade-policy]]
export const API_BASE_URL = `${String(REST_BASE_URL || "").replace(/\/+$/, "")}${IS_REST_PRO ? "/api" : ""}`;

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
  research: "/research",
  librarySearch: "/library/search",
  relationQa: "/library/relation-qa",
  investigativeQa: "/library/investigative-qa/v1",
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
  relationQa: "/library/relation-qa",
  investigativeQa: "/library/investigative-qa/v1",
};
