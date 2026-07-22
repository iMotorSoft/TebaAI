# Seguridad

PASS:

- Markdown/HTML/XSS cubiertos por DOMPurify y tests de `script`, handlers, iframe, object, embed, `javascript:` y `data:`;
- C0/C1, replacement char, mojibake, bidi controls y Unicode cubiertos por batch;
- raw audit text permanece fuera del DOM y del narrative;
- SQL usa parámetros; no se agregó interpolación de consultas;
- strings de request conservan límite de 1000 caracteres;
- no se registran raw snippets completos en producción;
- scan final sin credenciales, bearer tokens, cookies ni storage states;
- reportes no contienen prompts internos ni razonamiento privado.
