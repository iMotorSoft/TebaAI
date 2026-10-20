# Direction proof / limits

Direction counts ALL Unicode strong bidi classes: L→LTR; R/AL→RTL; both→MIXED;
no strong codepoint→UNRESOLVED. Neither the first character, filename nor a
language label decides direction. Digits, punctuation, niqqud and replacement
characters do not establish a strong direction. Mixed regions are unresolved,
not reordered. Source span bidi/dir metadata was investigated:167 damaged
Hebrew spans report bidi0 and dir(1,0), so those fields cannot prove RTL.

The positive native quality proof is deliberately horizontal LTR-only. RTL can
have separate source ownership when script evidence survives; its logical
order is NOT proved by reversing glyphs or by the mere presence of Hebrew.

167's two damaged Hebrew boxes remain separately discovered but direction and
provenance certification UNRESOLVED. Calling them RTL because a human golden
says Hebrew would violate the required automatic proof. Their quality is
UNRESOLVED, not 'Hebrew = bad'. This is a decisive golden failure, not hidden
behind the page's PARTIAL aggregate.

Tests cover pure LTR/RTL, mixed with a misleading first character, neutral-only,
replacement-only and missing script evidence. Native direction/opacity/paint
loss also removes positive quality. No normalization or textual reversal.
