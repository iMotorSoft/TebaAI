# Content Manager Premium UX — Política visual vinculante

> **Referencia canónica para cualquier desarrollo del Gestor de Contenidos.**
> Todo agente que trabaje en la UI del Content Manager debe leer este documento
> antes de escribir código. El cumplimiento de esta política es condición para
> cerrar el gate visual `TEBAAI_CONTENT_MANAGER_PREMIUM_UX_V1_PASS`.

El Gestor de Contenidos debe reflejar la identidad editorial premium de
Breslov Research, reutilizando sus tokens visuales, tipografías y patrones de
navegación. No debe diseñarse como un panel administrativo independiente.

---

## 1. Principio visual obligatorio

El Gestor de Contenidos **no debe diseñarse como un panel administrativo
independiente ni como una consola técnica genérica**. Debe sentirse como una
extensión natural de:

- la página premium de Breslov Research;
- el workspace `/research`;
- su identidad editorial, tipográfica y visual;
- sus patrones de navegación, superficies, espaciado y jerarquía.

**Antes de crear componentes nuevos**, inventariar obligatoriamente:

```
layouts existentes
tokens de diseño
tipografías
colores
bordes
radios
sombras
botones
campos
cards
headers
navegación
estados de carga
mensajes
componentes responsive
soporte RTL
```

Reutilizar los componentes y tokens existentes siempre que sea posible.
**No crear un segundo sistema visual.**

---

## 2. Identidad del producto

Nombre principal visible: **Gestor de Contenidos**

Descripción secundaria: **Carga, procesamiento y validación de fuentes documentales**

La interfaz debe mantener la identidad:

```
רבי נחמן
REBE NAJMÁN
BRESLOV RESEARCH
```

La marca debe acompañar la experiencia sin ocupar espacio excesivo ni competir
con la tarea administrativa.

**No usar como título principal**: `PDF Upload Console`, `Ingestion Dashboard`,
`Admin Content`, `Editor técnico`. Estos nombres pueden existir únicamente en
código, tests o documentación interna.

---

## 3. Carácter visual

La experiencia debe transmitir:

```
seriedad editorial
investigación
precisión
confianza
cuidado documental
tecnología discreta
calidad premium
```

Debe **evitar**:

```
dashboard SaaS genérico
apariencia de backoffice antiguo
tablas densas como superficie principal
colores estridentes
gradientes decorativos excesivos
iconografía infantil
bordes en todos los elementos
sombras pesadas
formularios técnicos interminables
mensajes internos expuestos al usuario
```

El resultado debe ser **sobrio, cálido y editorial**, no frío ni puramente
técnico.

---

## 4. Arquitectura de la pantalla

La pantalla principal debe organizarse en tres niveles:

1. **Encabezado**: nombre del producto, descripción, acción principal "Nueva carga"
   (visible pero no agresiva).
2. **Resumen operativo**: indicadores compactos (en procesamiento, pendientes de
   revisión, con advertencias, fallidos). No convertir en dashboard analítico.
3. **Cargas recientes**: documentos recientes con título, idioma, fecha, estado,
   etapa actual, páginas, responsable, acción contextual. Desktop: tabla
   editorial o lista estructurada. Móvil: cards.

---

## 5. Flujo "Nueva carga"

Etapas visibles: `1. Archivo → 2. Información → 3. Confirmación → 4. Procesamiento → 5. Resultado`

Cada etapa muestra solamente la información necesaria para la decisión actual.
El usuario debe comprender siempre: dónde está, qué está ocurriendo, qué falta,
qué ocurrirá después, si la acción todavía puede cancelarse.

### Selección del archivo

Zona de carga amplia, limpia y editorial. Permitir drag, click y teclado.

Texto principal: **"Seleccioná una fuente documental"**

Texto secundario: **"PDF de hasta {max_upload_size}. El archivo será validado antes de iniciar su procesamiento."**

Después de seleccionar, reemplazar el dropzone por una ficha con: nombre,
tamaño, páginas, idioma, estado de validación, SHA-256 abreviado en detalle
técnico.

### Metadata mínima

Mostrar únicamente: título de la obra, idioma principal, familia documental
(opcional), nota administrativa (opcional). Los campos técnicos resueltos por
backend deben quedar en "Detalles técnicos" contraíble.

### Confirmación

Ficha premium con: archivo, título, idioma, páginas, tamaño, familia,
resultado de duplicados, proceso propuesto, estado final esperado.

Mensaje principal: **"El documento será procesado y quedará como candidato para revisión."**

Advertencia: **"Esta operación no publica ni aprueba el documento."**

Acción principal: **"Iniciar procesamiento"**. Acción secundaria: **"Volver"**.

**No usar**: Publicar, Aprobar, Guardar y publicar, Enviar a producción.

### Procesamiento

Etapas con lenguaje editorial (no técnico):

```
Validando el archivo
Extrayendo las páginas
Normalizando el contenido
Organizando las secciones
Preparando la búsqueda
Generando el índice
Verificando el resultado
```

Cada etapa tiene estado: pendiente, en curso, completada, con advertencias,
fallida. Barra general solo como apoyo. No inventar precisión temporal o
porcentajes injustificados.

Mensaje: **"Podés salir de esta pantalla. El procesamiento continuará y quedará registrado en el historial."** (solo si la persistencia está soportada).

### Resultado exitoso

Título: **"Documento procesado"**. Estado editorial: **"Candidato para revisión"**.

Resumen: `{pages} páginas`, `{textual_pages} páginas con contenido`,
`{chunks} fragmentos preparados`, `{embeddings} registros de búsqueda`.

