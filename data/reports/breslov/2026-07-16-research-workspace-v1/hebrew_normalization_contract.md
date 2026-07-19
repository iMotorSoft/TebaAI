# Hebrew literal normalization contract

Canonical and search representations are separate.

`literal_text` preserves the NFC logical Unicode projection, niqqud, punctuation, letters, final letters, word order, line order, and references. Its page-96 SHA-256 is `3277b2423042696db70521faefb6999715324ca428efdd748c7aa33cf82a5049`.

`normalized_text` is derived only for retrieval by `normalize_hebrew_search`:

1. Unicode NFC;
2. remove bidi/invisible format controls;
3. remove niqqud, cantillation, and meteg;
4. normalize maqaf;
5. make punctuation, symbols, separators, and controls optional by mapping them to spaces;
6. case-fold mixed Latin content;
7. collapse whitespace.

It does not transliterate, translate, stem, reverse, delete Hebrew letters, change final letters, merge words, or replace canonical text.

Example:

```text
תְּהִלָּתִי אֶחְטָם לָךְ
→ תהלתי אחטם לך
```

NFC and NFD query variants produce the same derived search value. Evidence IDs derive from the persisted content node, not from the query variant.
