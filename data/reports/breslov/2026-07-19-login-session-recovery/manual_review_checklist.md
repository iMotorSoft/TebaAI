# Manual Review Checklist

- [x] Defect reproduced: login session card buttons inert
- [x] Root cause documented: hydration mismatch
- [x] Session backend confirmed: /auth/me returns 200
- [x] Real link to /research: `<a href="/research">` works without JS
- [x] Works without JS: link functions, buttons gracefully degrade
- [x] Hydration fixed: checking state eliminates SSR/client mismatch
- [x] Verify session works: states idle → verifying → valid/invalid
- [x] Logout works: clears tokens, switches to form
- [x] Cookie/token invalidated: localStorage cleared on logout
- [x] Refresh stable: page reload maintains session
- [x] New tab stable: opening /login in new tab shows session card
- [x] SSR/client coherent: all 3 states match during hydration
- [x] Expired session handled: verify detects expiration, shows message
- [x] Accessibility: type="button", aria-live, role="status", role="alert"
- [x] Responsive: DaisyUI card adapts to all viewports
- [x] Frontend tests: 3 E2E tests for session recovery
- [x] Backend auth tests: 47 passed
- [x] E2E principal: full flow login→research→login→verify→logout→re-login
- [x] 10/10 regression: 10 consecutive passes
- [x] Full Playwright suite: 45 passed
- [x] pnpm check: 0 errors
- [x] pnpm build: 7 pages
- [x] LAT check: PASS
- [x] git diff --check: PASS
- [x] Secrets: none detected
- [x] Backend active: http://127.0.0.1:7008
- [x] Astro active: http://127.0.0.1:3008
- [ ] Commit created

## Ready for manual review

Access:

- http://127.0.0.1:3008/login
- http://127.0.0.1:3008/research
