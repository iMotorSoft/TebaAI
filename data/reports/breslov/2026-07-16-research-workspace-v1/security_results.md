# Seguridad

Markdown pasa por Marked y DOMPurify con allowlist y prohibición explícita de contenido activo, imágenes, embeds, handlers, estilos, `javascript:`, `vbscript:` y `data:`. Los artefactos automáticos de Playwright están deshabilitados para evitar capturas o traces de credenciales. Los screenshots del reporte se toman sólo después del login.
