# SPEC — P3 attachments / voice / projects / vim

Source of truth: `docs/grand-plan.md` §7. Implements: H2 (attachments), H4-dictation (voice mode deferred —
see §5), H5 (memory toggle wiring), H11 (projects per D1), H13 kickoff (vim scope + spike, non-blocking).

## 1. Attachments (H2)

- Composer `+` button → sheet: Take photo (CameraX or `TakePicture` contract) / Choose image (Photo Picker,
  no storage perm) / Choose file (SAF `OpenDocument`, any mime).
- Staging: chips above composer with thumb/name/size + × remove. Images downscaled + JPEG-compressed
  client-side per settings (max dimension, quality) BEFORE base64; files ≤ setting cap (default 10MB,
  refuse larger with reason). HEIC/PNG → JPEG convert for photos.
- Send: `FilePartInput{type:"file", mime, filename, url:"data:<mime>;base64,..."}` appended after the
  text part (doc 07 probe: verified round-trip). Mixed text+files in one `prompt_async`.
- Thread render: image parts → Coil thumbnail, tap → zoom/pan viewer (P3 basic viewer: full-screen
  pan/zoom, share via system sheet). Non-image files → file card (name/mime).
- Settings honored: image compression (off/light/medium), max dimension, camera resolution.

## 2. Voice dictation (H4-dictation)

- Composer mic button → platform `SpeechRecognizer` (on-device if available) with partial results
  streamed into the composer text; error states (no speech, no permission) inline.
  Runtime `RECORD_AUDIO` request with rationale (X5 aggressive list covers it).
- Full-duplex voice MODE (conversation) → DEFERRED (§5): needs TTS + turn-taking + audio session
  management; own workstream after P4.

## 3. Projects (H11, D1)

- Client-side `Project` entity: `{id, name, directories[], instructions, memoryNote}` stored in
  DataStore (Room deferred to P4; DataStore JSON list suffices for P3 scale).
- Sessions screen: project filter chips (All + projects); new-session sheet offers project attach
  (sets default directory + injects instructions/memory as `system` prompt on first send of session).
- Projects manager screen (from Sessions overflow): CRUD + directory multi-add (via server `/project`
  worktree picker) + instructions/memory editors.
- H5 memory toggle: per-message effect = include/exclude the project's memoryNote (+ global simple-memory
  note TBD) from the `system` injection. Composer status row shows memory chip state (chip UI in P3,
  injection log line in debug).

## 4. Vim workstream kickoff (H13, non-blocking)

- Spike: survey Compose vim options (no known mature lib — expect custom `InputConnection` wrapper
  around the composer `TextFieldValue` + mode state machine). Deliverable: `docs/vim-spike.md` with
  approach + effort estimate + maximal-scope breakdown (normal/insert/visual, motions+text objects,
  registers, macros, marks/jumps, `:s`, counts). NO composer changes in P3 (parallel track).

## 5. Explicit non-goals / deferrals

- Voice MODE (full duplex), audio messages (record/play) → post-P4 workstream.
- Room (weekly stats store, message cache) → P4 with push bridge.
- Vim implementation → own workstream after spike approval.
- Image zoom viewer: basic pan/zoom + share in P3; annotate/crop later.

## 6. Acceptance

1. Photo → staged chip → send → server thread shows file part (verify via GET message mime/filename).
2. Gallery image + SAF file stage/send the same way; oversize file refused with reason.
3. Compression settings change resulting upload bytes (spot-check sizes).
4. Mic → dictated text appears in composer; denied perm → rationale + settings deep-link.
5. Project CRUD; session attached to project sends with `system` injection (verify via OkHttp body log).
6. Memory toggle flips injection on/off.
7. Vim spike doc written with estimate; no composer regression (existing tests green).
8. Tests: compression/staging VM tests, project repo tests, MockWebServer (file part body shape).
   Screenshots: attach sheet, staged chips, viewer, dictation, projects screens.

## 7. Review gate

Tests green · emulator screenshots · live file-part round-trip vs server · grand-plan cross-check
(H2, H4-dictation, H5, H11, H13-spike) · user review.
