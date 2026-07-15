"""Open, conservative literal catalog for Likutey Halajot nominal references.

This is a detection aid, not an authority file: only a matched ``surface_form``
which is present in the stored literal may be persisted.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class NominalReferencePattern:
    canonical_name: str
    reference_kind: str
    variants: tuple[str, ...]


CATALOG: tuple[NominalReferencePattern, ...] = (
    NominalReferencePattern("Zohar", "zohar", ("Zohar", "Zóhar", "זוהר")),
    NominalReferencePattern("Midrash", "midrash", ("Midrash", "מדרש")),
    NominalReferencePattern("Talmud", "talmudic_tractate", ("Talmud", "תלמוד")),
    NominalReferencePattern("Shulján Aruj", "halakhic_code", ("Shulján Aruj", "Shulchan Aruch", "שולחן ערוך")),
    NominalReferencePattern("Likutey Moharan", "breslov_work", ("Likutey Moharán", "Likutey Moharan", "Likutei Moharan", "ליקוטי מוהר\"ן", "LM I", "LM II")),
    NominalReferencePattern("Sichot HaRan", "breslov_work", ("Sichot HaRan", "Sijot HaRan", "שיחות הר\"ן")),
    NominalReferencePattern("Rebe Najmán", "breslov_figure", ("Rebe Najmán", "Rebbe Nachman", "Rabí Najmán", "Rabbi Nachman", "רבי נחמן")),
    NominalReferencePattern("Reb Noson", "breslov_figure", ("Reb Noson", "Rabí Natán", "Rabbi Natan", "רבי נתן")),
    NominalReferencePattern("Rashi", "rabbinic_commentator", ("Rashi", "רש\"י")),
    NominalReferencePattern("Rashbam", "rabbinic_commentator", ("Rashbam", "רשב\"ם")),
    NominalReferencePattern("Rambam", "rabbinic_commentator", ("Rambam", "רמב\"ם")),
    NominalReferencePattern("Ramban", "rabbinic_commentator", ("Ramban", "רמב\"ן")),
    NominalReferencePattern("Maharal", "rabbinic_commentator", ("Maharal", "מהר\"ל")),
    NominalReferencePattern("Mei HaNajal", "rabbinic_work", ("Mei HaNajal",)),
    NominalReferencePattern("Biur HaLikutim", "rabbinic_work", ("Biur HaLikutim",)),
    NominalReferencePattern("Parparaot LeJojmá", "rabbinic_work", ("Parparaot LeJojmá", "Parparaot LeJojma")),
)


def catalog_matches(text: str) -> list[tuple[re.Match[str], NominalReferencePattern, bool]]:
    """Return literal matches and whether the spelling is the canonical variant."""
    matches: list[tuple[re.Match[str], NominalReferencePattern, bool]] = []
    for entry in CATALOG:
        for variant in entry.variants:
            # Word boundaries avoid partial Latin matches; Hebrew variants are exact.
            expression = re.escape(variant)
            if any("A" <= char <= "z" for char in variant):
                expression = rf"(?<!\w){expression}(?!\w)"
            for match in re.finditer(expression, text, flags=re.IGNORECASE):
                matches.append((match, entry, match.group(0) == entry.canonical_name))
    return matches
