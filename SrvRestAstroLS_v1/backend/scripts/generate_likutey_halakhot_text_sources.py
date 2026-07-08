#! /usr/bin/env python3
"""
Generate local text/searchable Likutei Halakhot artifacts from Sefaria.

This workflow is read-only against upstream sources and writes only:
- local study artifacts under Download/Tora/Breslov/LikuteyHalajot/TextSources
- technical evidence under data/reports

It does not touch PostgreSQL, Milvus, LiteLLM or project runtime code paths.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


# @lat: [[likutey-halakhot-local-text-sources#Artifact Generation]]

SEFARIA_INDEX = "Likutei_Halakhot"
SEFARIA_WORK = "Likutei Halakhot"
SEFARIA_HE_TITLE = "ליקוטי הלכות"
USAGE_SCOPE = "internal_study"
DEFAULT_OUTPUT_ROOT = Path(
    "/media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources"
)
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORT_ROOT = REPO_ROOT / "data" / "reports"
HTTP_HEADERS = {
    "User-Agent": "TebaAI-LikuteyHalakhot-ArtifactGenerator/1.0",
    "Accept": "application/json",
}
HEBREW_RE = re.compile(r"[\u0590-\u05FF]")
NIQQUD_RE = re.compile(r"[\u0591-\u05C7]")
TAG_RE = re.compile(r"<[^>]+>")
PDF_NAME_MAP = {
    "Orach Chaim": "likutey_halakhot_orach_chayim_sefaria.pdf",
    "Yoreh Deah": "likutey_halakhot_yoreh_deah_sefaria.pdf",
    "Even HaEzer": "likutey_halakhot_even_haezer_sefaria.pdf",
    "Choshen Mishpat": "likutey_halakhot_choshen_mishpat_sefaria.pdf",
}
SLUG_MAP = {
    "Orach Chaim": "orach_chayim",
    "Yoreh Deah": "yoreh_deah",
    "Even HaEzer": "even_haezer",
    "Choshen Mishpat": "choshen_mishpat",
}
SECTIONS = [
    ("Orach Chaim", "אורח חיים"),
    ("Yoreh Deah", "יורה דעה"),
    ("Even HaEzer", "אבן העזר"),
    ("Choshen Mishpat", "חושן משפט"),
]
ORIGINAL_GETADDRINFO = socket.getaddrinfo


@dataclass
class LeafMetrics:
    segments: int
    total_chars: int
    hebrew_chars: int
    empty_segments: int
    has_html: bool
    has_niqqud: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Artifact root for JSON/Markdown/HTML/PDF/manifests.",
    )
    parser.add_argument(
        "--report-root",
        type=Path,
        default=DEFAULT_REPORT_ROOT,
        help="Repository report directory for technical evidence.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.15,
        help="Pause between Sefaria leaf requests.",
    )
    return parser.parse_args()


def prefer_ipv4() -> None:
    def _ipv4_first(
        host: str,
        port: int,
        family: int = 0,
        type: int = 0,
        proto: int = 0,
        flags: int = 0,
    ) -> list[tuple[Any, ...]]:
        infos = ORIGINAL_GETADDRINFO(host, port, family, type, proto, flags)
        return sorted(infos, key=lambda item: 0 if item[0] == socket.AF_INET else 1)

    socket.getaddrinfo = _ipv4_first


def ensure_dirs(root: Path, report_root: Path) -> dict[str, Path]:
    dirs = {
        "root": root,
        "json": root / "sefaria_json",
        "markdown": root / "markdown",
        "html": root / "html",
        "pdf": root / "pdf",
        "manifests": root / "manifests",
        "reports": root / "reports",
        "repo_reports": report_root,
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def fetch_json(url: str, retries: int = 3) -> Any:
    request = urllib.request.Request(url, headers=HTTP_HEADERS)
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.load(response)
        except Exception as exc:  # pragma: no cover - network errors are external
            last_error = exc
            if attempt == retries:
                raise
            time.sleep(1.0 * attempt)
    raise RuntimeError(f"unreachable fetch_json error: {last_error}")


def node_titles(node: dict[str, Any]) -> dict[str, str]:
    titles = {}
    for entry in node.get("titles", []):
        lang = entry.get("lang")
        text = entry.get("text")
        if lang and text:
            titles[lang] = text
    if node.get("title"):
        titles.setdefault("en", node["title"])
    if node.get("heTitle"):
        titles.setdefault("he", node["heTitle"])
    return titles


def get_index_metadata() -> dict[str, Any]:
    return fetch_json(f"https://www.sefaria.org/api/v2/raw/index/{SEFARIA_INDEX}")


def get_versions_metadata() -> list[dict[str, Any]]:
    data = fetch_json(f"https://www.sefaria.org/api/texts/versions/{SEFARIA_INDEX}")
    if isinstance(data, list):
        return data
    return []


def get_text_response(ref: str) -> dict[str, Any]:
    url = (
        "https://www.sefaria.org/api/v3/texts/"
        + urllib.parse.quote(ref, safe="")
        + "?language=hebrew"
    )
    data = fetch_json(url)
    if not isinstance(data, dict):
        raise TypeError(f"Unexpected response for {ref!r}: {type(data).__name__}")
    return data


def iter_segments(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        parts: list[str] = []
        for child in node:
            parts.extend(iter_segments(child))
        return parts
    return []


def strip_tags(text: str) -> str:
    return TAG_RE.sub("", text)


def compute_leaf_metrics(text_node: Any) -> LeafMetrics:
    segments = iter_segments(text_node)
    total_chars = sum(len(seg) for seg in segments)
    hebrew_chars = sum(len(HEBREW_RE.findall(seg)) for seg in segments)
    empty_segments = sum(1 for seg in segments if not strip_tags(seg).strip())
    has_html = any(bool(TAG_RE.search(seg)) for seg in segments)
    has_niqqud = any(bool(NIQQUD_RE.search(seg)) for seg in segments)
    return LeafMetrics(
        segments=len(segments),
        total_chars=total_chars,
        hebrew_chars=hebrew_chars,
        empty_segments=empty_segments,
        has_html=has_html,
        has_niqqud=has_niqqud,
    )


def section_leaf_refs(index_data: dict[str, Any]) -> list[dict[str, Any]]:
    schema_nodes = index_data["schema"]["nodes"]
    results: list[dict[str, Any]] = []
    for top_en, top_he in SECTIONS:
        top_node = next(
            node
            for node in schema_nodes
            if node_titles(node).get("en") == top_en
        )
        for leaf in top_node.get("nodes", []):
            titles = node_titles(leaf)
            leaf_en = titles["en"]
            leaf_he = titles["he"]
            results.append(
                {
                    "top_en": top_en,
                    "top_he": top_he,
                    "leaf_en": leaf_en,
                    "leaf_he": leaf_he,
                    "ref": f"{SEFARIA_WORK}, {top_en}, {leaf_en}",
                    "leaf_node": leaf,
                }
            )
    return results


def render_markdown(section_title_he: str, section_title_en: str, section_data: dict[str, Any]) -> str:
    summary = section_data["summary"]
    lines = [
        f"# {SEFARIA_HE_TITLE} — {section_title_he}",
        "",
        f"מקור: Sefaria — `{SEFARIA_WORK}`",
        f"Section: `{section_title_en}`",
        f"שימוש: `{USAGE_SCOPE}`",
        f"תאריך יצירה: {section_data['generated_at']}",
        f"Refs hojas: {summary['refs']}",
        f"Segmentos: {summary['segments']}",
        f"Caracteres hebreos: {summary['hebrew_chars']}",
        f"Versiones detectadas: {', '.join(summary['versions']) or 'n/a'}",
        f"Licencias detectadas: {', '.join(summary['licenses']) or 'n/a'}",
        "",
        "## Metadata",
        "",
        f"- Título canónico: {SEFARIA_HE_TITLE} / {SEFARIA_WORK}",
        "- Autor canónico: Nathan Sternhartz",
        f"- Scope: `{USAGE_SCOPE}`",
        "- Commercial use: `false`",
        "- Public corpus publication: `false`",
        "",
    ]

    for leaf in section_data["refs"]:
        lines.extend(
            [
                f"## {leaf['leaf_he']}",
                "",
                f"Sefaria ref: `{leaf['ref']}`",
                "",
                f"הפניה: `{leaf['heRef']}`",
                "",
                f"Version: `{leaf['versionTitle'] or 'unknown'}`",
                "",
                f"License: `{leaf['license'] or 'unknown'}`",
                "",
            ]
        )
        for chapter_idx, chapter in enumerate(leaf["text"], start=1):
            lines.extend([f"### הלכה {chapter_idx}", ""])
            if not isinstance(chapter, list):
                lines.extend([str(chapter), ""])
                continue
            for section_idx, section in enumerate(chapter, start=1):
                lines.extend(
                    [
                        f"#### סעיף {section_idx}",
                        "",
                        f"`{leaf['ref']} {chapter_idx}:{section_idx}`",
                        "",
                    ]
                )
                if not isinstance(section, list):
                    lines.extend([str(section), ""])
                    continue
                for paragraph in section:
                    if strip_tags(str(paragraph)).strip():
                        lines.extend([str(paragraph), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_html(section_title_he: str, section_title_en: str, section_data: dict[str, Any]) -> str:
    summary = section_data["summary"]
    versions = "".join(
        f"<li><code>{html.escape(version)}</code></li>"
        for version in summary["versions"]
    ) or "<li><code>unknown</code></li>"
    licenses = "".join(
        f"<li><code>{html.escape(license)}</code></li>"
        for license in summary["licenses"]
    ) or "<li><code>unknown</code></li>"
    body_parts = [
        "<!doctype html>",
        '<html lang="he" dir="rtl">',
        "<head>",
        '<meta charset="utf-8" />',
        f"<title>{html.escape(SEFARIA_HE_TITLE)} — {html.escape(section_title_he)}</title>",
        "<style>",
        "@page { size: A4; margin: 16mm; }",
        "body { direction: rtl; unicode-bidi: plaintext; font-family: 'Noto Sans Hebrew', 'DejaVu Sans', sans-serif; line-height: 1.7; font-size: 16px; color: #111; background: #fff; }",
        "main { max-width: 900px; margin: 0 auto; }",
        "h1, h2, h3, h4 { direction: rtl; page-break-after: avoid; }",
        "h1 { border-bottom: 2px solid #222; padding-bottom: 0.4rem; }",
        "h2 { margin-top: 2rem; border-top: 1px solid #bbb; padding-top: 1rem; }",
        "h3 { margin-top: 1.5rem; }",
        "h4 { margin-top: 1rem; }",
        "p { margin: 0.5rem 0; }",
        ".meta { border: 1px solid #bbb; padding: 1rem; background: #f8f8f8; margin-bottom: 1.5rem; }",
        ".meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }",
        ".source-note { direction: ltr; text-align: left; font-size: 12px; color: #444; word-break: break-word; }",
        ".section-note { font-size: 13px; color: #333; }",
        "ul { margin: 0.25rem 0 0.75rem; }",
        "</style>",
        "</head>",
        "<body>",
        "<main>",
        f"<h1>{html.escape(SEFARIA_HE_TITLE)} — {html.escape(section_title_he)}</h1>",
        '<section class="meta">',
        "<p><strong>Source:</strong> Sefaria</p>",
        f"<p><strong>Work:</strong> <code>{html.escape(SEFARIA_WORK)}</code></p>",
        f"<p><strong>Section:</strong> <code>{html.escape(section_title_en)}</code></p>",
        f"<p><strong>Usage:</strong> <code>{html.escape(USAGE_SCOPE)}</code> · internal · study · non-commercial</p>",
        f"<p><strong>Generated:</strong> {html.escape(section_data['generated_at'])}</p>",
        '<div class="meta-grid">',
        "<div>",
        f"<p><strong>Refs hojas:</strong> {summary['refs']}</p>",
        f"<p><strong>Segmentos:</strong> {summary['segments']}</p>",
        f"<p><strong>Caracteres hebreos:</strong> {summary['hebrew_chars']}</p>",
        f"<p><strong>Refs vacías:</strong> {summary['empty_refs']}</p>",
        "</div>",
        "<div>",
        "<p><strong>Versiones detectadas:</strong></p>",
        f"<ul>{versions}</ul>",
        "<p><strong>Licencias detectadas:</strong></p>",
        f"<ul>{licenses}</ul>",
        "</div>",
        "</div>",
        "</section>",
    ]

    for leaf in section_data["refs"]:
        body_parts.extend(
            [
                f"<h2>{html.escape(leaf['leaf_he'])}</h2>",
                f'<p class="source-note">Sefaria ref: {html.escape(leaf["ref"])}</p>',
                f'<p class="section-note">הפניה: <code>{html.escape(leaf["heRef"])}</code></p>',
                f'<p class="section-note">Version: <code>{html.escape(leaf["versionTitle"] or "unknown")}</code></p>',
                f'<p class="section-note">License: <code>{html.escape(leaf["license"] or "unknown")}</code></p>',
            ]
        )
        for chapter_idx, chapter in enumerate(leaf["text"], start=1):
            body_parts.append(f"<h3>הלכה {chapter_idx}</h3>")
            if not isinstance(chapter, list):
                body_parts.append(f"<p>{chapter}</p>")
                continue
            for section_idx, section in enumerate(chapter, start=1):
                body_parts.extend(
                    [
                        f"<h4>סעיף {section_idx}</h4>",
                        f'<p class="source-note">{html.escape(leaf["ref"])} {chapter_idx}:{section_idx}</p>',
                    ]
                )
                if not isinstance(section, list):
                    body_parts.append(f"<p>{section}</p>")
                    continue
                for paragraph in section:
                    paragraph_text = str(paragraph)
                    if strip_tags(paragraph_text).strip():
                        body_parts.append(f"<p>{paragraph_text}</p>")

    body_parts.extend(["</main>", "</body>", "</html>"])
    return "\n".join(body_parts)


def parse_pdf_pages(pdfinfo_stdout: str) -> int:
    match = re.search(r"^Pages:\s+(\d+)$", pdfinfo_stdout, flags=re.MULTILINE)
    return int(match.group(1)) if match else 0


def run_pdfinfo(pdf_path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "pages": parse_pdf_pages(proc.stdout),
        "raw": proc.stdout,
    }


def extract_pdf_text(pdf_path: Path) -> str:
    proc = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    commands = [
        [
            "google-chrome",
            "--headless=new",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ],
        [
            "google-chrome",
            "--headless",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ],
    ]
    last_error: Exception | None = None
    for command in commands:
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=900,
            )
            return
        except Exception as exc:  # pragma: no cover - depends on Chrome runtime
            last_error = exc
    raise RuntimeError(f"Unable to render PDF for {html_path.name}: {last_error}")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, content: Any) -> None:
    path.write_text(
        json.dumps(content, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def markdown_table(rows: list[dict[str, Any]]) -> str:
    headers = [
        "status",
        "section",
        "pdf_file",
        "json_file",
        "markdown_file",
        "html_file",
        "refs",
        "segments",
        "hebrew_chars",
        "versions",
        "licenses",
        "selectable_text",
        "notes",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        line = []
        for header in headers:
            value = row.get(header, "")
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            value = str(value).replace("\n", " ").replace("|", "\\|")
            line.append(value)
        lines.append("| " + " | ".join(line) + " |")
    return "\n".join(lines) + "\n"


def collect_hebrewbooks_backups(output_root: Path) -> list[str]:
    parent = output_root.parent
    pdfs = sorted(
        path.name for path in parent.glob("*.pdf") if path.is_file()
    )
    return pdfs


def section_summary(refs: list[dict[str, Any]]) -> dict[str, Any]:
    versions = sorted({ref["versionTitle"] or "unknown" for ref in refs})
    licenses = sorted({ref["license"] or "unknown" for ref in refs})
    return {
        "refs": len(refs),
        "segments": sum(ref["metrics"]["segments"] for ref in refs),
        "total_chars": sum(ref["metrics"]["total_chars"] for ref in refs),
        "hebrew_chars": sum(ref["metrics"]["hebrew_chars"] for ref in refs),
        "empty_segments": sum(ref["metrics"]["empty_segments"] for ref in refs),
        "refs_with_html": sum(1 for ref in refs if ref["metrics"]["has_html"]),
        "refs_with_niqqud": sum(1 for ref in refs if ref["metrics"]["has_niqqud"]),
        "empty_refs": sum(1 for ref in refs if ref["metrics"]["segments"] == 0),
        "versions": versions,
        "licenses": licenses,
    }


def build_section_payload(
    generated_at: str,
    top_en: str,
    top_he: str,
    leaf_entries: list[dict[str, Any]],
    index_data: dict[str, Any],
    versions_data: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = section_summary(leaf_entries)
    return {
        "generated_at": generated_at,
        "source_provider": "sefaria",
        "source_work": SEFARIA_WORK,
        "source_index": SEFARIA_INDEX,
        "canonical_title_he": SEFARIA_HE_TITLE,
        "canonical_title_en": SEFARIA_WORK,
        "author_canonical": "Nathan Sternhartz",
        "usage_scope": USAGE_SCOPE,
        "commercial_use": False,
        "public_corpus_publication": False,
        "section_en": top_en,
        "section_he": top_he,
        "index_metadata": {
            "title": index_data.get("title"),
            "categories": index_data.get("categories"),
            "schema_titles": index_data.get("schema", {}).get("titles", []),
        },
        "versions_catalog": versions_data,
        "summary": summary,
        "refs": leaf_entries,
    }


def build_leaf_record(leaf_ref: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    version = response.get("versions", [{}])[0] if response.get("versions") else {}
    text = version.get("text") or []
    metrics = compute_leaf_metrics(text)
    return {
        "top_en": leaf_ref["top_en"],
        "top_he": leaf_ref["top_he"],
        "leaf_en": leaf_ref["leaf_en"],
        "leaf_he": leaf_ref["leaf_he"],
        "ref": response.get("ref", leaf_ref["ref"]),
        "heRef": response.get("heRef"),
        "sectionNames": response.get("sectionNames"),
        "addressTypes": response.get("addressTypes"),
        "versionTitle": version.get("versionTitle"),
        "versionSource": version.get("versionSource"),
        "license": version.get("license"),
        "warnings": response.get("warnings", []),
        "metrics": asdict(metrics),
        "text": text,
        "available_versions": response.get("available_versions", []),
    }


def write_report(
    path: Path,
    manifest_rows: list[dict[str, Any]],
    backup_pdfs: list[str],
    generation_time: str,
) -> None:
    useful = [row for row in manifest_rows if row["status"] in {"generated", "partial"}]
    lines = [
        "# Likutei Halakhot Text PDF Generation Report",
        "",
        "This report documents the local generation of textual/searchable Likutei Halakhot study artifacts from Sefaria without database ingestion.",
        "",
        f"- Generated: {generation_time}",
        f"- Source provider: `sefaria`",
        f"- Usage scope: `{USAGE_SCOPE}`",
        "- PostgreSQL: untouched",
        "- Milvus: untouched",
        "- LiteLLM: untouched",
        "- OCR: not used",
        "- Embeddings: not generated",
        "",
        "## Coverage",
        "",
        markdown_table(manifest_rows),
        "",
        "## HebrewBooks visual backups",
        "",
        "The local HebrewBooks PDFs remain image-only visual/page backups and were not used as text sources.",
        "",
    ]
    if backup_pdfs:
        lines.extend([f"- `{name}`" for name in backup_pdfs])
    else:
        lines.append("- No parent-level backup PDFs were detected.")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Use the generated Sefaria PDFs for internal study and text search, but preserve version/license metadata per section because Sefaria does not expose one clearly licensed Hebrew version for the whole work.",
            "",
            "## Limitations",
            "",
            "- Sefaria pagination does not align with HebrewBooks page images.",
            "- Orach Chaim resolves to `CC-BY-NC`, while the other tested sections resolve to `unknown` licenses via Or Haganuz versions.",
            "- These PDFs are suitable as local textual artifacts, not as a page-faithful edition map.",
            "",
            "## Final outputs",
            "",
        ]
    )
    for row in useful:
        lines.append(f"- `{row['pdf_file']}`")
    write_text(path, "\n".join(lines).rstrip() + "\n")


def main() -> int:
    args = parse_args()
    prefer_ipv4()
    dirs = ensure_dirs(args.output_root, args.report_root)
    generation_time = datetime.now(UTC).replace(microsecond=0).isoformat()

    index_data = get_index_metadata()
    versions_data = get_versions_metadata()
    leaf_refs = section_leaf_refs(index_data)
    grouped: dict[str, list[dict[str, Any]]] = {top_en: [] for top_en, _ in SECTIONS}
    errors: dict[str, list[str]] = {top_en: [] for top_en, _ in SECTIONS}

    for leaf_ref in leaf_refs:
        try:
            print(f"[fetch] {leaf_ref['top_en']} :: {leaf_ref['leaf_en']}", file=sys.stderr, flush=True)
            response = get_text_response(leaf_ref["ref"])
            grouped[leaf_ref["top_en"]].append(build_leaf_record(leaf_ref, response))
        except Exception as exc:  # pragma: no cover - external network data
            errors[leaf_ref["top_en"]].append(f"{leaf_ref['ref']}: {exc}")
            print(f"[error] {leaf_ref['ref']}: {exc}", file=sys.stderr, flush=True)
        time.sleep(args.sleep_seconds)

    manifest_rows: list[dict[str, Any]] = []

    for top_en, top_he in SECTIONS:
        refs = grouped[top_en]
        slug = SLUG_MAP[top_en]
        json_path = dirs["json"] / f"likutey_halakhot_{slug}_sefaria.json"
        markdown_path = dirs["markdown"] / f"likutey_halakhot_{slug}_sefaria.md"
        html_path = dirs["html"] / f"likutey_halakhot_{slug}_sefaria.html"
        pdf_path = dirs["pdf"] / PDF_NAME_MAP[top_en]

        section_payload = build_section_payload(
            generation_time,
            top_en,
            top_he,
            refs,
            index_data,
            versions_data,
        )
        write_json(json_path, section_payload)

        markdown_content = render_markdown(top_he, top_en, section_payload)
        html_content = render_html(top_he, top_en, section_payload)
        write_text(markdown_path, markdown_content)
        write_text(html_path, html_content)

        notes: list[str] = []
        status = "generated"
        selectable_text = "no"
        page_count = 0
        size_mb = 0.0
        if errors[top_en]:
            status = "partial"
            notes.extend(errors[top_en])
        if not refs:
            status = "failed"
            notes.append("No refs downloaded for section.")
        else:
            try:
                print(f"[pdf] {top_en}", file=sys.stderr, flush=True)
                render_pdf(html_path, pdf_path)
                pdf_info = run_pdfinfo(pdf_path)
                pdf_text = extract_pdf_text(pdf_path)
                page_count = pdf_info["pages"]
                size_mb = round(pdf_path.stat().st_size / (1024 * 1024), 2)
                if HEBREW_RE.search(pdf_text):
                    selectable_text = "yes"
                else:
                    status = "needs_review"
                    notes.append("pdftotext did not extract Hebrew characters from the PDF.")
            except Exception as exc:  # pragma: no cover - depends on Chrome/pdf tools
                status = "failed"
                notes.append(str(exc))
                print(f"[pdf-error] {top_en}: {exc}", file=sys.stderr, flush=True)

        summary = section_payload["summary"]
        manifest_rows.append(
            {
                "status": status,
                "section": f"{top_he} / {top_en}",
                "pdf_file": str(pdf_path),
                "json_file": str(json_path),
                "markdown_file": str(markdown_path),
                "html_file": str(html_path),
                "refs": summary["refs"],
                "segments": summary["segments"],
                "hebrew_chars": summary["hebrew_chars"],
                "versions": summary["versions"],
                "licenses": summary["licenses"],
                "selectable_text": selectable_text,
                "pages": page_count,
                "size_mb": size_mb,
                "notes": " | ".join(notes) if notes else "",
            }
        )

    manifest_json_path = dirs["manifests"] / "likutey_halakhot_text_pdf_manifest.json"
    manifest_md_path = dirs["manifests"] / "likutey_halakhot_text_pdf_manifest.md"
    report_json_path = dirs["reports"] / "likutey_halakhot_text_pdf_report.json"
    report_md_path = dirs["reports"] / "likutey_halakhot_text_pdf_report.md"
    repo_report_md_path = dirs["repo_reports"] / "likutey-halakhot-text-pdf-generation-2026-07-01.md"

    write_json(
        manifest_json_path,
        {
            "generated_at": generation_time,
            "source_provider": "sefaria",
            "usage_scope": USAGE_SCOPE,
            "rows": manifest_rows,
        },
    )
    write_text(manifest_md_path, markdown_table(manifest_rows))
    write_json(
        report_json_path,
        {
            "generated_at": generation_time,
            "backup_pdfs": collect_hebrewbooks_backups(args.output_root),
            "manifest_rows": manifest_rows,
        },
    )
    write_report(
        report_md_path,
        manifest_rows,
        collect_hebrewbooks_backups(args.output_root),
        generation_time,
    )
    write_report(
        repo_report_md_path,
        manifest_rows,
        collect_hebrewbooks_backups(args.output_root),
        generation_time,
    )

    failed = [row for row in manifest_rows if row["status"] in {"failed", "needs_review"}]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
