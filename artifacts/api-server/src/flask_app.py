"""Flask API for CampusSathi.

This file keeps the project easy to explain in a B.Tech minor-project viva:
PyMuPDF extracts PDF text, small Python functions produce extractive summaries
and keyword-matched answers, and JSON/files on the server's local disk persist
the notes without an external AI service or object-storage API.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf
from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

# Keep the index and PDFs beside the Flask source so local runs use predictable
# paths regardless of which directory the workflow starts from.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
NOTES_FILE = DATA_DIR / "notes.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# A lock prevents overlapping requests from overwriting the local JSON index.
STORE_LOCK = threading.RLock()
SUBJECTS = {"DSA", "DBMS", "OS", "CN"}
NOT_FOUND_ANSWER = "Answer not found in your notes"

STOP_WORDS = {
    "about", "after", "again", "also", "among", "and", "are", "because",
    "been", "before", "being", "between", "can", "could", "does", "each",
    "for", "from", "have", "here", "into", "itself", "more", "most",
    "not", "only", "other", "our", "over", "same", "some", "such", "than",
    "that", "the", "their", "them", "then", "there", "these", "they",
    "this", "those", "through", "under", "until", "very", "was", "were",
    "what", "when", "where", "which", "while", "will", "with", "would",
    "you", "your",
}


def read_notes() -> list[dict[str, Any]]:
    """Read the local JSON note index; a missing file is an empty workspace."""
    if not NOTES_FILE.exists():
        return []
    try:
        data = json.loads(NOTES_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        # Fail loudly rather than silently replacing a damaged index.
        raise RuntimeError("The local notes index could not be read.")


def write_notes(notes: list[dict[str, Any]]) -> None:
    """Atomically replace the local index so a partial write cannot corrupt it."""
    temporary_file = NOTES_FILE.with_suffix(".json.tmp")
    temporary_file.write_text(
        json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary_file, NOTES_FILE)


def keywords(text: str) -> list[str]:
    """Return meaningful, lower-cased keywords in frequency order."""
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]*", text.lower())
    filtered = [token for token in tokens if len(token) > 2 and token not in STOP_WORDS]
    return [word for word, _count in Counter(filtered).most_common()]


def get_sentences(text: str) -> list[str]:
    """Split extracted PDF text into readable sentence-sized study points."""
    flattened = re.sub(r"[ \t]+", " ", text.replace("\r", " "))
    sentences = re.split(r"(?<=[.!?])\s+|\n+", flattened)
    return [sentence.strip(" \t•-") for sentence in sentences if sentence.strip()]


def make_summary(extracted_text: str) -> dict[str, Any]:
    """Build an extractive summary from only the first 500 PDF words.

    Keyword frequency ranks sentences already present in the student's notes;
    this function does not generate or supplement facts.
    """
    first_words = re.findall(r"\S+", extracted_text)[:500]
    excerpt = " ".join(first_words)
    terms = keywords(excerpt)
    top_terms = terms[:4]
    sentences = get_sentences(excerpt)

    # Select sentence snippets by how many top keywords they contain.
    ranked = sorted(
        enumerate(sentences),
        key=lambda pair: (
            -sum(1 for term in top_terms if term in pair[1].lower()),
            pair[0],
        ),
    )
    selected: list[str] = []
    for _position, sentence in ranked:
        if not selected or sentence not in selected:
            selected.append(sentence)
        if len(selected) == 6:
            break

    # Formula and definition callouts are also copied from the same 500-word
    # source excerpt, then capped to keep revision cards concise.
    formulas = [
        sentence
        for sentence in sentences
        if re.search(r"(?:=|≈|≠|≤|≥|∑|√|∫|O\s*\(|\b(?:log|sin|cos)\s*\()", sentence)
    ][:5]
    definition_pattern = re.compile(
        r"\b(?:is defined as|is a|is an|are a|refers to|means|definition of)\b",
        re.IGNORECASE,
    )
    definitions = [sentence for sentence in sentences if definition_pattern.search(sentence)][:5]

    return {
        "topic": " · ".join(term.title() for term in top_terms) or "Key ideas from your notes",
        "bullets": selected or ["No readable text was found in the first 500 words."],
        "formulas": formulas,
        "definitions": definitions,
        "sourceWordCount": len(first_words),
    }


def split_paragraphs(text: str) -> list[str]:
    """Preserve PDF paragraphs, with sentence groups as a fallback."""
    raw_paragraphs = [
        re.sub(r"\s+", " ", piece).strip()
        for piece in re.split(r"\n\s*\n+", text.replace("\r", ""))
        if piece.strip()
    ]
    if len(raw_paragraphs) > 1:
        return raw_paragraphs

    sentences = get_sentences(text)
    return [
        " ".join(sentences[index:index + 3])
        for index in range(0, len(sentences), 3)
        if sentences[index:index + 3]
    ]


def public_note(note: dict[str, Any]) -> dict[str, Any]:
    """Strip private extracted text and local file paths from API responses."""
    return {
        "id": note["id"],
        "ownerId": note["ownerId"],
        "title": note["title"],
        "subject": note["subject"],
        "filename": note["filename"],
        "fileSize": note["fileSize"],
        "uploadedAt": note["uploadedAt"],
        "isShared": note["isShared"],
        "summary": note["summary"],
    }


def find_note(notes: list[dict[str, Any]], note_id: str) -> dict[str, Any] | None:
    return next((note for note in notes if note.get("id") == note_id), None)


@app.errorhandler(413)
def file_too_large(_error: Exception):
    return jsonify({"error": "PDF must be smaller than 20 MB."}), 413


@app.get("/api/healthz")
def health_check():
    return jsonify({"status": "ok"})


@app.post("/api/dashboard")
def dashboard():
    data = request.get_json(silent=True) or {}
    owner_id = str(data.get("ownerId", "")).strip()
    if not owner_id:
        return jsonify({"error": "ownerId is required."}), 400

    with STORE_LOCK:
        notes = [note for note in read_notes() if note.get("ownerId") == owner_id]

    return jsonify({
        "totalNotes": len(notes),
        "sharedNotes": sum(1 for note in notes if note.get("isShared")),
        "totalWords": sum(note.get("summary", {}).get("sourceWordCount", 0) for note in notes),
        # This is a simple planning estimate, not a tracked timer.
        "hoursSaved": min(len(notes) * 3, 21),
    })


@app.get("/api/notes")
def shared_notes():
    subject = request.args.get("subject", "").strip().upper()
    if subject and subject not in SUBJECTS:
        return jsonify({"error": "Subject must be DSA, DBMS, OS, or CN."}), 400

    with STORE_LOCK:
        notes = [note for note in read_notes() if note.get("isShared")]
    if subject:
        notes = [note for note in notes if note.get("subject") == subject]
    notes.sort(key=lambda note: note.get("uploadedAt", ""), reverse=True)
    return jsonify([public_note(note) for note in notes])


@app.post("/api/notes/mine")
def my_notes():
    data = request.get_json(silent=True) or {}
    owner_id = str(data.get("ownerId", "")).strip()
    if not owner_id:
        return jsonify({"error": "ownerId is required."}), 400

    with STORE_LOCK:
        notes = [note for note in read_notes() if note.get("ownerId") == owner_id]
    notes.sort(key=lambda note: note.get("uploadedAt", ""), reverse=True)
    return jsonify([public_note(note) for note in notes])


@app.post("/api/notes")
def upload_note():
    owner_id = request.form.get("ownerId", "").strip()
    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip().upper()
    pdf = request.files.get("file")

    if not owner_id or not title or not pdf:
        return jsonify({"error": "Owner, note title, subject, and PDF are required."}), 400
    if subject not in SUBJECTS:
        return jsonify({"error": "Subject must be DSA, DBMS, OS, or CN."}), 400
    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Choose a PDF file."}), 400

    pdf_bytes = pdf.read()
    if not pdf_bytes.startswith(b"%PDF-"):
        return jsonify({"error": "The selected file is not a valid PDF."}), 400

    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        extracted_text = "\n\n".join(page.get_text("text") for page in document).strip()
        document.close()
    except Exception:
        return jsonify({"error": "This PDF could not be opened. Check that it is not damaged or password-protected."}), 400

    if not extracted_text:
        return jsonify({"error": "No selectable text was found. Scanned PDFs need OCR before they can be summarized."}), 422

    note_id = str(uuid.uuid4())
    original_filename = secure_filename(pdf.filename) or "study-notes.pdf"
    stored_filename = f"{note_id}.pdf"
    local_file = UPLOAD_DIR / stored_filename
    local_file.write_bytes(pdf_bytes)

    note = {
        "id": note_id,
        "ownerId": owner_id,
        "title": title[:120],
        "subject": subject,
        "filename": original_filename,
        "fileSize": len(pdf_bytes),
        "uploadedAt": datetime.now(timezone.utc).isoformat(),
        # The Share Hub is meant to make uploaded course notes useful to juniors.
        # Students can still turn sharing off from the workspace at any time.
        "isShared": True,
        "summary": make_summary(extracted_text),
        "extractedText": extracted_text,
        "localFile": str(local_file),
    }
    try:
        with STORE_LOCK:
            notes = read_notes()
            notes.append(note)
            write_notes(notes)
    except Exception:
        local_file.unlink(missing_ok=True)
        raise

    return jsonify(public_note(note)), 201


@app.post("/api/notes/share")
def set_note_sharing():
    data = request.get_json(silent=True) or {}
    owner_id = str(data.get("ownerId", "")).strip()
    note_id = str(data.get("noteId", "")).strip()
    is_shared = data.get("isShared")
    if not owner_id or not note_id or not isinstance(is_shared, bool):
        return jsonify({"error": "ownerId, noteId, and isShared are required."}), 400

    with STORE_LOCK:
        notes = read_notes()
        note = find_note(notes, note_id)
        if not note or note.get("ownerId") != owner_id:
            return jsonify({"error": "Note not found in your notes."}), 404
        note["isShared"] = is_shared
        write_notes(notes)
    return jsonify(public_note(note))


@app.post("/api/notes/question")
def ask_note_question():
    data = request.get_json(silent=True) or {}
    owner_id = str(data.get("ownerId", "")).strip()
    note_id = str(data.get("noteId", "")).strip()
    question = str(data.get("question", "")).strip()
    if not owner_id or not note_id or not question:
        return jsonify({"error": "ownerId, noteId, and question are required."}), 400

    with STORE_LOCK:
        note = find_note(read_notes(), note_id)
    if not note or note.get("ownerId") != owner_id:
        return jsonify({"error": "Note not found in your notes."}), 404

    question_terms = set(keywords(question))
    best_paragraph = ""
    best_matches: set[str] = set()
    best_score = 0
    for paragraph in split_paragraphs(note.get("extractedText", "")):
        paragraph_terms = set(keywords(paragraph))
        matches = question_terms & paragraph_terms
        score = len(matches)
        if score > best_score:
            best_score = score
            best_paragraph = paragraph
            best_matches = matches

    if best_score == 0:
        return jsonify({
            "answer": NOT_FOUND_ANSWER,
            "found": False,
            "matchedKeywords": [],
        })

    return jsonify({
        "answer": best_paragraph[:1800],
        "found": True,
        "matchedKeywords": sorted(best_matches),
    })


@app.post("/api/notes/delete")
def delete_note():
    data = request.get_json(silent=True) or {}
    owner_id = str(data.get("ownerId", "")).strip()
    note_id = str(data.get("noteId", "")).strip()
    with STORE_LOCK:
        notes = read_notes()
        note = find_note(notes, note_id)
        if not owner_id or not note or note.get("ownerId") != owner_id:
            return jsonify({"error": "Note not found in your notes."}), 404
        remaining = [item for item in notes if item.get("id") != note_id]
        write_notes(remaining)
    Path(note.get("localFile", "")).unlink(missing_ok=True)
    return "", 204


@app.post("/api/notes/download")
def download_note():
    data = request.get_json(silent=True) or {}
    owner_id = str(data.get("ownerId", "")).strip()
    note_id = str(data.get("noteId", "")).strip()
    with STORE_LOCK:
        note = find_note(read_notes(), note_id)
    if not note or (note.get("ownerId") != owner_id and not note.get("isShared")):
        return jsonify({"error": "Note not found or is not shared."}), 404
    local_file = Path(note.get("localFile", ""))
    if not local_file.is_file():
        return jsonify({"error": "The local PDF file is missing."}), 404
    return send_file(
        local_file,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=note.get("filename", "study-notes.pdf"),
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        debug=False,
    )
