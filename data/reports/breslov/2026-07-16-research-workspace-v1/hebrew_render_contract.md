# Contrato de render hebreo

1. `quote` es el literal canónico y conserva la identidad estable.
2. `display_quote`/`display_snippet` son derivados de presentación opcionales y declaran su método.
3. Un bloque hebreo recibe `lang="he"`, `dir="rtl"` y `research-hebrew-text`.
4. Un bloque latino recibe `dir="ltr"`; un bloque genuinamente mixto recibe `dir="auto"` y sus runs hebreos inline se aíslan con `bdi lang="he" dir="rtl"`.
5. Metadata bibliográfica se renderiza en un contenedor LTR separado.
6. Marked no es autoridad para `lang`/`dir`. DOMPurify elimina atributos no confiables y el frontend asigna sólo valores allowlisted después de sanitizar.
7. El DOM conserva el orden lógico; CSS nunca reordena contenido.
8. No se permiten inversión manual, `word-break:break-all`, justificado, tracking editorial latino ni cursiva sobre hebreo.
9. Snippets frontend usan `Intl.Segmenter` con fallback por grapemas/palabras.
10. Vaciar el composer restaura LTR; un único carácter hebreo aislado no cambia la dirección.
