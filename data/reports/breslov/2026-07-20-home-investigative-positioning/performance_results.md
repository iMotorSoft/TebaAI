# Resultados de performance

- Build estático: 7 páginas PASS.
- HTML generado de la home: 22.689 bytes.
- CSS compartido existente: 82.396 bytes; CSS específico de la home: 16.356 bytes.
- Islas propias de la home: selector 1.272 bytes, menú 1.445 bytes y acceso por sesión 582 bytes, más runtime Svelte compartido.
- No se añadieron bibliotecas, imágenes, fuentes externas ni dependencias.
- La representación del producto usa HTML y CSS; no depende de una imagen LCP pesada.
- Sólo se hidratan idioma, menú y enlaces dependientes de sesión.
- Respuesta local observada de `/`: HTTP 200 en 0,011 s, sin valor de benchmark contractual.
- No se detectaron respuestas 4xx/5xx ni errores de consola en el recorrido responsive de la home.

No se declara un resultado Lighthouse porque no forma parte de las herramientas reproducibles actuales del repositorio.
