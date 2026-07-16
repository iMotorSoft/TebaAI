# Authentication results

The two administrative E2E environment variables were present in the Playwright process; their values were never printed, recorded, or committed.

- Correct administrative login: PASS.
- Invalid synthetic credentials: PASS (401 and readable browser alert).
- Session display, token presence in transient browser storage, and `/auth/me`: PASS.
- Logout clears the visible local session: PASS.
- Unauthenticated administration redirect: PASS.
- Authenticated `/admin/users`: PASS.
- Authenticated protected search and Relation QA regression: PASS.

Safe browser evidence is in `screenshots/auth/`: the unfilled login form, a clipped session-status message, and a clipped protected-route heading. No credential value, token, or user email is present in those captures.
