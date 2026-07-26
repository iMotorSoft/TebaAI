# Acción Modificar

Modificar abre un textarea prellenado, enfoca el editor, respeta IME, Enter y Shift+Enter.

El envío crea una nueva llamada `phase=interpret` con `supersedes_interpretation_id`. El backend interpreta primero y sólo entonces supersede la versión previa, evitando perder una interpretación utilizable si la reinterpretación falla.

No se adquiere pool PostgreSQL ni se ejecuta análisis. La nueva card vuelve a mostrar únicamente `Analizar` y `Modificar`.
