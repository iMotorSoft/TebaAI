from modules.library.zone_candidate_promotion_validator import ZoneCandidate,ZoneCandidatePageContext,validate_zone_candidate
def test_rejects_lesson_candidate_on_diagram_page():
 d=validate_zone_candidate(ZoneCandidate('lesson','text',None,.95),ZoneCandidatePageContext(405,'diagram caption',document_part='diagram'))
 assert d.decision=='reject_candidate'
def test_promotes_verified_quote_only():
 d=validate_zone_candidate(ZoneCandidate('diagram','graphic','Diagramas',.95,'Diagramas'),ZoneCandidatePageContext(403,'Gráficos-Diagramas',document_part='diagram'))
 assert d.decision=='promote_candidate'
