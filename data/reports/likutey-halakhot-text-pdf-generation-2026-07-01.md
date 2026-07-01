# Likutei Halakhot Text PDF Generation Report

This report documents the local generation of textual/searchable Likutei Halakhot study artifacts from Sefaria without database ingestion.

- Generated: 2026-07-01T23:25:04+00:00
- Source provider: `sefaria`
- Usage scope: `internal_study`
- PostgreSQL: untouched
- Milvus: untouched
- LiteLLM: untouched
- OCR: not used
- Embeddings: not generated

## Coverage

| status | section | pdf_file | json_file | markdown_file | html_file | refs | segments | hebrew_chars | versions | licenses | selectable_text | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| generated | אורח חיים / Orach Chaim | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/pdf/likutey_halakhot_orach_chayim_sefaria.pdf | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/sefaria_json/likutey_halakhot_orach_chayim_sefaria.json | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/markdown/likutey_halakhot_orach_chayim_sefaria.md | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/html/likutey_halakhot_orach_chayim_sefaria.html | 42 | 4430 | 6968427 | Likutei Halachot: Orach Chaim 1, Likutei Halachot: Orach Chaim 2, Likutey Halakhot, Breslov Research Institute. Jerusalem-New York, 2019 | CC-BY-NC, unknown | yes |  |
| generated | יורה דעה / Yoreh Deah | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/pdf/likutey_halakhot_yoreh_deah_sefaria.pdf | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/sefaria_json/likutey_halakhot_yoreh_deah_sefaria.json | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/markdown/likutey_halakhot_yoreh_deah_sefaria.md | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/html/likutey_halakhot_yoreh_deah_sefaria.html | 54 | 2614 | 4355381 | Likutei Halachot: Yoreh Deah 1, Likutei Halachot: Yoreh Deah 2 | unknown | yes |  |
| generated | אבן העזר / Even HaEzer | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/pdf/likutey_halakhot_even_haezer_sefaria.pdf | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/sefaria_json/likutey_halakhot_even_haezer_sefaria.json | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/markdown/likutey_halakhot_even_haezer_sefaria.md | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/html/likutey_halakhot_even_haezer_sefaria.html | 8 | 440 | 722880 | Likutei Halachot: Even HaEzer 1, Likutei Halachot: Even HaEzer 2 | unknown | yes |  |
| generated | חושן משפט / Choshen Mishpat | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/pdf/likutey_halakhot_choshen_mishpat_sefaria.pdf | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/sefaria_json/likutey_halakhot_choshen_mishpat_sefaria.json | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/markdown/likutey_halakhot_choshen_mishpat_sefaria.md | /media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/html/likutey_halakhot_choshen_mishpat_sefaria.html | 41 | 3081 | 4174608 | Likutei Halachot: Choshen Mishpat 1, Likutei Halachot: Choshen Mishpat 2 | unknown | yes |  |


## HebrewBooks visual backups

The local HebrewBooks PDFs remain image-only visual/page backups and were not used as text sources.

- `hebrewbooks_43317_likutey_halajot_orach_chayim.pdf`
- `hebrewbooks_67652_likutey_halajot_even_haezer.pdf`
- `hebrewbooks_67653_likutey_halajot_choshen_mishpat_a.pdf`
- `hebrewbooks_67654_likutey_halajot_choshen_mishpat_b.pdf`
- `hebrewbooks_67655_likutey_halajot_yoreh_deah.pdf`

## Recommendation

Use the generated Sefaria PDFs for internal study and text search, but preserve version/license metadata per section because Sefaria does not expose one clearly licensed Hebrew version for the whole work.

## Limitations

- Sefaria pagination does not align with HebrewBooks page images.
- Orach Chaim resolves to `CC-BY-NC`, while the other tested sections resolve to `unknown` licenses via Or Haganuz versions.
- These PDFs are suitable as local textual artifacts, not as a page-faithful edition map.

## Final outputs

- `/media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/pdf/likutey_halakhot_orach_chayim_sefaria.pdf`
- `/media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/pdf/likutey_halakhot_yoreh_deah_sefaria.pdf`
- `/media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/pdf/likutey_halakhot_even_haezer_sefaria.pdf`
- `/media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources/pdf/likutey_halakhot_choshen_mishpat_sefaria.pdf`
