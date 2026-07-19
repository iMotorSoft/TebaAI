# Manual Hebrew literal review checklist

Use the administrative credentials configured in the environment. Do not record them in this report.

- Login: http://127.0.0.1:3008/login
- Workspace: http://127.0.0.1:3008/research

## 1. Pointed phrase

Paste `תְּהִלָּתִי אֶחְטָם לָךְ`.

- [ ] The response says the phrase was found and does not discuss a “relación solicitada”.
- [ ] The source is Likutey Moharán I — edición española BRI.
- [ ] The source panel shows PDF page 96, printed page 76, and `LIKUTEY MOHARÁN #2:7`.
- [ ] The literal text reads naturally right-to-left and retains niqqud.

## 2. Unpointed phrase

Paste `תהלתי אחטם לך`.

- [ ] It resolves to the same evidence, document, page anchor, and pages.
- [ ] The canonical result still displays the pointed source text.

## 3. Partial phrase

Search `אחטם לך`.

- [ ] The same physical page is a principal result.
- [ ] The result is labeled as a literal normalized/no-niqqud match, not a translation.

## 4. Full Hebrew question

Search `איפה מופיע תהלתי אחטם לך`.

- [ ] The query is treated as `literal_lookup`.
- [ ] The question, quote, and source drawer are RTL while metadata remains LTR.

## 5. Mobile

Repeat on a phone or responsive mode.

- [ ] No horizontal overflow at 390 px or 320 px.
- [ ] The source panel/drawer opens, traps focus, closes with Escape, and returns focus.
- [ ] The physical page, printed page, section, and Hebrew quote remain visible.

## Negative control

Search `תהלתי אחטמ לך`.

- [ ] It returns no literal evidence and does not invent a page, translation, or physical source.
