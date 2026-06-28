# Authentication Security Policy

TebaAI authentication protects users and administrative operations through explicit password, token, session and role boundaries.

## Password Storage

Passwords are hashed with Argon2id and may include a server-side pepper loaded through typed configuration.

- plaintext passwords are never persisted or logged;
- bootstrap and E2E credentials come from environment variables;
- documentation and versioned tests contain no shared password fallback.

## Token Lifecycle

Access and refresh credentials have different formats, lifetimes and revocation behavior.

- access tokens are signed JWTs with issuer, audience, subject, role, type, `jti`, issue and expiry claims;
- refresh tokens are opaque random values and only their SHA-256 hashes are persisted;
- refresh rotates the token and detects reuse within a token family;
- logout revokes the relevant session and remains idempotent.

## Authorization

Route guards authenticate first and then enforce the minimum role required by the operation.

Roles are `admin`, `editor` and `viewer`. Administrative user management requires `admin`; library search requires an authenticated user.

## Browser Session

The current frontend token storage is transitional and must not be treated as the final production security design.

Migration to secure `httpOnly` cookies requires an ADR covering CSRF, SameSite, Secure, refresh rotation, logout, cross-origin development and Playwright setup.

## Configuration

Authentication settings follow [[global-configuration-facade-policy]] and are loaded only through `core/config.py`.

Secrets use `SecretStr` or equivalent protected types and are never exposed by public frontend configuration.

## Validation

Auth changes require focused backend tests and browser validation proportional to the changed contract.

Minimum coverage includes password verification, claim validation, refresh rotation/reuse, revocation, role guards and missing-credential behavior.
