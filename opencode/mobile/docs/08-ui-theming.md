# 08 — UI/UX, theming engine, layout, scalability

Source of truth: grand-plan.md. Theme tokens below are the DEFAULT scheme (dark cyberpunk neon);
the engine (T1–T3) must allow full user restyling later.

## 1. Material3 Expressive (locked UI framework)

- `androidx.compose.material3:material3` (Expressive APIs; 1.4.0-alpha11 → 1.5.0-alphaX track).
- Theme entry: `MaterialExpressiveTheme(colorScheme, motionScheme, shapes, typography, content)`;
  `motionScheme = MotionScheme.expressive()` (or `.standard()`); custom components animate with
  `MaterialTheme.motionScheme.defaultSpatialSpec()/defaultEffectsSpec()`.
- New components to use: `ButtonGroup`, `LoadingIndicator` (for `PullToRefreshBox`),
  expressive shape morphing, spring motion. Dynamic color stays (`dynamicDarkColorScheme/…`).
- Catalogs: meticha/material-3-expressive-catalog, emertozd/compose-material-3-expressive-catalog.

## 2. Default theme: dark cyberpunk neon (dark default; light + auto also ship)

```
background #05010F | surface #0B0620 | surfaceContainer* ramp on deep violet
primary #00F0FF (cyan neon) | secondary #B537F2 (magenta) | tertiary #39FF14 (acid green, sparing)
error #FF2A6D | onPrimary/onSurface ≥ 4.5:1 (neon-on-black passes, neon-on-neon doesn't)
```

- Neon glow without custom draw: `Modifier.shadow(elevation, spotColor = primary)` + graphicsLayer
  on expressive springs; `drawBehind` bloom for send button only.
- Expressive Shapes: large rounded 28dp+ bubbles → cyberpunk-soft look.
- Light scheme: same hue family, lifted surfaces (define explicitly, never auto-invert).

## 3. Theme engine (T1–T3: day-one architecture)

- All color/type/shape/size values flow from `ThemeRepository` → `CompositionLocal` tokens → M3 scheme.
  NO hardcoded colors/sp/dp in features (lint-enforced).
- Token categories: colors (full M3 ramp + custom neon accents), typography (font family files + scale),
  shapes (corner radii), sizes (bubble padding, composer height, icon sizes), effects (glow on/off, spring stiffness).
- Dark / light / system-auto modes; scheme export/import JSON (user schemes later, X-scope);
  screenshot tests per scheme × mode.
- Dynamic knobs in settings (doc 13 §Theme): scheme, mode, font family, font size scale, glow intensity.

## 4. Edge-to-edge + insets (forced posture, doc 05 §5)

- `enableEdgeToEdge()` in `Activity.onCreate()`; per-component insets only:
  `windowInsetsPadding(safeDrawing)` per screen, `imePadding()` on composer,
  `navigationBarsPadding()` on bottom bars, `statusBarsPadding()` on top bars.
- Message list draws behind nav bar (transparent); composer rides ABOVE IME via animated IME inset.
- 3-button nav gets automatic translucent scrim; gesture nav fully transparent.
- Audit low-traffic screens (onboarding, settings, rationales) — commonly occluded.

## 5. Adaptive layouts (phones / foldables / tablets)

- `material3-adaptive`: `ListDetailPaneScaffold` (sessions → thread — canonical chat pattern),
  `NavigableListDetailPaneScaffold`; drive with `currentWindowAdaptiveInfo()` / `WindowSizeClass`.
- Foldables: `androidx.window WindowInfoTracker` for hinge; never place composer under hinge.
- Phone portrait: single pane + drawer; landscape/tablet: list+detail two-pane; large tablet: optional third
  pane (files/diff). State preserved across form-factor changes.

## 6. Dynamic type + i18n-proofing

- `sp` follows system scale automatically; test at 200%. No hardcoded dp heights on text containers;
  `Modifier.heightIn(min=)` + flexible layouts. Never cap `fontScale`.
- Bubble widths verified with longest-locale strings at max scale.

## 7. Chat-screen component map

- TopAppBar: session title (tap → rename), status dot, model+effort chip, agent chip, overflow menu.
- MessageList: date/session dividers; user bubbles right, agent left; tool cards collapsible;
  reasoning collapsed + timer; patch/diff expandable; todo live check-off; per-turn cost footer;
  error cards inline with retry; "jump to latest" FAB; pull-to-refresh → status-poll resync.
- Composer: `+` attach (file/photo/camera) → growing text field (vim motions H13, `/` commands H12,
  `@` path autocomplete) → mic → send/stop morph. Staged attachments as chips with ×.
  Memory toggle + websearch indicator + browser chip as above-composer status row.
- Permission cards: inline in thread at the requesting turn (Once / Always / Reject) + mirrored
  in notification (P1) + background-health pending list.

## 8. Motion + haptics

- Expressive springs for send/appear; `Confirm` haptic on send, `Reject` on error, `LongPress` on actions.
- Streaming: buffer deltas ~100–200ms before markdown-tail recompose (perf, doc 12).

## Sources

- https://m3.material.io/blog/m3-expressive-motion-theming
- https://developer.android.com/develop/ui/compose/system/setup-e2e
- https://developer.android.com/develop/ui/compose/build-adaptive-apps
- https://getstream.io/chat/docs/sdk/android/compose/overview/
- https://github.com/GetStream/stream-chat-android
- https://github.com/mikepenz/multiplatform-markdown-renderer
- https://coil-kt.github.io/coil/compose
- https://developer.android.com/media/camera/camerax
- https://developer.android.com/reference/android/speech/SpeechRecognizer
- https://github.com/KevinnZou/compose-webview (NOT Accompanist — deprecated)
