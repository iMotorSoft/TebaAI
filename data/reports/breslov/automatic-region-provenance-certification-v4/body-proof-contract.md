# V4 body proof contract

Input: canonicalized page (boxes and text lines sorted by deterministic
geometry/source IDs), a centred caption anchor and a separator anchor.

1. `MAIN_BODY` evidence requires canonical source line IDs and geometry inside
   the body frame, ordered by script LTR.
2. Native visibility may strengthen evidence but is not required for the
   body `ORDER_PROOF`.
3. Quality `ACCEPTED` still requires visible native exact tokens; without it a
   structurally proven body is `CERTIFIED` + `UNRESOLVED`.
4. Narrow sidebar/quote columns (`width < 250`) and `section-header` boxes are
   not body paragraphs and are expected non-certifiable.
5. Retained non-body/non-note certificates and failed body proofs downgrade to
   `UNRESOLVED` + `LAYOUT_UNSUPPORTED`; ambiguous layout fails closed.
