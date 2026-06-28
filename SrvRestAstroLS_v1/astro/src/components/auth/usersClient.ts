import { API_BASE_URL, API_ROUTES } from "../global.js";

const BASE = API_BASE_URL.replace(/\/+$/, "");

// ── Types matching backend schemas ──────────────────────────────────────

export interface UserInfo {
  id: string;
  email: string;
  username: string | null;
  role: string;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface UserListResponse {
  items: UserInfo[];
  total: number;
}

export interface CreateUserPayload {
  email: string;
  username: string | null;
  password: string;
  role: string;
  is_active: boolean;
}

export interface UpdateUserPayload {
  username?: string | null;
  role?: string;
  is_active?: boolean;
}

// ── Error ───────────────────────────────────────────────────────────────

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ── Helpers ─────────────────────────────────────────────────────────────

async function apiGet<T>(url: string, token: string): Promise<T> {
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const detail = await res.json().then((d) => d.detail || d.message || res.statusText).catch(() => res.statusText);
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

async function apiPost<T>(url: string, token: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().then((d) => d.detail || d.message || res.statusText).catch(() => res.statusText);
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

async function apiPatch<T>(url: string, token: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().then((d) => d.detail || d.message || res.statusText).catch(() => res.statusText);
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

// ── Public API ──────────────────────────────────────────────────────────

export async function listUsers(token: string): Promise<UserListResponse> {
  return apiGet<UserListResponse>(`${BASE}${API_ROUTES.users}`, token);
}

export async function createUser(token: string, payload: CreateUserPayload): Promise<UserInfo> {
  return apiPost<UserInfo>(`${BASE}${API_ROUTES.users}`, token, payload);
}

export async function updateUser(token: string, userId: string, payload: UpdateUserPayload): Promise<UserInfo> {
  return apiPatch<UserInfo>(`${BASE}${API_ROUTES.users}/${userId}`, token, payload);
}

export async function activateUser(token: string, userId: string): Promise<UserInfo> {
  return apiPost<UserInfo>(`${BASE}${API_ROUTES.users}/${userId}/activate`, token);
}

export async function deactivateUser(token: string, userId: string): Promise<UserInfo> {
  return apiPost<UserInfo>(`${BASE}${API_ROUTES.users}/${userId}/deactivate`, token);
}
