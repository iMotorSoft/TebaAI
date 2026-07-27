# Private beta research guest

Fecha: 2026-07-27.

Objetivo: provisionar `guest@tebaai.live` como usuario activo `viewer`, con acceso
autenticado a Breslov Research y sin autoridad administrativa, editorial, de
ingesta o de modificación del corpus.

Estado final:

- `GUEST_USER_PROVISIONING_FULL_PASS`;
- `RESEARCH_READ_ONLY_ROLE_FULL_PASS`;
- `GUEST_AUTHENTICATION_E2E_FULL_PASS`;
- `GUEST_WRITE_DENIAL_FULL_PASS`;
- `PRIVATE_BETA_GUEST_READY`.

El usuario quedó activo, autenticable y limitado al rol canónico `viewer`.
Provisioning, E2E real, denegaciones 20/20, aislamiento, sesiones, regresión
admin, performance y cero cambios de corpus fueron validados.

La cuenta es compartida temporalmente por un grupo pequeño conocido. Esto es
aceptable para la beta inicial, pero no permite atribución, revocación ni límites
por persona. Si la beta continúa, deben crearse cuentas individuales por
invitación.
