# Responsive results

Chromium screenshots were captured through Playwright after animation settlement.

| Class | Evidence | Result |
| --- | --- | --- |
| Desktop 1536 × 1024 | `screenshots/desktop/desktop-1536x1024.png` | PASS |
| Tablet 820 × 1180 | `screenshots/tablet/tablet-820x1180.png` | PASS |
| Mobile 390 × 844 | `screenshots/mobile/mobile-390x844.png` | PASS |

The browser assertion verifies `body.scrollWidth === body.clientWidth` at each capture. The mobile menu opens and exposes the real login and access anchors. CSS breakpoints also cover 320px and the 2 + 2 + 1 capability fallback below 360px.
