# Root Cause Analysis: Login Session Recovery Navigation Blocked

## Symptoms

- Session card shows email, username, role after navigating to `/login` with valid session
- "Ir a Investigación" link does not navigate
- "Verificar sesión" button does not respond
- "Cerrar sesión" button does not respond
- User must re-enter credentials despite session being recovered

## Root Cause

### Hydration Mismatch (Primary)

The `LoginForm.svelte` component used `$state<UserInfo | null>(getStoredUser())` as the
initial value for the `user` reactive variable. During SSR (server-side rendering),
`getStoredUser()` returns `null` because there is no `localStorage` access. The component
renders the `{:else}` branch: the login form.

On the client, during hydration, `getStoredUser()` finds a valid user in `localStorage`,
so `user` is not null. The component expects to render the `{#if user}` branch: the
session card.

**SSR renders:** `<form>` with email/password inputs
**Client expects:** `<div>` card with user info and buttons

Svelte 5 detects this mismatch and performs a full DOM replacement. During this
replacement process, event handlers attached via `onclick={handler}` can become
detached or fail to bind to the new elements. This leaves the buttons inert.

### Missing `type="button"`

Buttons in the session card did not have an explicit `type="button"` attribute. While
not the primary cause (buttons are outside any `<form>`), this is an accessibility
and correctness concern.

### No Loading/Result States for Verify

`handleRefresh` called `getMe()` and updated `user`, but did not provide:
- Visual feedback during the API call (no loading state)
- Success/error messages after completion

### No Transition State

The component had no intermediary state between SSR (no `localStorage`) and client
(`localStorage` available). This caused a flash from form → card and the hydration
mismatch.

## Fix

1. **Added `checking` state**: Initialized as `$state(true)`. During SSR, renders a
   neutral "Verificando sesión…" placeholder. On client mount, resolves to `false`
   after reading `localStorage`. Eliminates hydration mismatch entirely.

2. **Moved user initialization to `onMount`**: Instead of initializing `user` from
   `getStoredUser()` at the component level (which runs during SSR), we initialize
   in `onMount` (which only runs on the client). This ensures SSR always renders
   the checking state.

3. **Added `verifying` state**: Boolean that tracks when the verify API call is in
   progress. The button shows a spinner and "Verificando…" text while `verifying` is
   true. The button is also `disabled` during verification.

4. **Added `verifyMessage` state**: Displays "Sesión válida." (green) on success or
   "La sesión expiró. Volvé a iniciar sesión." (amber) if the token is invalid. Uses
   `aria-live="polite"` for screen reader announcements.

5. **Added `type="button"`**: Explicit type on both session card buttons.

6. **Proper cleanup in handleLogout**: Clears `verifyMessage` in addition to `user`
   and `error`.

## Prevention

- Components with conditional SSR/client rendering should use an intermediary state
  to avoid hydration mismatches.
- API-dependent UI actions (verify, submit) should always have loading/result states.
- Buttons should always have explicit `type` attributes.
