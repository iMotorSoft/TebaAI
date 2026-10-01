"""Reproduce original PDFs through DEV upload/job/targeted worker APIs.

Requires local services and environment-provided E2E credentials. Never
publishes or uses the primary scope. Reuses this report's job manifests.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx

OUTPUT = Path(__file__).resolve().parent
BACKEND = OUTPUT.parents[3] / "SrvRestAstroLS_v1" / "backend"
BASE = "http://127.0.0.1:7008"
SCOPE = {"knowledge_scope_code": "breslov_e2e"}


def save(name, data):
    (OUTPUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2))


with httpx.Client(timeout=180) as client:
    def login():
        response = client.post(BASE + "/auth/login", json={
            "email": os.environ["TEBAAI_E2E_ADMIN_EMAIL"],
            "password": os.environ["TEBAAI_E2E_ADMIN_PASSWORD"],
        })
        response.raise_for_status()
        client.headers["Authorization"] = "Bearer " + response.json()["access_token"]

    def request(method, path, **kwargs):
        response = client.request(method, BASE + path, **kwargs)
        if response.status_code == 401:
            login()
            response = client.request(method, BASE + path, **kwargs)
        response.raise_for_status()
        return response.json()

    login()
    sys.path.insert(0, str(BACKEND))
    from modules.embeddings.client import embed_text
    start = time.monotonic()
    vector = embed_text("DEV Hebrew fidelity: יְהִי רָצוֹן 6 = ו ; 1 = א")
    assert len(vector) == 1536
    save("embeddings-preflight-before-reingest.json", {"status": "PASS", "dimension": len(vector), "seconds": round(time.monotonic() - start, 2), "fallback": False})
    for case, name, title in [
        ("a", "UN DÍA EN LA VIDA (KDP).pdf", "Un Día en la Vida de un Jasid de Breslov"),
        ("b", "LA POTENCIA DE LA PLEGARIA Interior Print.pdf", "La Potencia de la Plegaria"),
    ]:
        source = Path("/media/issajar/DEVELOP/Download/Tora/Breslov") / name
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        fixture = json.loads((BACKEND / "tests/fixtures/hebrew_pdf_fidelity" / f"case_{case}.json").read_text())
        assert sha == fixture["source_sha256"], "Source changed; do not use a substitute"
        manifest = OUTPUT / f"{case}-job-created.json"
        if manifest.exists():
            job = json.loads(manifest.read_text())
            job = request("GET", "/admin/content/jobs/" + job["job_id"], params=SCOPE)
            if job["status"] == "failed":
                save(f"{case}-attempt-{job['attempt_number']}-failed.json", job)
                assert job["cleanup_status"] in {"completed", "not_required"}, "Wait for verified manifest compensation"
                job = request("POST", "/admin/content/jobs/" + job["job_id"] + "/retry", params=SCOPE)
                save(f"{case}-job-created.json", job)
        else:
            upload = request("POST", "/admin/content/uploads", params=SCOPE,
                             files={"file": (name, source.read_bytes(), "application/pdf")})
            save(f"{case}-upload.json", upload)
            job = request("POST", "/admin/content/jobs", json={
                **SCOPE, "upload_id": upload["upload_id"], "title": title, "language": "auto",
                "administrative_notes": "DEV fidelity: original PDF, isolated scope; no promotion",
            })
            save(f"{case}-job-created.json", job)
        print(case, job["job_id"], job["status"], flush=True)
        if job["status"] == "queued":
            environment = dict(os.environ, TEBAAI_ENV="development", TEBAAI_POSTGRES_AUTO_MIGRATE="false",
                TEBAAI_CONTENT_MANAGER_E2E_ENABLED="true", TEBAAI_CONTENT_MANAGER_E2E_FIXTURE_SHA256=sha,
                TEBAAI_CONTENT_MANAGER_WORKER_SCOPE="breslov_e2e", TEBAAI_CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED="false")
            with (OUTPUT / f"{case}-worker-attempt-{job['attempt_number']}.log").open("w") as log:
                subprocess.run([str(BACKEND / ".venv/bin/python"), "-u", "scripts/content_manager_worker.py",
                    "--once", "--job-id", job["job_id"]], cwd=BACKEND, env=environment, stdout=log, stderr=log, check=True)
        job = request("GET", "/admin/content/jobs/" + job["job_id"], params=SCOPE)
        save(f"{case}-job-final.json", job)
        assert job["status"] in {"completed", "completed_with_warnings"}, job["status"]
        diagnostic = request("GET", "/admin/content/jobs/" + job["job_id"] + "/diagnostic", params=SCOPE)
        save(f"{case}-diagnostic.json", diagnostic)
        print(case, job["status"], job["document_id"], flush=True)
