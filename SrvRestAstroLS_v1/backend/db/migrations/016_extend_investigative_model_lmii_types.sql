-- Types required by the LM II layout-aware profile.
ALTER TABLE library_content_units_v2 DROP CONSTRAINT IF EXISTS library_content_units_v2_unit_type_check;
ALTER TABLE library_content_units_v2 ADD CONSTRAINT library_content_units_v2_unit_type_check
CHECK (unit_type IN ('work','part','volume','lesson','lesson_section','halakhic_discourse','chapter','story','prayer','sicha','letter','introduction','appendix','glossary','diagram_collection','note_collection','section','page','index','unknown'));
ALTER TABLE library_content_relations_v2 DROP CONSTRAINT IF EXISTS library_content_relations_v2_relation_type_check;
ALTER TABLE library_content_relations_v2 ADD CONSTRAINT library_content_relations_v2_relation_type_check
CHECK (relation_type IN ('parent_child','is_part_of','is_primary_text_of','is_satellite_of','translates','parallel_translation','explains','comments_on','quotes','quotes_source_for','cites','derives_from','applies','summarizes','defines_term','visualizes','cross_references','same_lesson_section','same_page','same_node','same_semantic_unit','literal_cooccurrence','thematic_relation','bechina_relation','remez_relation','derash_relation','ai_inferred','editorial_only'));
