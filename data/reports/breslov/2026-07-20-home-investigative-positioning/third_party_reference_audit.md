# Auditoría de referencias de terceros

## Estado anterior

El hero contenía una tarjeta de colaboración institucional con nombre completo, sigla y un claim de trabajo conjunto. El componente fue retirado, no ocultado mediante CSS.

## Alcance revisado

- home renderizada;
- header y footer públicos;
- SEO y metadata;
- componentes públicos de la home;
- navegación y menú móvil;
- textos alternativos y representación del producto;
- tests de contenido;
- rótulo público de la edición española en `/research`.

Los patrones prohibidos permanecen únicamente como literales de control dentro de tests y scripts de barrido. No forman parte del contenido público renderizado.
