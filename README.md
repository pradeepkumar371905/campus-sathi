# CampusSathi - A Solution for B.Tech Students

CampusSathi is a study workspace for B.Tech CSE students who need to organize lecture notes, revise key ideas quickly, and share useful PDFs with juniors.

## Problem

Students often keep class notes across scattered PDFs and folders. Finding definitions, formulas, or the one paragraph that answers a doubt takes time, and good notes rarely reach the next batch.

## Solution

Upload a subject PDF, get a compact keyword-based revision summary, search a question against that PDF's extracted text, and make the note visible to juniors in the subject hub. New uploads are shared by default and can be made private.

## Features

- Home page explaining the problem, solution flow, and daily study-time goal.
- Dashboard to upload CSE subject PDFs for DSA, DBMS, OS, and CN.
- PyMuPDF text extraction and an extractive, keyword-ranked summary based on the first 500 words.
- Formula and definition callouts copied from the uploaded material.
- Doubt search that returns the most relevant paragraph from the selected note only. If no question keywords are found, it says: **“Answer not found in your notes”.**
- Share Hub with subject filtering, share/unshare controls, and PDF downloads.
- Responsive blue-and-white interface and a viva-oriented project objective section.
- A browser-local profile ID separates each browser's personal notes. No account or external AI/API key is required.

## Tech Stack

- **Frontend:** HTML, Tailwind CSS, JavaScript (React + Vite)
- **Backend:** Python Flask
- **PDF reading:** PyMuPDF
- **Local persistence:** PDF files and a JSON note index saved under `artifacts/api-server/data/`
- **API contract/client:** OpenAPI with generated TypeScript hooks for the React frontend

The keyword summary and Q&A use deterministic local text processing, not a generative AI model. PDFs are stored on the server's local filesystem, not in cloud object storage.

## Run locally

Install the workspace dependencies, then start the API and frontend using their Replit workflows:

```bash
pnpm install
pnpm --filter @workspace/api-server run dev
pnpm --filter @workspace/campus-sathi run dev
```

The Flask API uses `PORT` from the workflow environment. Python dependencies are listed in `requirements.txt` and `pyproject.toml`.

## Future Scope

- Add an AI chatbot that can explain concepts while citing the uploaded source.
- Add a plagiarism checker for student submissions.
- Add OCR support for scanned/image-only lecture PDFs.
- Add authenticated student accounts and cross-device note synchronization.

## Local data and privacy

Uploaded PDFs and the extracted note index stay on the server's local disk in `artifacts/api-server/data/`. The index is ignored by Git. The browser-generated profile ID is a lightweight local identifier, not a secure sign-in system; do not use it to protect sensitive or private documents in a public deployment.

The current file-based store is intended for a single-process project/demo. A multi-instance deployment would need a shared database and persistent file storage.
