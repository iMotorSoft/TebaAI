# Breslov — Production Deployment Runbook V1

Estado: preparado, no ejecutado. Requiere autorización explícita de una
ventana productiva. No habilitar el worker ni cargar el golden hasta completar
los checks previos.

1. Congelar el HEAD candidato y registrar checksum de artefactos.
2. Hacer backup PostgreSQL y verificar que sea restaurable.
3. Inventariar PostgreSQL, Milvus (colección, PK y metadata) y configuración.
4. Confirmar estrategia de recuperación de documentos, chunks y vectores.
5. Reconciliar los seis jobs históricos por ID; no reprocesar a ciegas.
6. Provisionar un editor con privilegio mínimo y un viewer de smoke.
7. Provisionar storage persistente, absoluto y con permisos mínimos.
8. Configurar flags primary, scope `breslov_primary` y worker; mantenerlo detenido.
9. Aplicar migraciones 040/041 con el runner oficial y auto-migrate desactivado.
10. Desplegar backend del HEAD congelado.
11. Desplegar el frontend correspondiente.
12. Mantener el worker detenido hasta pasar health/config/RBAC.
13. Ejecutar health checks, readiness y smoke autenticado.
14. Verificar RBAC: editor upload permitido y viewer upload `403`.
15. Habilitar el flag primary y arrancar el worker solo después de los checks.
16. Subir un PDF golden autorizado en producción.
17. Verificar `READY`, reconciliación PG↔Milvus y visibilidad publicada.
18. Ejecutar consulta literal como viewer.
19. Ejecutar consulta semántica como viewer y validar grounding.
20. Validar libro, página y fragmento/source de cada cita.
21. Si falla un check: detener worker, deshabilitar primary, preservar candidatos,
    activar rollback de código/configuración y no borrar documentos `ready`.

El gate final
`TEBAAI_BRESLOV_EDITOR_UPLOAD_TO_USER_QUERY_PRODUCTION_V1_PASS` solo se puede
cerrar tras observar en el entorno productivo el circuito completo editor →
upload → ingesta → búsqueda → respuesta grounded → cita.