Acciones: **"Abrir diagnóstico"**, **"Probar en Investigación"**,
**"Volver al gestor"**. Si se permite probar, mostrar:
**"Este documento todavía no fue aprobado."**

#### Decisión editorial posterior

Cuando el despliegue habilite explícitamente la ingesta del scope primario,
el resultado reconciliado puede ofrecer una segunda decisión separada:
**"Publicar para consulta"**.

Esta acción nunca forma parte de la confirmación de carga, debe exigir una
confirmación editorial explícita y solo puede promover un `test_candidate`
cuyos chunks, embeddings y vectores hayan sido reconciliados exactamente. La
UI no debe mostrarla en scopes E2E ni sugerir que completar la ingesta equivale
a publicar.

### Resultado con advertencias

Tratamiento visual prudente, no alarmista. Título:
**"Documento procesado con observaciones"**.

Explicación: **"El documento quedó disponible para revisión, pero se detectaron aspectos que conviene verificar."**

Mostrar primero las observaciones editoriales; los códigos técnicos en
diagnóstico expandible.

### Fallos

Título: **"No se pudo completar el procesamiento"**. Mostrar: qué etapa falló,
qué puede hacer el usuario, si el archivo sigue disponible, si puede
reintentarse. Código técnico solo como información secundaria.

**No mostrar** stack traces, paths internos ni payloads.

---

## 6. Historial y detalle

Estados visibles: Validando, Esperando confirmación, En procesamiento,
Candidato para revisión, Con observaciones, Fallido, Cancelado.

Cada documento abre un detalle con: resumen, línea de tiempo, resultado,
advertencias, historial de intentos, auditoría básica, diagnóstico técnico
contraíble. No abrir toda la información técnica de forma predeterminada.

---

## 7. Jerarquía de información

Tres niveles:

| Nivel | Contenido |
|---|---|
| Principal | documento, estado, progreso, resultado, acciones |
| Secundario | idioma, familia, páginas, observaciones, historial |
| Técnico (contraíble) | job_id, upload_id, document_id, SHA-256, pipeline, chunks, embeddings, PG↔Milvus, warning/error codes, attempt, timestamps |

**No mezclar los tres niveles en una única tabla.**

---

## 8. Desktop y móvil

**Desktop**: ancho de lectura controlado, espaciado amplio, paneles con
jerarquía, tabla o lista de cargas recientes, detalle en panel o página
dedicada. No ocupar innecesariamente todo el ancho.

**Móvil (390 × 844)**: cards, título/estado/etapa primero, acciones de ancho
completo cuando corresponda, botones con área táctil suficiente, detalles
técnicos contraídos, evitar tablas horizontales y paneles laterales. El
proceso completo debe poder realizarse sin zoom ni scroll horizontal.

---

## 9. Multilingüe y RTL

La interfaz debe estar preparada para español, inglés y hebreo. El idioma del
documento no cambia automáticamente el de la interfaz.

---

## 10. Accesibilidad

Debe garantizarse navegación completa por teclado, foco visible y etiquetado
correcto de campos. Los estados deben diferenciarse por texto e icono, no solo
por color.

---

## 11. Animación

Usar transiciones cortas y discretas, con feedback inmediato. Respetar
`prefers-reduced-motion`.

---

## 12. Estados vacíos

Estado inicial: **"Todavía no hay documentos cargados"**

Texto secundario: **"Las nuevas fuentes documentales aparecerán aquí junto con su estado de procesamiento."**

Acción: **"Cargar primer documento"**. No mostrar una tabla vacía.

---

## 13. Criterio visual de aceptación

El gate `TEBAAI_CONTENT_MANAGER_PREMIUM_UX_V1_PASS` solo puede cerrarse cuando:

```
el gestor parece parte del mismo producto que /research
no existe un dashboard visual paralelo
los tokens existentes fueron reutilizados
el flujo es comprensible sin conocer el pipeline
la información técnica está subordinada
desktop y móvil conservan jerarquía
hebreo y RTL funcionan correctamente
los estados de error y advertencia son legibles
la pantalla transmite calidad editorial premium
```

**No cerrar** el gate visual si:

```
parece una plantilla administrativa genérica
se agregaron colores o componentes inconsistentes
la tabla domina toda la experiencia
los nombres técnicos aparecen como lenguaje principal
el flujo móvil depende de scroll horizontal
el progreso se limita a un spinner
los detalles técnicos compiten con la acción principal
la estética premium solo se validó subjetivamente
```

---

## 14. Validación visual obligatoria

Capturas y validaciones requeridas para todos los estados:

```
estado vacío
archivo seleccionado
archivo válido
duplicado detectado
confirmación
procesamiento
resultado exitoso
resultado con advertencias
fallo
historial
detalle técnico expandido
```

Viewports: **1440 × 900**, **1024 × 768**, **390 × 844**.

Comparar visualmente con las superficies existentes de Breslov Research.
Documentar componentes reutilizados, tokens reutilizados, componentes nuevos
(con justificación), diferencias desktop/móvil, comportamiento RTL.

La validación no debe limitarse a comprobar que la página renderiza.

---

## 15. Gates

```text
Gate funcional:
TEBAAI_PDF_UPLOAD_INGESTION_CONSOLE_V1_DEV_READY

Gate visual:
TEBAAI_CONTENT_MANAGER_PREMIUM_UX_V1_PASS
```

El cierre general de la fase Content Manager requiere ambos gates.

**Regla determinante**: no aprobar una implementación técnicamente completa si
visualmente parece un dashboard administrativo genérico.
