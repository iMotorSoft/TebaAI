# ADR — Modelo documental investigativo LM II

No se realiza una edición crítica: todo texto legible entra o permanece en el corpus y la página física es el ancla mínimo. Clasificación y relación lógica son capas separadas. Los comentaristas visibles se modelan como satélites derivados, citable y buscables, sin reemplazar el texto primario que los contiene. Las continuaciones inciertas quedan como fragmentos citables o enlaces probables; no se inventa `continuation_of`.

Rollback: eliminar únicamente nodos con `metadata_json.investigative_derivative=true`; los nodos y literales originales quedan intactos.
