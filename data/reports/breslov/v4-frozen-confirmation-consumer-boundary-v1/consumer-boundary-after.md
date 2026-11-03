# Consumer boundary after

`extract_pdf_with_region_certificates(...)` now imports V4 explicitly:

```python
from modules.library.automatic_region_certification_v4 import (
    extract_pdf_region_certificates,
)
return [page.to_dict() for page in extract_pdf_region_certificates(...)]
```

The public return shape is unchanged: one page-local dictionary per requested
physical page, each carrying region certificates and page-local Markdown
ranges. Consumers receive V4 certificates with
`certificate_version = automatic-region-certification-v4`.

Contract properties covered by `tests/test_consumer_region_certificates_v4.py`:

- V1 is never called by the consumer boundary.
- V4 failure is fail-closed: there is no V1 fallback.
- Consumer output is byte-identical to direct V4 `page.to_dict()` output.
- Returned certificates are explicitly V4.
- A cross-page continuation remains linked through the consumer.
- Unresolved regions are returned, not filtered.
- One-based unique page validation remains intact.
- The worker does not call the opt-in helper.

No dynamic version selection, environment switch, V1 fallback or worker
integration was added.
