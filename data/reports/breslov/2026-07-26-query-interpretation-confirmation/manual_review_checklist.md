# Checklist de revisión manual

URLs:

- http://127.0.0.1:3008/login
- http://127.0.0.1:3008/research

## Prueba 1

Enviar `tisha beav`.

- [ ] Muestra “Interpreté que desea investigar referencias sobre Tishá BeAv.”
- [ ] Sólo aparecen Analizar y Modificar como acciones principales.
- [ ] No hay resultados antes de Analizar.

## Prueba 2

Pulsar Analizar.

- [ ] Ejecuta una vez.
- [ ] Aparecen LM XV, PDF 262, página impresa 248 y `#85:2`.

## Prueba 3

Enviar `Tisha B'Av`, pulsar Modificar y cambiar a `relación entre Tishá BeAv y los veintiún días`.

- [ ] Aparece la nueva interpretación relacional.
- [ ] Siguen sólo Analizar y Modificar.
- [ ] No hay retrieval antes de Analizar.
- [ ] Analizar ejecuta la consulta modificada.

## Prueba 4

Enviar `donde aparece Oraj Jaim 1`.

- [ ] La card identifica una referencia estructural.
- [ ] Al analizar aparecen LH, PDF 36 y página impresa 18.

## Prueba 5

Enviar `Moshé, tú lo has dicho bien`.

- [ ] La card identifica una frase literal.
- [ ] Al analizar aparecen LMI, PDF 93 y página impresa 73.

## Prueba 6

Enviar una consulta hebrea.

- [ ] El subject se lee en RTL.
- [ ] Analizar y Modificar conservan el orden.
- [ ] El análisis comienza sólo tras Analizar.
