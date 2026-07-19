# Hebrew literal instruction extraction

The literal is selected by Hebrew Unicode script boundaries, not by a hard-coded quotation. Text outside the first and last Hebrew code points is retained as an instruction and excluded from retrieval. A small edge vocabulary classifies localization wording in Spanish, English, and Hebrew; it does not define, translate, or rewrite the literal.

For the reported input:

- `literal_raw`: `ת ְּ הִ לָּ ת ִ י אֶ חְ ט ָ ם לָ ך`
- `instruction`: `donde esta`
- `instruction_language`: `es`
- `intent`: `literal_lookup`
- query sent to normal phrase retrieval: `תהלתי אחטם לך`

Instructions are supported before or after the literal. The frontend continues sending and rendering the exact user input.
