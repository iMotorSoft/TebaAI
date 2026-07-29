"""Auditable, data-driven catalog of Breslov concepts with aliases, transliterations and translations.

Every concept has a canonical label, validated aliases, transliteration variants, Hebrew
orthography, translations and typed relations. The catalog is the single source of truth
for what terms exist in the corpus — the AI may suggest candidates *from* this catalog
but never invent outside it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


from typing import Literal

RelationKind = Literal[
    "exact_alias",
    "transliteration",
    "translation",
    "hebrew_original",
    "related_concept",
    "thematic_parallel",
]


@dataclass(frozen=True)
class ConceptRelation:
    label: str
    relation_type: RelationKind


@dataclass(frozen=True)
class ConceptEntry:
    """A single concept in the Breslov catalog."""

    concept_id: str
    canonical_label: str
    language: str  # interface language (es, en, he)
    hebrew: str | None = None
    aliases: tuple[str, ...] = ()
    transliterations: tuple[str, ...] = ()
    translations: tuple[str, ...] = ()
    related_concepts: tuple[ConceptRelation, ...] = ()

    def all_searchable_forms(self) -> set[str]:
        """Every form under which this concept can be retrieved or suggested."""
        forms = {
            self.canonical_label,
            self.canonical_label.lower(),
        }
        for a in self.aliases:
            forms.add(a)
            forms.add(a.lower())
        for t in self.transliterations:
            forms.add(t)
            forms.add(t.lower())
        for tr in self.translations:
            forms.add(tr)
            forms.add(tr.lower())
        if self.hebrew:
            forms.add(self.hebrew)
        return forms


# ---------------------------------------------------------------------------
# Master catalog
# ---------------------------------------------------------------------------

CATALOG: tuple[ConceptEntry, ...] = (
    ConceptEntry(
        concept_id="azamra",
        canonical_label="Azamra",
        language="es",
        hebrew="אזמרה",
        aliases=("azamra",),
        transliterations=("azamra",),
        translations=(),
        related_concepts=(),
    ),
    ConceptEntry(
        concept_id="hitbodedut",
        canonical_label="Hitbodedut",
        language="es",
        hebrew="התבודדות",
        aliases=("hitbodedut", "plegaria personal", "oración personal"),
        transliterations=("hisbodedus", "hitbodedus", "hitbodédut"),
        translations=("personal prayer", "secluded prayer", "plegaria personal", "oración personal"),
        related_concepts=(
            ConceptRelation("Tefilá", "related_concept"),
            ConceptRelation("plegaria", "translation"),
            ConceptRelation("soledad espiritual", "thematic_parallel"),
            ConceptRelation("conversación con Dios", "thematic_parallel"),
            ConceptRelation("oración", "translation"),
        ),
    ),
    ConceptEntry(
        concept_id="tefila",
        canonical_label="Tefilá",
        language="es",
        hebrew="תפילה",
        aliases=("tefilá", "tefila", "plegaria", "oración"),
        transliterations=("tefilah", "tefilla", "tfila"),
        translations=("prayer", "oración", "plegaria"),
        related_concepts=(
            ConceptRelation("Hitbodedut", "related_concept"),
            ConceptRelation("plegaria personal", "thematic_parallel"),
        ),
    ),
    ConceptEntry(
        concept_id="emuna",
        canonical_label="Emuná",
        language="es",
        hebrew="אמונה",
        aliases=("emuná", "emuna", "fe"),
        transliterations=("emunah",),
        translations=("faith", "fe", "emunah"),
        related_concepts=(
            ConceptRelation("Bitajón", "related_concept"),
            ConceptRelation("confianza", "thematic_parallel"),
        ),
    ),
    ConceptEntry(
        concept_id="tzadik",
        canonical_label="Tzadik",
        language="es",
        hebrew="צדיק",
        aliases=("tzadik", "tsadik", "justo", "righteous"),
        transliterations=("tzadick", "tsadik", "tsadick", "zadik"),
        translations=("righteous one", "justo", "sabio"),
        related_concepts=(
            ConceptRelation("Rebe Najmán", "related_concept"),
            ConceptRelation("Rabí Natán", "related_concept"),
            ConceptRelation("justo", "translation"),
        ),
    ),
    ConceptEntry(
        concept_id="daat",
        canonical_label="Da'at",
        language="es",
        hebrew="דעת",
        aliases=("da'at", "daat", "conocimiento"),
        transliterations=("daas", "da'as"),
        translations=("knowledge", "consciousness", "conocimiento", "sabiduría"),
        related_concepts=(
            ConceptRelation("sabiduría", "thematic_parallel"),
            ConceptRelation("conocimiento divino", "thematic_parallel"),
        ),
    ),
    ConceptEntry(
        concept_id="simja",
        canonical_label="Simjá",
        language="es",
        hebrew="שמחה",
        aliases=("simjá", "simja", "alegría", "alegria"),
        transliterations=("simcha", "simkha"),
        translations=("joy", "happiness", "alegría", "felicidad"),
        related_concepts=(
            ConceptRelation("alegría", "translation"),
            ConceptRelation("Atzvut", "related_concept"),
            ConceptRelation("felicidad", "thematic_parallel"),
        ),
    ),
    ConceptEntry(
        concept_id="atzvut",
        canonical_label="Atzvut",
        language="es",
        hebrew="עצבות",
        aliases=("atzvut", "atsvut", "tristeza", "melancolía", "melancolia"),
        transliterations=("atzvus", "atsvus", "atzves"),
        translations=("sadness", "melancholy", "despondency", "tristeza", "melancolía"),
        related_concepts=(
            ConceptRelation("Simjá", "related_concept"),
            ConceptRelation("tristeza", "translation"),
            ConceptRelation("alegría", "thematic_parallel"),
        ),
    ),
    ConceptEntry(
        concept_id="escorpion",
        canonical_label="Escorpión",
        language="es",
        hebrew="עקרב",
        aliases=("escorpión", "escorpion", "escorpiones", "escorpoion", "scorpion", "עקרב", "עקרבים"),
        transliterations=(),
        translations=("scorpion", "escorpión", "עקרב"),
        related_concepts=(
            ConceptRelation("miedo", "thematic_parallel"),
            ConceptRelation("temor", "thematic_parallel"),
            ConceptRelation("serpiente", "thematic_parallel"),
        ),
    ),
    ConceptEntry(
        concept_id="yirat_shamayim",
        canonical_label="Yirat Shamayim",
        language="es",
        hebrew="יראת שמים",
        aliases=("yirat shamayim", "temor de Dios", "temor reverencial"),
        transliterations=("yiras shomayim", "yirat shomayim", "yiras shamayim"),
        translations=("fear of Heaven", "awe of God", "temor de Dios", "temor reverencial"),
        related_concepts=(
            ConceptRelation("temor", "translation"),
            ConceptRelation("Emuná", "related_concept"),
        ),
    ),
    ConceptEntry(
        concept_id="brit",
        canonical_label="Brit",
        language="es",
        hebrew="ברית",
        aliases=("brit", "pacto", "alianza", "pureza sexual"),
        transliterations=("bris", "brit"),
        translations=("covenant", "sexual purity", "pacto", "alianza"),
        related_concepts=(
            ConceptRelation("pureza", "thematic_parallel"),
            ConceptRelation("santidad", "thematic_parallel"),
        ),
    ),
    ConceptEntry(
        concept_id="tikun_haklali",
        canonical_label="Tikún HaKlali",
        language="es",
        hebrew="תיקון הכללי",
        aliases=("tikún haklali", "tikun haklali", "tikún haKlali"),
        transliterations=("tikun haklali", "tikun haklaly", "tikkun haklali"),
        translations=("General Remedy", "Remedio General", "Tikún HaKlali"),
        related_concepts=(
            ConceptRelation("Rebe Najmán", "related_concept"),
            ConceptRelation("Diez Salmos", "thematic_parallel"),
        ),
    ),
    ConceptEntry(
        concept_id="likutey_moharan",
        canonical_label="Likutey Moharán",
        language="es",
        hebrew="ליקוטי מוהרן",
        aliases=("likutey moharán", "likutey moharan", "likutey mohorán"),
        transliterations=("likutei moharan", "likutei moharán", "likute moharan", "likutey moharan"),
        translations=("Likutey Moharán", "Likutey Moharan"),
        related_concepts=(
            ConceptRelation("Rebe Najmán", "related_concept"),
            ConceptRelation("Rabí Natán", "related_concept"),
        ),
    ),
    ConceptEntry(
        concept_id="rabi_natan",
        canonical_label="Rabí Natán",
        language="es",
        hebrew="רבי נתן",
        aliases=("rabí natán", "rabi natan", "rabí noson"),
        transliterations=("rabbi natan", "rabi noson", "reb noson", "rabbi noson"),
        translations=("Rabbi Nathan", "Rabí Natán"),
        related_concepts=(
            ConceptRelation("Rebe Najmán", "related_concept"),
            ConceptRelation("Likutey Moharán", "related_concept"),
        ),
    ),
    ConceptEntry(
        concept_id="rebe_najman",
        canonical_label="Rebe Najmán",
        language="es",
        hebrew="רבי נחמן",
        aliases=("rebe najmán", "rebe najman", "rabí najmán", "rabi najman", "rebe najmán"),
        transliterations=("rebbe nahman", "rebbe nachman", "rabi nahman", "reb nahman", "nachman"),
        translations=("Rebbe Nachman", "Rebe Najmán", "Rabí Najmán"),
        related_concepts=(
            ConceptRelation("Rabí Natán", "related_concept"),
            ConceptRelation("Likutey Moharán", "related_concept"),
            ConceptRelation("Tikún HaKlali", "related_concept"),
        ),
    ),
    ConceptEntry(
        concept_id="zohar",
        canonical_label="Zohar",
        language="es",
        hebrew="זהר",
        aliases=("zohar", "zóhar", "zohar"),
        transliterations=("zohar",),
        translations=("Zohar", "Libro del Esplendor"),
        related_concepts=(
            ConceptRelation("Cabbalá", "related_concept"),
            ConceptRelation("Rashbí", "related_concept"),
        ),
    ),
    ConceptEntry(
        concept_id="teshuva",
        canonical_label="Teshuvá",
        language="es",
        hebrew="תשובה",
        aliases=("teshuvá", "teshuva", "arrepentimiento", "retorno"),
        transliterations=("teshuvah", "teshuva", "tshuva"),
        translations=("repentance", "return", "arrepentimiento", "retorno espiritual"),
        related_concepts=(
            ConceptRelation("Tikún HaKlali", "related_concept"),
            ConceptRelation("arrepentimiento", "translation"),
        ),
    ),
    ConceptEntry(
        concept_id="habla",
        canonical_label="Habla",
        language="es",
        hebrew="דיבור",
        aliases=(
            "habla", "palabra", "decir", "voz",
            "speech", "speaking", "word",
            "דיבור", "דבור",
        ),
        transliterations=("dibur", "dibbur", "dibuk"),
        translations=(
            "speech", "speaking", "word",
            "habla", "palabra", "voz",
        ),
        related_concepts=(
            ConceptRelation("sangre", "thematic_parallel"),
            ConceptRelation("hitbodedut", "related_concept"),
            ConceptRelation("plegaria", "thematic_parallel"),
        ),
    ),
    ConceptEntry(
        concept_id="miedo",
        canonical_label="Miedo",
        language="es",
        hebrew="פחד",
        aliases=(
            "miedo", "temor", "temor reverencial",
            "fear", "awe", "dread",
            "פחד", "יראה", "יראת",
        ),
        transliterations=("pahad", "pakhad", "yirah", "yira"),
        translations=(
            "fear", "awe", "dread", "reverence",
            "miedo", "temor", "temor reverencial",
        ),
        related_concepts=(
            ConceptRelation("Yirat Shamayim", "related_concept"),
            ConceptRelation("Emuná", "thematic_parallel"),
            ConceptRelation("escorpion", "thematic_parallel"),
        ),
    ),
    ConceptEntry(
        concept_id="sangre",
        canonical_label="Sangre",
        language="es",
        hebrew="דם",
        aliases=(
            "sangre", "blood", "sanguínea",
            "דם", "דמים",
        ),
        transliterations=("dam", "dom", "damin"),
        translations=(
            "blood", "sangre",
        ),
        related_concepts=(
            ConceptRelation("habla", "thematic_parallel"),
            ConceptRelation("impurezas", "thematic_parallel"),
        ),
    ),
)


# ---------------------------------------------------------------------------
# Derived index: all searchable forms → concept_id
# ---------------------------------------------------------------------------

def _build_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for entry in CATALOG:
        for form in entry.all_searchable_forms():
            existing = idx.get(form)
            if existing and existing != entry.concept_id:
                # Allow multiple entries for the same form; keep first.
                continue
            idx[form] = entry.concept_id
    return idx


FORM_INDEX: dict[str, str] = _build_index()


def lookup_by_form(query: str) -> str | None:
    """Return the concept_id for any searchable form (exact match only)."""
    return FORM_INDEX.get(query)


def get_concept(concept_id: str) -> ConceptEntry | None:
    """Return the ConceptEntry by id."""
    for entry in CATALOG:
        if entry.concept_id == concept_id:
            return entry
    return None


__all__ = [
    "CATALOG",
    "FORM_INDEX",
    "ConceptEntry",
    "ConceptRelation",
    "lookup_by_form",
    "get_concept",
]
