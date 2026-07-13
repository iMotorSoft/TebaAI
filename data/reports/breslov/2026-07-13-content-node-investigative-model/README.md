# Content Node Investigative Model

Estado: `PASS_WITH_ACCEPTED_LIMITATIONS`.

Se adoptó `ROUTE_D_HYBRID`: PostgreSQL conserva la verdad canónica nueva; las
tablas V2 y los índices Milvus/pgvector permanecen como compatibilidad de
retrieval durante la transición. La migración `015` y el adaptador reproducible
crean evidencia anclada sin alterar corpus ni índices existentes.

Limitación aceptada: el adaptador de páginas V2 no pretende inferir notas,
columnas ni traducciones paralelas. Es deliberadamente conservador: conserva
literal, página, árbol y unidad semántica; los perfiles layout-aware por PDF
son la siguiente ingesta editorial, no una inferencia automática insegura.
