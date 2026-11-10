# H13 vim spike (maximal scope) — 2026-10-05

Source of truth: grand-plan.md (D-Vim). Status: SPIKE COMPLETE, implementation not started.

## 1. Library survey: nothing exists

- GitHub repo search `vim jetpack compose kotlin` → 1 irrelevant result (Vimystry, a video app).
- Known ecosystem: IdeaVim (IntelliJ, Swing — not reusable), `vim` emulators for Android
  keyboards (e.g. unexpected-keyboard has some motions, wrong layer), Termux vim (terminal, wrong layer).
- Conclusion (matches plan assumption): **custom implementation required**.

## 2. Architecture

- Layer: pure-Kotlin state machine in `:domain` (no Android imports) operating on
  `(text: String, cursor: Int)` → `(text, cursor, mode)` transitions. UI binds to Compose
  `TextFieldValue(text, selection)` + `KeyboardOptions` + custom key handling via
  `Modifier.onPreviewKeyEvent` for normal-mode keys (hjkl etc. arrive as key events when the
  field is focused; printable-chars path stays on the IME in insert mode).
- Do NOT fight the IME: insert mode = stock Compose text field (IME does composition,
  autocorrect, predictions). Normal/visual modes intercept hardware/software key events at the
  Compose layer and mutate TextFieldValue programmatically.
- `:w` = send, `:q` = clear+blur, `:wq` = send, `:s/a/b/` = substitute on composer text,
  `:e!` = clear. Ex line = same text field prefixed with `:` (mode=commandline).
- Registers `"0-9a-z`: in-memory map in the VM (persist named registers in DataStore later).
  Macros `q{reg}` record key-event stream; `@{reg}` replays through the same transition function
  (pure function ⇒ replay is trivially correct).
- Marks `m{a-z}` + jumps `'{a-z}`: per-composer-position map; jumps across messages not needed
  (composer-only scope). Counts prefix all motions/operators. Text objects `iw/aw/i(/a(/i{/a{ etc.
  via word/sentence/bracket scanners over the String (no LSP needed).

## 3. Phased breakdown (maximal scope)

- V1 (core, ~4–6 days): modes normal/insert/visual(+line), hjkl/wbe/ge/$/0/^/gg/G/fFtT;,./,
  i/a/I/A/o/O, x/X/s/S/r, dd/yy/p/P/u/Ctrl-r, counts, `.` repeat (last change, not motion).
- V2 (text objects + search, ~3–4 days): iw/aw/iW/aW/is/as/ip/ap/ib/ab, `/` `?` n/N, * (word under cursor).
- V3 (registers/macros/marks, ~3 days): `"ayy`, `"ap`, `qaq@a`, `m{a-z}`, `'{a-z}`, jumps list.
- V4 (ex + composer bindings, ~2–3 days): `:w/:q/:wq/:e!/:s`, counts everywhere, status-bar mode
  indicator in composer (`-- NORMAL --` chip), `vim.enabled` setting + per-composer toggle.
- Total: ~12–16 days. Test strategy: `:domain` state-machine unit tests (transition tables —
  cheap, exhaustive), then on-device key-event tests.

## 4. Risks

- Soft-keyboard key events: Gboard sends `KEYCODE_UNKNOWN` for most letters (goes through IME
  commit path, not key events). Normal-mode letters (h/j/k/l) from soft keyboards may NOT arrive
  as key events → mitigation: custom input filter using `InputConnection` wrapper
  (`InputConnectionWrapper.commitText` interception) OR an on-screen vim key row. This is the
  highest-risk item — prototype V1 against Gboard on API 26 + current BEFORE committing to V2+.
- `onPreviewKeyEvent` + `TextFieldValue` cursor control is well-trodden (verified pattern).

## 5. Decision needed (user, before V1)

- Soft-keyboard strategy if Gboard commitText interception proves flaky: (a) vim key row above
  keyboard, (b) hardware-keyboard-first with soft fallback, (c) custom IME (out of scope).
