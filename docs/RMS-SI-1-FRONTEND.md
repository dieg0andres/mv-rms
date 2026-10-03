# RMS-SI-1.0 frontend binding

Contract revision: `13eb82e2-9762-4d96-83cc-30e6aa8b6f3e`. All fixture content is fictional/synthetic.

- Source and Idea editors submit complete snapshots using the contract’s exact wire names. Blank Source-correction content becomes `content_base64: null`; no predecessor bytes are read back into the browser.
- Idea contributions use `source_version_id`, never `source_id` alone, and display the exact Source version identifier.
- Detail/history templates show stable identity, immutable version identity, predecessor, correction reason, changed fields, actor/time, and contribution text. They do not render raw Source bytes.
- These are presentation components only. Backend must authorize routes and supply page contexts: editors only for `editor`, details/history for `editor`/`founder_viewer`, and generic anonymous/denied/not-found responses.

The integrated candidate supplies those contexts at:

```text
GET /sources/new
GET /sources/{source_id}/correct
GET /sources/{source_id}/history
GET /ideas/new
GET /ideas/{idea_id}
GET /ideas/{idea_id}/correct
GET /ideas/{idea_id}/history
```
