# Morfología hebrea prudente

La forma exacta siempre se conserva y se consulta primero. La normalización de búsqueda aplica NFC y puede retirar niqqud/cantilación sin modificar el texto canónico.

Expansiones controladas:

1. forma exacta;
2. forma sin niqqud;
3. artículo definido `ה` cuando la palabra restante conserva longitud segura;
4. un único prefijo `ו`, `ב`, `כ`, `ל` o `מ` bajo guardas de longitud;
5. alias ortográfico previamente validado;
6. traducción secundaria marcada, nunca evidencia literal.

No hay stemming agresivo, transliteración, inversión, eliminación de letras finales ni generación libre de singular/plural. Por ejemplo, `העקרב` conserva la variante exacta y añade `עקרב` como `definite_article_removed`; `בָּעַקְרָב` conserva exacto, elimina niqqud y sólo después considera el prefijo.
