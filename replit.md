# CampusSathi

CampusSathi helps B.Tech CSE students extract revision points from lecture PDFs, search questions within their own notes, and share useful material by subject.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the Flask API server
- `pnpm --filter @workspace/campus-sathi run dev` — run the React + Vite frontend
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- Python dependencies are listed in `requirements.txt` and `pyproject.toml`.
- Uploaded PDFs and `notes.json` are written to `artifacts/api-server/data/` locally.

## Stack

- Frontend: React, Vite, Tailwind CSS, TypeScript
- API: Python Flask
- PDF extraction: PyMuPDF
- Local persistence: JSON index plus PDF files
- API client generation: Orval from `lib/api-spec/openapi.yaml`

## Where things live

- `artifacts/campus-sathi/` — responsive student-facing web app
- `artifacts/api-server/src/flask_app.py` — PDF upload, local persistence, summary, sharing, and note-only Q&A
- `lib/api-spec/openapi.yaml` — API contract source of truth
- `README.md` — project overview and viva-ready stack/future scope

## Architecture decisions

- Summaries rank sentences from only the first 500 extracted words; no external AI provider is used.
- Q&A searches paragraphs from the selected note and does not add outside facts.
- PDFs and extracted text are kept in a local JSON/file store to honor the request for local-only persistence.
- The browser-generated owner ID is for a classroom demo, not secure user authentication.

## Product

- Upload and summarize DSA, DBMS, OS, and CN PDFs.
- Search doubts against a selected personal note and share notes with juniors.

## User preferences

- Do not add OpenAI or other external AI/API keys; keep summary and Q&A local and keyword-based.
- Keep uploaded files and note data on local storage.

## Gotchas

- Local JSON/filesystem persistence is single-process and is not suitable for multi-instance scaling without replacing the storage layer.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
