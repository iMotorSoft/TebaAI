# Session Contract — Login /login

## Frontend → Backend API Contract

| Endpoint | Method | Auth | Request | Response |
|----------|--------|------|---------|----------|
| `/auth/login` | POST | None | `{email, password}` | `{access_token, refresh_token, token_type, expires_in, user}` |
| `/auth/me` | GET | Bearer token | None | `{id, email, username, role, is_active}` |
| `/auth/logout` | POST | None | `{refresh_token}` | `{status: "ok"}` |

## Token Storage

- `tebaai_access_token` → `localStorage` (JWT)
- `tebaai_refresh_token` → `localStorage` (opaque, 48 bytes)
- `tebaai_user` → `localStorage` (JSON serialized `UserInfo`)

All storage access is guarded by `typeof window !== "undefined"` for SSR safety.

## Session Card Lifecycle

1. SSR renders "Verificando sesión…" placeholder (`checking=true`)
2. Client hydrates, `onMount` fires
3. `getStoredUser()` reads `localStorage`
4. If user + token found → `user = storedUser`, `checking = false` → session card
5. If no stored data → `checking = false` → login form

## Button Behavior

### "Ir a Investigación"
- `<a href="/research">` — real HTML link
- Navigates without JavaScript dependency
- Works in all states (even SSR-only)

### "Verificar sesión"
- Calls `getMe()` → `GET /auth/me` with Bearer token
- States: `idle` → `verifying` → `valid` | `invalid`
- Valid: "Sesión válida." (green alert)
- Invalid: "La sesión expiró. Volvé a iniciar sesión." (amber alert) + switches to login form

### "Cerrar sesión"
- Calls `logout()` → `POST /auth/logout` with refresh token
- Clears all `localStorage` tokens
- Clears `user` state → switches to login form
- `/research` redirects to `/login` after logout

## Expired Session Edge Case

If token is expired when visiting `/login`:
- `getStoredUser()` still returns stored user (stale data)
- Session card shows with stale user info
- Clicking "Verificar sesión" detects expiration → switches to form + shows message
- No redirect loop (`getMe()` is not called on mount for auto-redirect)
