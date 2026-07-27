# Provisioning

Herramienta: `backend/scripts/provision_research_guest.py`.

Contrato:

- email obligatorio por `--email`;
- password sólo desde `TEBAAI_GUEST_PASSWORD` mediante `SecretStr`;
- normalización y validación de email;
- creación activa con rol `viewer` y membresías completas;
- ejecución repetida idempotente;
- rotación sólo con `--rotate-password`;
- cuenta elevada preexistente bloqueada salvo `--allow-demotion` explícito;
- degradación o rotación revoca refresh sessions;
- una única transacción sobre la base `tebaai`;
- salida sin password, hash, token ni objeto completo.

Resultado: usuario creado, activo, email normalizado, rol `viewer`, hash
Argon2id y membresías `viewer` en organización, workspace y proyecto. La
contraseña temporal fue eliminada del entorno después de las validaciones.
