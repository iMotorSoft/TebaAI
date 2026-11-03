# Decisión de arquitectura — propuesta, NO integración

## A. OCR regional

`TEBAAI_BRESLOV_HEBREW_REGIONAL_OCR_REAL_V1 = PASS_NOT_USEFUL`

Alcance del estado: benchmark real completado y reproducible; **el engine/pack/config probado no se recomienda como fallback automático de la región hebrea principal**. No significa que OCR sea incapaz de rescatar letras: lo hace claramente. Hay elegibilidad SEARCH de fragmentos muy acotados (`אוֹר הַפָּנִים`, línea 143 a 400dpi), pero no de todo el cuerpo167. Niqqud imperfecto y pérdida de folios impiden DISPLAY. Los otros caminos ya recuperan algunos de esos fragmentos; no hay ventaja universal demostrada.

- 3 líneas167: 138 letras, 4 edits a 300/400dpi PSM6 (97.10%); 2 edits a 400dpi PSM7 (98.55%) pero palabras fusionadas y `=` espurio. No mezclar mejores salidas por fixture para simular un engine perfecto.
- `כנ"ל → פנ"ל`, `בחינת → חינת` y `אותה כנ"ל → אותהכנ"ל` son defectos materiales para literal search. Una media alta no los absuelve.
- Subfragmento pointed167: 8/8 letras, orden y límites exactos; 4/5 marks (80%, pierde holam). SEARCH acotado sí, DISPLAY no.
- Header55: recupera 11/11 letras frente a native/historical roto; `37 → 7`, mientras reconstrucción ya recupera heading/folio. No reabrir el folio resolver mediante OCR.
- Línea143: a 400dpi37/37 letras y límites/orden exactos. No certifica resto de página ni niqqud completo; reconstrucción también la conserva.
- Región notas combinadas: OCR_LAYOUT_FAIL. Columnas separadas son mejores, pero native válido sigue preferido.

Principio futuro favorable: **visual bueno + embedded roto + OCR local verificablemente bueno → candidato de fallback REGIONAL**, nunca OCR global. Aún faltan detector/gate de calidad generalizable y muestras independientes para integración. No instalar otra suite pesada ni seguir tuneando este fixture en esta fase.

Propuesta mínima posterior:

1. Native por región conservando geometría/provenance; reutilización histórica sólo donde sea certificada.
2. Gate que detecte Unicode no fiable en región visible (U+FFFD/control, mapas ausentes, cobertura de glyphs). Un conteo de página con texto oculto NO es suficiente.
3. OCR sólo de bbox visible sospechoso, nunca español correcto, notas35/36 ni columnas unidas.
4. Validación regional independiente; abstenerse ante fusiones, letras inciertas, referencias/números perdidos. No `reverse()`, no inserción de letras para coincidir con golden.
5. Elegibilidad SEARCH y DISPLAY separada. Artefacto derivado con engine/pack/dpi/bbox/config/hash; texto canónico y citas nunca sustituidos silenciosamente.

El gate propuesto es un diseño, no código de worker ni detector listo. R167_C_niqqud por sí solo no justifica OCR de todo R167_B. Toda decisión queda offline.

## B. Variantes de búsqueda

`TEBAAI_BRESLOV_HEBREW_ORTHOGRAPHIC_SEARCH_VARIANTS_V1 = BLOCKED`

La cascada de candidatos curados mejora recall **en el conjunto anotado** (3/11 → 11/11) y rechaza6/6 negativos. Embeddings ya encuentran el caso focal top1, pero no distinguen identidad léxica: los negativos entran6/6 top3 y תפילה queda detrás de תפלין. Ni exact+semantic suficiente ni variantes universales certificadas pueden afirmarse.

El prototipo confirma que `פירוש` puede encontrar `פֵּרוּשׁ` sin alterar un byte de la evidencia, con `match_type=orthographic_variant`. `פרוש` devuelve `niqqud_insensitive`, la query pointed devuelve `exact`. La tolerancia NO es identidad textual, corrección ni spellchecker.

Bloqueo preciso: las guardas/contextos son anotaciones manuales del mismo development set, no un desambiguador en retrieval; falta holdout independiente con sentidos alternativos y un snapshot de corpus. No tratar 0/6 falsos positivos como garantía.

Propuesta futura mínima:

- Query original inmutable.
- Exact NFC → representación derivada sin marks → candidatos **dirigidos de lexemas revisados**, con token boundaries, scope/contexto y límite de expansión → semantic.
- `exact > niqqud_insensitive > orthographic_variant > semantic` entre evidencias equivalentes; ninguna variante desplaza un exacto comparable.
- Metadata `original_query`, `expanded_variants`, `rule_id`, `match_type`, razón/contexto; cada resultado cita el source exacto, no la variante.
- Sin borrar todas las י/ו, stems genéricos, afijos automáticos ni equivalencias almacenadas. Desconocidos/ambiguos sólo candidatos o abstención, no corrección silenciosa.
- Whitelist inicial candidata de este benchmark: פירוש/פרוש, עיקר/עקר, תחילה/תחלה, תפילין/תפלין, בבוקר/בבקר, תפילה/תפלה, חידושין/חדושין, עיבור/עבור. No activarla todavía ni declarar todos sus usos seguros.

Siguiente prompt: validar holdout y guardas, luego integración mínima separada si la evidencia alcanza. **READY_FOR_C_REINGEST=NO**, sin worker, extractor, frontend, PG/Milvus ni producción modificados.
