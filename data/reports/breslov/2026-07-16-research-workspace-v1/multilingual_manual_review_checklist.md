# Revisión manual multilingüe

Usar las credenciales administrativas configuradas en el entorno. No copiar credenciales a reportes.

- Login: http://127.0.0.1:3008/login
- Workspace: http://127.0.0.1:3008/research

## Pruebas

- [ ] `אתה מחפש איפה נמצא מושג העקרב.` se interpreta como concepto `עקרב`, devuelve fuentes y no busca la oración completa.
- [ ] `איפה נמצא המושג עקרב` devuelve el mismo concepto.
- [ ] `dónde aparece עקרב` mantiene español como instrucción y hebreo como sujeto.
- [ ] `where is עקרב mentioned` mantiene inglés como instrucción y hebreo como sujeto.
- [ ] `איפה מופיע תהלתי אחטם לך` se interpreta como `literal_lookup`.
- [ ] `מה הקשר בין דם לדיבור` se interpreta como relación y exige coevidencia.
- [ ] `ומה בליקוטי הלכות` conserva `עקרב` y aplica scope Likutey Halajot.
- [ ] `תראה לי את המקור העיקרי` abre la evidencia principal validada.
- [ ] `ת ְּ הִ לָּ ת ִ י אֶ חְ ט ָ ם לָ ך donde esta` conserva página PDF 96 e impresa 76.
- [ ] En desktop, tablet y móvil no hay overflow; hebreo usa RTL y metadata LTR.

El aviso de fallback de IA debe aparecer únicamente dentro de “Detalles de la consulta”; la consulta debe seguir funcionando mediante el analizador determinístico.
