# Consumer boundary before

`SrvRestAstroLS_v1/backend/modules/library/extractors.py` exposed the opt-in
`extract_pdf_with_region_certificates(pdf_path, pages=...)` capability but
imported it from the V1 module inside the function:

```python
from modules.library.automatic_region_certification import (
    extract_pdf_region_certificates,
)
return [page.to_dict() for page in extract_pdf_region_certificates(...)]
```

Consequences:

- Callers asking the current extractor for region certificates still received
  V1 certificates.
- V1 certifies extractor classes without independent zone, boundary or
  ownership proof; it is the source of the five known unsafe certifications.
- There was no explicit consumer contract pinning a certificate version and no
  regression preventing a later V1 fallback.
- The worker did not call this helper, so the mismatch was latent rather than
  an active worker regression.
