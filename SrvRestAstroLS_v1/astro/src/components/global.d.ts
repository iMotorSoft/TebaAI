export const APP_NAME: "TebaAI";
export const APP_PUBLIC_NAME: "Teba AI";

export const API_BASE_URL: string;

export const DEFAULT_LOCALE: "es";
export const SUPPORTED_LOCALES: readonly ["es", "en", "he"];
export const LOCALE_DIRECTION: Readonly<{
  es: "ltr";
  en: "ltr";
  he: "rtl";
}>;
export const DEFAULT_DIRECTION: "ltr";

export const AUTH_ENABLED: true;

export const BRAND: Readonly<{
  name: "TebaAI";
  publicName: "Teba AI";
  tagline: "Generic content platform";
}>;

export const ROUTES: Readonly<{
  home: "/";
  login: "/login";
  librarySearch: "/library/search";
}>;

export const API_ROUTES: Readonly<{
  health: "/health";
  ready: "/ready";
  login: "/auth/login";
  me: "/auth/me";
  refresh: "/auth/refresh";
  logout: "/auth/logout";
  users: "/users";
  librarySearch: "/library/search";
}>;
