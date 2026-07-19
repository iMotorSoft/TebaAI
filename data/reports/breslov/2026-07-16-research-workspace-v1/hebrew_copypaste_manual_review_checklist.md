# Manual Hebrew copy/paste review

Use the administrative credentials configured in the environment. Do not record them in this report.

- Login: http://127.0.0.1:3008/login
- Workspace: http://127.0.0.1:3008/research

## Exact reported case

Paste exactly:

`ת ְּ הִ לָּ ת ִ י אֶ חְ ט ָ ם לָ ך donde esta`

Confirm that the result is not `no_evidence`, is not described as a requested relation, preserves the original question, and shows the canonical Hebrew quotation. Open its source and confirm physical PDF page 96, printed page 76, section `LIKUTEY MOHARÁN #2:7`, and readable RTL text.

## Equivalence

Start a new research turn for each of these:

- `תְּהִלָּתִי אֶחְטָם לָךְ`
- `תהלתי אחטם לך`
- `אחטם לך`

Confirm that all select the same physical document, page anchor, and evidence.

## Responsive and negative checks

At desktop, tablet, 390 px, and 320 px, confirm no horizontal overflow and that the source panel/drawer preserves RTL quotation and LTR metadata. Then query `תהלתי אחטמ לך` and confirm that no literal evidence is invented.
