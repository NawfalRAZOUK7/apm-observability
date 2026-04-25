# Rapport TeX - Suggestions & Plan (Checklist)

## Suggestions (checklist)
- [ ] Add short `Introduction` section before Chap1 (new file or in main).
- [ ] Add `Conclusion et perspectives` after Chap4.
- [ ] Move cloud vs on-prem conclusion from Chap4 into final conclusion.
- [ ] Add `docs/Tex/main.tex` with `\documentclass`, preamble, and `\input` of all chapters.
- [ ] Replace Markdown inside LaTeX verbatim blocks; use `\url{}` and `\texttt{}`.
- [ ] Add citations for claims (compression ratio, enterprise list) using `\cite{}`.
- [ ] Merge duplicated cloud vs on-prem conclusion into a single final section.
- [ ] Align the cluster description with `docker/cluster/docker-compose.*`.
- [ ] Clarify endpoints: `/api/requests/ingest/` for bulk ingest, `/api/requests/` for CRUD.
- [ ] Add concrete backup/seed commands matching the Makefile and backup compose stack.
- [ ] Expand Grafana section with datasource config, example queries, and panel list.
- [ ] Add the referenced images or update `\includegraphics{}` paths.
- [ ] Ensure preamble includes `graphicx`, `float`, `booktabs`, and `url` (or `hyperref`).

## Updating (checklist)
- [ ] Add `Abstract`, `List of Figures`, and a numeric bibliography style (IEEE-like).
- [ ] Create `docs/Tex/images/` and add `timescaledb.png` and `grafana_dashboard.png` (or update paths).
- [ ] Add `docs/Tex/main.tex` and verify the document compiles.
- [ ] Fix `curl` examples to be raw commands (no Markdown links).
- [ ] Update Chap2 cluster section to match the real Docker Compose files.
- [ ] Enrich Chap3 practical section with real steps and outputs from this repo.
- [ ] Move or rewrite the Chap4 conclusion to avoid repetition.

## Plan (checklist)
- [ ] Phase 0 - Scope: target length 15-25 pages (adjust if a template exists).
- [ ] Phase 1 - Structure: create `main.tex` with preamble + chapter inputs.
- [ ] Phase 1 - Structure: add Intro + Conclusion/Perspectives sections.
- [ ] Phase 1 - Structure: verify required LaTeX packages for tables, figures, and URLs.
- [ ] Phase 2 - Content: correct commands, endpoints, and cluster description.
- [ ] Phase 2 - Content: add backup/seed/grafana details aligned with repo.
- [ ] Phase 2 - Content: add citations and bibliography entries.
- [ ] Phase 3 - Assets: add images or update paths and captions.
- [ ] Phase 3 - Review: build the PDF and do a quick consistency pass.
