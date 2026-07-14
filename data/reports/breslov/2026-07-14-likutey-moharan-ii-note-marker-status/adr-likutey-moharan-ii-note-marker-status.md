# ADR — Estado de marcador de notas

“Título” no describe el dato: se usan `marker_kind`, `marker_value` y `marker_status`. `visible_note_number` sólo conserva texto explícito; `probable_note_number` queda nulo salvo evidencia independiente. Un marcador o continuación probable no crea relación editorial. Rollback: las columnas son aditivas y el backfill sólo modifica sus valores.
