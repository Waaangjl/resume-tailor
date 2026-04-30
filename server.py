#!/usr/bin/env python3
"""Local dev server — serves the wizard frontend and exposes /api endpoints."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from flask import Flask, Response, jsonify, request, send_from_directory

import build
import fetch as fetch_mod
from tailor import DEFAULT_STYLE, draft_stories, generate_cover_letter, tailor_with_fit

app = Flask(__name__)


@app.route("/")
def index():
    return send_from_directory(ROOT / "frontend", "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(ROOT / "frontend", filename)


@app.route("/api/health")
def health():
    return jsonify({"ok": True})


@app.route("/api/compile-pdf", methods=["POST"])
def api_compile_pdf():
    latex = (request.json or {}).get("latex", "")
    if not latex.strip():
        return jsonify({"ok": False, "error": "No LaTeX provided"}), 400
    with tempfile.TemporaryDirectory() as tmp:
        tex_path = Path(tmp) / "resume.tex"
        tex_path.write_text(latex, encoding="utf-8")
        pdf_path = build.compile_pdf(tex_path)
        if pdf_path and pdf_path.exists():
            return Response(pdf_path.read_bytes(), content_type="application/pdf")
    return jsonify({"ok": False, "error": "PDF compilation failed — is pdflatex installed?"}), 500


@app.route("/api/fetch-jd", methods=["POST"])
def api_fetch_jd():
    url = (request.json or {}).get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "No URL provided"}), 400
    try:
        text = fetch_mod.get_jd(url)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if not text.strip():
        return jsonify({"ok": False, "error": "Page returned no readable text — paste the JD directly."})
    return jsonify({"ok": True, "text": text})


@app.route("/api/draft-stories", methods=["POST"])
def api_draft_stories():
    body       = request.json or {}
    resume_tex = (body.get("resume", {}).get("latex", "") or "").strip()
    jd_data    = body.get("jd", {})
    jd_text    = (jd_data.get("text", "") or "").strip()
    model      = body.get("model", "sonnet")

    if not resume_tex:
        return jsonify({"ok": False, "error": "Need a resume (LaTeX) before drafting stories."}), 400

    try:
        if not jd_text and jd_data.get("url"):
            jd_text = fetch_mod.get_jd(jd_data["url"])
        stories = draft_stories(resume_tex, jd_text, model)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    if not stories:
        return jsonify({"ok": False, "error": "Could not draft stories — try again or write your own."}), 500
    return jsonify({"ok": True, "stories": stories})


def _evt(event: str, **data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.route("/api/generate", methods=["POST"])
def api_generate():
    body        = request.json or {}
    resume_data = body.get("resume", {})
    jd_data     = body.get("jd", {})
    profile     = body.get("profile", {})
    stories     = body.get("stories", [])
    voice_data  = body.get("voice", {})
    model_name  = body.get("model", "sonnet")

    resume_tex = (resume_data.get("latex") or "").strip()
    jd_text    = (jd_data.get("text") or "").strip()
    jd_url     = (jd_data.get("url") or "").strip()

    if not resume_tex:
        return jsonify({"ok": False, "error": "Resume content is missing — pick a file or paste LaTeX."}), 400
    if not jd_text and not jd_url:
        return jsonify({"ok": False, "error": "Job description is missing — paste text or provide a URL."}), 400

    def stream():
        nonlocal jd_text
        try:
            if not jd_text and jd_url:
                yield _evt("progress", step=0, label="Fetching job description…")
                try:
                    jd_text = fetch_mod.get_jd(jd_url)
                except Exception as e:
                    yield _evt("error", message=f"Could not fetch JD: {e}")
                    return
                if not jd_text.strip():
                    yield _evt("error", message="Fetched page returned no readable text — paste the JD directly.")
                    return

            yield _evt("progress", step=1, label="Extracting job metadata…")
            meta = build.extract_jd_meta(jd_text, model_name)

            yield _evt("progress", step=2, label="Tailoring resume…")
            tailored_tex, _pdf_bytes, fit_summary = tailor_with_fit(
                jd_text, resume_tex, model_name,
            )

            yield _evt("progress", step=3, label="Building diff…")
            diff_html = build.make_html_diff(
                resume_tex, tailored_tex,
                company=meta.company, role=meta.role,
            )

            yield _evt("progress", step=4, label="Writing cover letter…")
            story_objs = [s for s in stories if s.get("text", "").strip()] or None
            style      = voice_data.get("sample") or DEFAULT_STYLE
            cover      = generate_cover_letter(
                jd_text, resume_tex, meta, model_name, profile, style,
                stories=story_objs,
            )

            yield _evt("done",
                tailored_tex=tailored_tex,
                cover_letter=cover,
                diff_html=diff_html,
                company=meta.company.replace("_", " "),
                role=meta.role.replace("_", " "),
                jd_text=jd_text,         # round-trip so frontend match score uses real JD prose, not URL slug
                fit_summary=fit_summary,
            )
        except Exception as e:
            yield _evt("error", message=str(e))

    return Response(
        stream(),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
    print(f"\n  resume-tailor  →  http://localhost:{port}\n")
    app.run(port=port, debug=False, threaded=True)
