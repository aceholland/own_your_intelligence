# Own interaction contract

Business authority: `PRODUCT.md`, user requirements recorded there. All workspaces belong to one local owner; no claim of multi-user security, encryption, model training or model-weight export. No billing or external tool execution. No destructive operations in this milestone. Download exposes the selected workspace's business data to a local ZIP file, with an explicit explanation before download.

## Canonical UI Map
| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | `web/app.js` native select fields | DESIGN.md + this contract | workspace/model/mode | browser keyboard and popup |
| Form | `field()` and `formAction()` | this contract + API validation | create/edit | browser create and invalid form |
| Scrollbar | `web/styles.css` global baseline | DESIGN.md | document/modal | narrow viewport inspection |
| Toast | `notify()` and `#toast` | this contract | success/info/error | live-region browser inspection |
| CRUD | `api()`, workspace/job route functions | PRODUCT.md | create/read/update only | Python API tests and browser flow |

## Flow ledger
- Create workspace: name → saved workspace home → success toast. API errors keep modal and input.
- Create job: name and goal → saved Teach it screen → success toast. Source: PRODUCT.md milestone.
- Save instructions/model: explicit Save → retain same screen → saved toast. Stale revision returns inline conflict and offers refresh; never silently overwrite.
- Add teaching/check example: same shared dialog → close only after success → owning screen updates. A check is never included in a teaching prompt or training JSONL. Source: PRODUCT.md isolation contract.
- Try: pending text explains laptop speed; answer only after actual inference; failure retains request and displays recovery. One inference at a time on laptop. No optimistic answer.
- Correction: editable answer in dialog → teaching example saved to draft → live version unchanged. Source: PRODUCT.md approval contract.
- Check: background work with actual completed count → per-case human review → no automated claim of correctness. Changing snapshot makes results visibly stale.
- Approve or switch version: app dialog explains exact effect and requires explicit action. Draft remains editable; approved immutable snapshots retain old documents and examples. Source: PRODUCT.md lifecycle.
- Export: modal explains private data, training JSONL and absent model weights → explicit Download workspace → same screen.

## Behavior
One shared modal uses `<dialog>.showModal()`, titled by `aria-labelledby`; close restores trigger focus, serious actions focus Cancel. Toast is a shared polite live region. Forms use novalidate with app-owned errors, associated labels/help, aria-invalid and first invalid field focus. Textareas do not resize manually and have generous heights.

Save and generation buttons have stable minimum geometry and disabled/busy states. User input stays in the current form on errors. Unsaved instruction changes require a navigation choice; try-request drafts are kept in memory by job. No sensitive content in URLs or browser storage. Route hash stores workspace ID, job ID and screen only. History restores navigation; invalid routes show a recoverable error.

Polling is restricted to active evaluations and ignores stale route responses. Empty library and examples show next steps. Every background error remains inline, beyond toast lifetime. Status colors have equivalent text. No table selection, paging, date picker, password, search, multi-user session or payment primitives are applicable.

## Scope limits
Files: UTF-8 .txt/.md/.csv, <=1 MB and <=200,000 characters, up to 40 per workspace. One file per upload; picker and drop surface share validation/error behavior. No PDF parser in this milestone. Workspaces <=30, jobs <=100, examples <=200; check runs <=10. Only recent 20 answers and 10 check runs are shown; exports include that same recent history plus all sources, examples and approved versions.

## Accessibility and locale
Native buttons/links/labels, keyboard focus, skip link, semantic navigation, responsive document scroll, reduced motion and text alternatives. Target WCAG 2.2 AA without claiming certification. English messages; dates rendered through Intl in browser timezone. Native select popup geometry is accepted. Server error messages are plain English. Offline requests retain input and advise reconnect/retry.
