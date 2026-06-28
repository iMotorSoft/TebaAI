import { API_BASE_URL, API_ROUTES } from "../global.js";

/**
 * Minimal auth client for TebaAI frontend.
 *
 * Uses fetch() directly against the backend at API_BASE_URL.
 * CORS is configured on the backend for local development origins.
 * localStorage is used as temporary token storage (transient decision,
 * to be replaced by httpOnly cookies in a future phase).
 *
 * Tokens are never logged in full. Passwords are never stored.
 * All storage access is guarded against SSR (server-side rendering).
 */

const BASE = API_BASE_URL.replace(/\/+$/, "");

const isBrowser = typeof window !== "undefined";

const STORAGE_KEYS = {
  ACCESS_TOKEN: "tebaai_access_token",
  REFRESH_TOKEN: "tebaai_refresh_token",
  USER: "tebaai_user",
} as const;

// ── Storage helpers (transient) ───────────────────────────────────────────

function getAccessToken(): string | null {
  if (!isBrowser) return null;
  return localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
}

function setTokens(access: string, refresh: string): void {
  if (!isBrowser) return;
  localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, access);
  localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, refresh);
}

function clearTokens(): void {
  if (!isBrowser) return;
  localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
  localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
  localStorage.removeItem(STORAGE_KEYS.USER);
}

// ── Response types ────────────────────────────────────────────────────────

export interface UserInfo {
  id: string;
  email: string;
  username: string | null;
  role: string;
  is_active: boolean;
}

export interface LoginResult {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserInfo;
}

// ── HTTP helpers ──────────────────────────────────────────────────────────

class AuthError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "AuthError";
    this.status = status;
  }
}

async function apiPost<T>(url: string, body: unknown, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const detail = await res.json().then((d) => d.detail || d.message || res.statusText).catch(() => res.statusText);
    throw new AuthError(detail, res.status);
  }

  return res.json();
}

async function apiGet<T>(url: string, token: string): Promise<T> {
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const detail = await res.json().then((d) => d.detail || d.message || res.statusText).catch(() => res.statusText);
    throw new AuthError(detail, res.status);
  }

  return res.json();
}

// ── Public API ────────────────────────────────────────────────────────────

export async function login(email: string, password: string): Promise<LoginResult> {
  const result = await apiPost<LoginResult>(`${BASE}${API_ROUTES.login}`, { email, password });
  setTokens(result.access_token, result.refresh_token);
  if (isBrowser) {
    localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(result.user));
  }
  return result;
}

export async function getMe(): Promise<UserInfo | null> {
  const token = getAccessToken();
  if (!token) return null;

  try {
    const user = await apiGet<UserInfo>(`${BASE}${API_ROUTES.me}`, token);
    if (isBrowser) {
      localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user));
    }
    return user;
  } catch {
    return null;
  }
}

export async function refresh(refreshToken: string): Promise<{ access_token: string; refresh_token: string } | null> {
  try {
    const result = await apiPost<{ access_token: string; refresh_token: string; token_type: string; expires_in: number }>(
      `${BASE}${API_ROUTES.refresh}`,
      { refresh_token: refreshToken },
    );
    setTokens(result.access_token, result.refresh_token);
    return { access_token: result.access_token, refresh_token: result.refresh_token };
  } catch {
    clearTokens();
    return null;
  }
}

export async function logout(): Promise<void> {
  const refreshToken = isBrowser ? localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN) : null;
  if (refreshToken) {
    try {
      await apiPost<{ status: string }>(`${BASE}${API_ROUTES.logout}`, { refresh_token: refreshToken });
    } catch {
      // Idempotent: clear locally even if server call fails
    }
  }
  clearTokens();
}

export function getStoredUser(): UserInfo | null {
  if (!isBrowser) return null;
  const raw = localStorage.getItem(STORAGE_KEYS.USER);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserInfo;
  } catch {
    return null;
  }
}

export function getStoredAccessToken(): string | null {
  return getAccessToken();
}

export function getStoredRefreshToken(): string | null {
  if (!isBrowser) return null;
  return localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
}

export function isAuthenticated(): boolean {
  return !!getAccessToken();
}
