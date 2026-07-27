# Política de manejo de contraseña

- El secreto no se acepta como argumento, archivo, URL, fixture ni fallback.
- `core/config.py` es el único lector de entorno y lo representa como
  `SecretStr`.
- Provisioning falla cerrado si `TEBAAI_GUEST_PASSWORD` está ausente.
- Playwright omite E2E guest si `TEBAAI_E2E_GUEST_PASSWORD` está ausente.
- La UI y los tests nunca imprimen ni capturan el campo de contraseña.
- Los reportes no contienen password, hash, JWT, cookies ni storage state.
- Tras provisioning, el operador debe ejecutar `unset TEBAAI_GUEST_PASSWORD`.
