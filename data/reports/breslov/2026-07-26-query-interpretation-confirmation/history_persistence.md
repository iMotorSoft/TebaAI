# Historial y persistencia

La consulta crea un único turno. Interpretación y respuesta viven en ese turno, por lo que Analizar no duplica la pregunta.

Una interpretación pendiente se guarda en `sessionStorage` con consulta, ID, conversación y contrato validado. Reload restaura la card y sus dos acciones. Nueva investigación elimina el pendiente y genera otra conversación. El historial máximo existente de 15 preguntas se conserva.

La persistencia es por pestaña; el backend impide cruces de usuario y conversación.
