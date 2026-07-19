# Hebrew PDF grapheme reconstruction contract

1. Preserve the raw question and canonical corpus text.
2. Normalize query processing to NFC without replacing stored content.
3. Parse Hebrew base letters and combining marks in logical order.
4. Attach a separated niqqud or cantillation mark to the preceding Hebrew base letter.
5. Preserve known word boundaries in normally spaced text.
6. Treat dense glyph-by-glyph spacing as ambiguous rather than deleting all spaces.
7. Generate no more than 64 bounded segmentations.
8. Select word boundaries only after a literal corpus match.
9. Run the selected form through the shared niqqud-insensitive search normalizer.
10. Rank evidence with the existing indexed phrase search; vector search cannot substitute for a literal hit.

The reported raw phrase reconstructs to `תְּהִלָּתִי אֶחְטָם לָך`; the corpus-selected search form is `תהלתי אחטם לך`; the canonical evidence remains `תְּהִלָּתִי אֶחְטָם לָךְ`.
