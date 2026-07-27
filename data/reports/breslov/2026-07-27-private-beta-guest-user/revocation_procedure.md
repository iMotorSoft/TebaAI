# Rotación y revocación

## Rotar contraseña

1. Cargar el nuevo secreto en `TEBAAI_GUEST_PASSWORD` mediante entrada segura.
2. Ejecutar el provisioner con `--email guest@tebaai.live --rotate-password`.
3. Desasignar la variable del entorno.
4. Confirmar login nuevo y rechazo del secreto anterior.

La rotación revoca todas las refresh sessions del guest.

## Desactivar y revocar

1. Un administrador autenticado invoca
   `POST /users/{guest_user_id}/deactivate`.
2. El backend marca el usuario inactivo, sincroniza autoridad y revoca sus
   refresh sessions en la misma transacción.
3. Confirmar rechazo de login, refresh y access JWT previo.

## Reactivar

Un administrador invoca `POST /users/{guest_user_id}/activate`; luego debe
rotarse la contraseña mediante el mecanismo seguro anterior antes de compartir
acceso.
