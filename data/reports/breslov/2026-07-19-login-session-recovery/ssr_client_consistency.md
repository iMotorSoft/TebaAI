# SSR/Client Consistency — LoginForm.svelte

## Before Fix

| State | SSR | Client (hydration) | DOM after hydration |
|-------|-----|-------------------|-------------------|
| No session | Form | Form ✅ | Form ✅ |
| Valid session | Form ❌ | Card ❌ (mismatch) | Card with potential handler loss |

**Problem**: SSR renders form, client expects card. Svelte 5 detects mismatch,
replaces DOM. Event handlers may detach during replacement.

## After Fix

| State | SSR | Client (1st render) | Client (onMount) | DOM |
|-------|-----|-------------------|-------------------|-----|
| No session | "Verificando..." | "Verificando..." ✅ | Form ✅ | Matches |
| Valid session | "Verificando..." | "Verificando..." ✅ | Card ✅ | Matches |

All three states now have SSR/Client consistency during hydration:
- `checking=true` during SSR → placeholder rendered
- `checking=true` during client hydration → same placeholder
- `onMount` resolves state → either form or card
- No hydration mismatch → no DOM replacement → event handlers preserved

## Testing

Verified 10/10 consecutive times with Playwright:
- No console errors
- All buttons functional
- Navigation works
- Verify works
- Logout works
- `/research` protected after logout
