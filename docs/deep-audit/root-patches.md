# Root reachable patch audit — in progress

Current canonical coverage: `root-patches-coverage-current.jsonl` has one record for each of4,205(commit,path) changes, with positive evidence and superseded raw-row references. The original `root-patches-coverage.jsonl` is preserved as a4,954-row trace containing749 superseded pending duplicates; do not count its raw statuses as unresolved semantic scope.




Read-only Git object review at root HEAD ccb0b49195cfcd4fc11ea86cb15294e603e2a753.188 reachable commits;4,205 raw recursive file-change records (including root commits, gitlinks and mode changes) inventoried. Metadata/object hashes are not semantic reads. opencode/ history belongs to history_intent. Reflog/unreachable objects remain parent/history scope. No tests, builds, checkouts, source edits or live changes.

First semantic patch slice: ccb0b49,27a842f,2821315,0ef16d4,df47f6b,169df0b,9527ac2,5d3b9da,c5f51ae in full. Per-file ledger records exact old/new blobs and changed/deleted mode, with all other historical changes pending.

The tmux sequence supplies precise taste evidence: initial5d3b9da preserves native choose-tree preview/mouse/destructive confirmation while adding reversible hide/reveal; c5f51ae moves archive to z to restore native h/l collapse and adds hierarchical workspace listing/default sessions. Those defaults are historical, later superseded by explicit empty workspace intent in current source.169df0b restores original diamond icon;9527ac2 restricts help hint to picker visibility. df47f6b deletes the entire nine-frame ease-out reveal, preferring immediate centered buffered first frame.0ef16d4 moves capsule edges into the margin so selected/unselected label starts align, caches state path, batches tmux RPCs, and chooses direct executable launch on3.7+ to avoid shell startup cost.2821315 removes outside popup margins;27a842f removes status-row reservation and adds a nested real-terminal sentinel test, acknowledging PTY size alone failed to establish pixel/row coverage. ccb0b49 separates outline accent from solid BODY/BORDER background so rounded corner outside cells show terminal background.

These are semantic changes visible in patches, not just commit-subject inference. Historical performance/test claims in HANDOFF are owner/previous-agent evidence, not tests rerun during this audit. No zero-new or complete-history claim.

## Installer repair sequence — full patches, not subjects

Additional full patches read:343eb0a,8f0e4fc,672cac1,f057c12,5337ee0,75932a3,c91158a,4bdda89,96094f7,866269e,7206219,75de8c8,85cf499,410a021,b209254,cbe415a,5bc4368,fb7d45b,3499734,97559e4,ed416ed,4f2988e,3652c83,d4b9dc7,e313e0e,4c33478,712e4a2,5879a76.

This chronology makes a repeated ideology observable: an installed executable or exit-zero command is insufficient; the expected user behavior must exist.343eb0a moves wa build from dev to messaging so selecting messaging actually yields its TUI.5337ee0 wraps both xfconf and gsettings in dbus-run-session, because gsettings can exitzero without committing; f057c12 catches manually-authored steps that bypass this wrapper.75932a3 tests installed link rather than the installer's PATH. c91158a brings hardware question detection into headless --apply, preventing Intel fallback on AMD.75de8c8 removes yay from the package catalogue to avoid replacing a working yay-bin helper with conflicting source package.672cac1 rejects wallust-git v4alpha fallback because it cannot read the v3 config, moving to locked crates.io v3 cargo install and a visibility symlink.410a021 explicitly documents `after` as documentary/file-order based, matching INF004 rather than runtime dependency enforcement.

Historical root install3652c83 was a malformed Bash header, `ln -d s` entries, copying scripts into /usr/bin and immediate hyprctl reload; ed416ed repairs ln flags but keeps relative targets/copies. This makes the later symlink-to-current-source approach a meaningful migration, not an arbitrary preference.96094f7 explains stale /usr/bin copies shadowed by /usr/local/bin; current c2a is intentionally outside repo because of embedded authentication material (no values read/reproduced here).

fb7d45b adds busy indication and pushes freshly observed VPN state directly after confirmation, replacing an8-second poll lag; this substantiates desktop adapter design.3499734 records fullscreen tag identity sticking after state changes and reload returning ok without removing it; remapping/new windows are the historical acceptance boundary.85cf499 also contains unrelated UI/theme seam corrections: two-row capsule ends are flattened to stop hourglass pinching.5879a76 implements heuristic decrypt-retry stub hiding by same sender/60-second successor, retaining a stub with no such successor; this is a display heuristic rather than message-ID correlation.

37 complete commits/70 file patches read at this checkpoint; all other file patches remain explicitly pending.

## Early configuration and visual taste slice

Full additional patches:3f97e0e,2803c43,b724da7,aed8bfb,c570931,747caee,f4c334e,f189670,0c7c83a,b7ee005,47e2503,7d010e9,f3ae4dc,f78f1ee,1316fdc,4fd054b,ed39570,e9a9fc7,ac5950e.

The style history is measured geometry: c570931 stops painting a nested volume capsule twice; aed8bfb increases workspace disc to38square after measured32x33 fill looked oval, accounts for collapsed slider reserving width, and shifts speaker by padding.3f97e0e replaces uniquely glossy three-stop shortcut gradients with shared flat raised fill and hairline, prevents text-hover rectangle inside open notification card, and hides GTK scrollbars because they visually sit outside glass styling.747caee/2803c43 replace magic notification radii with shared token. These prove consistency is sought through shared tokens and observed glyph/pixel proportions, rather than merely declaring a theme.

Earlier Hypr patches preserve machine churn and unfinished experiments: user-home launcher paths change scriptkid to bu, then become sourced custom.conf excluded from Git; f3ae4dc introduces LIBVA_DRIVER_NAME=iHD with Quest comment, and old global floating/centering rules appear in0c7c83a. These are historical provenance, not current live config recommendations.7d010e9 reservesF1–F12special workspaces and moves recorder chords to avoid collisions. Hyprlock patches add grace/cursor hiding/DPMS then change typography and remove blur. b724da7 adds Lua entrypoint as symlink to lua/hyprland.lua.

56 complete commits/99 file patches read;4,106file patches still pending. No whole-history or zero-new claim.

## Safety and proof history slice

Full patches18ff78f,9d04621,9c43680,2266780,34d76fe,a4df267,d5c6233,b9a4aa4,4e32237,afa82fa read; only installer/data/steps.toml path read in mixed45d6fb8/36f9346(opencode historical portion delegated). Credential-related lines omitted entirely from afa82fa output; no secret values persisted.

4e32237 closes root-helper capability escalation paths by per-file key allowlists, rejecting control-bearing/oversized values, and refusing to create missing keys: path-only restriction had allowed WireGuard executable hooks and Forti pppd plugins. d5c6233 supplies the actual one-at-time AUR runner loop, reports independent failures, extends bootstrap tmux lifespan, and sets TPM environment in server state rather than child shell. b9a4aa4 removes restored copycat plugin because it hijacked Escape/copy via asynchronous wrappers; native tmux search plus double/triple click behavior replaces it. Reinitializing a once-missing plugin exposed the regression, explaining why a reproducible fresh clone can differ from a long-running setup.

34d76fe/2266780/9c43680/9d04621 progressively refine acceptance honesty: parser success did not prove dispatcher behavior, bogus direction was accepted without windows, then actual nested-focus attempts disproved the proposed host-focus workaround. Scripts/documentation explicitly separate state transition evidence from tolerated call shape.18ff78f documents the actual Lua symlink activation boundary. a4df267 links motion curve tokens between compositor/widgets and changes follow_min_visible for continuous scroll; its literal speed-to-ms assertion is historical prose, not independently verified here.

**HIST-INF-001 — c2a history leak is not established by the removal subject.** afa82fa adds ignore/test/prose safeguards, but contains no c2a file deletion. `git log --all -- scripts/c2a` is empty and4,205rawfilepatchrecords contain no such path. Prose says it was committed; reachable rootGit evidence does not substantiate that statement. Current local credential-bearing helper was observed elsewhere by parent; no implication of absent secret exposure outside these reachableobjects is made. This is a provenance correction, not a credential rotation request.

## Current mechanisms become recoverable — medium patch slice

Full3cbe549,37bed45,3475df0,8d5c127,d6eae02,350daf5,9a37b27,2d7c7ef,94d329d,78b719f,2d543bd patches read.3cbe549 introduces explicit terminaltaste AGENTS, same modal search grammar across in-context menus, compact preview labels, reserved toast row, and window moves that retain source sessions by rescue shells. Source window indexes are re-resolved per move to survive renumbering. Its animation implementation is historical and then deleted by df47f6b.

37bed45 replaces guessed OpenCode flag mappings with recorded rejected flags/positional prompt behavior and gives402billing its own precedence rule above generic Claude auth. It explicitly documents own-permission bypass and deliberate metered-provider exception.3475df0 postpones credentials until tools are installed and reconstructs Fisher ownership records for vendored plugins, while using one D-Bus policy for read and write.8d5c127 responds to ABI soname drift despite unchanged Hyprland version by ldd checking, clean rebuild and atomic installed-plugin rename; running-loaded alone is insufficient for next-login persistence.

350daf5 changes socket existence to actual dial liveness before adopting sync and removes stale inode before spawn. d6eae02 follows with always-on polling under webhook because adopted process supervision is absent: recovery is layered beyond the one stale socket cause. Receipt event-loss gap W008 remains because polling cannot reconstruct those ephemeral events.9a37b27 corrects self-referential dead submodule revision to real SDDM upstream, removes unused network-manager gitlink, guards shell startup helper calls, stops alias -s dirtying repo every shell, and codifies Japanese login variant previously only root-owned live state.

2d7c7ef records stale-parsed Eww reloads and repairs one unmatched paren;94d329d moves application glyph mapping into adapter Python, because widgets lack reusable functions, and carries urgency by tint while reducing badge-reading cost.78b719f checks actual executable comm rather than command-line mentions before VPN state reporting and detaches confirmation loops to avoid blocking Eww.2d543bd adds explicit real-pointer selftest: hover is not button delivery; its source changesDND/brightness/silence/panels and is effectful, hence deliberately not run.

Latest exact checkpoint: 77 complete commits, 176 read file patches and 4029 pending of4,205records. Earlier checkpoint counts describe historical progress. No zero-new/complete-history claim.

## Exact new-file semantic representatives

Parent authorized reuse of full semantic source reads for new-file additions, with exact Git blob equality and addition path/mode context.340 additions first reconciled to this investigator's infrastructure/UI source reads; then all team's read ledgers were consulted. A record becomes read only when the current representative file still matches its ledger SHA256 and its Git blob hash equals the added historical blob. Unread/generated/asset-only representatives do not qualify. Modified files remain pending unless their actual delta was read. Every reused record names its source representative and ledger. This is semantic content reuse with verified identity, not equating a hash with understanding.

Reconciled checkpoint: {'read': 1490, 'pending': 2715}. Exact source representative additions make large initial commits partially read; no whole-history completion inferred.

## Exact deleted-source representatives

With parent authorization,691 deleted-file patches were reconciled to exact old Git blobs of fully read source representatives, after reading complete commit messages and deletion path/mode context. Most are671 ArchPilot snapshot deletions in4ebe9db: deliberate untracking of timestamped search-polluting local source copies, retaining the snapshot script and adding ignore policy. Other14 Fisher atomic-save leftovers in8b472de express mutableuniversalstate separation; remaining deletions belong to b4be38b,dc63810,c11d3bb,b8dbcad. Every ledger entry states representative and intent-review boundary. Modified blobs remain pending.

Latest reconciled counts: {'read': 2181, 'pending': 2024}.

## Asset/generated addition-deletion classification

Existing team asset-inspected/generated-classified representatives were similarly checked by currentSHA256 plus Gitblob and reused only for exact added/deletedobjects, preserving their original inspection/classification notes. This does not upgrade assets to semantic source or claim vendor/build internals read. Modified assets remain pending until their actual change is characterized.

Exact latest ledger counts: {'read': 2181, 'pending': 1628, 'asset-inspected': 394, 'generated-classified': 2}.

## Geometry and migration refinements

Complete afa8d01/38a1974 and all nonopencode files in773cc65/c0f3156 read. afa8d01 is the actual dispatcher repair patch behind later proof documentation: typed workspace/group/fullscreen/resize calls replace shell exec_raw, full direction names replace shorthand, mouse=true replaces drag=true.38a1974 removes all-window floating rules so scrolling has windows to arrange, preserving specific dialogs.773cc65 matches rounded cap foreground to each highlighted row fill, removes duplicate avatar-foot shapes, adds one-cell composer breathing gap and separates adjacent chip curves. c0f3156 makes optional steps follow selected groups and lets AUR install plan anticipate its own earlier helper bootstrap; whitespace-normalized copy comparison avoids churn when SwayNC strips one final newline. Font family correction follows actual fontconfig family rather than an assumed alias.

Latest ledger counts: {'read': 2199, 'pending': 1610, 'asset-inspected': 394, 'generated-classified': 2}.

## Small mutable-state/import slice

Pending portions of4ebe9db,ba89fd0,15f7f9d,cc24b7e,77593a9,e4c895e,eb61236,c96950e,6d0d7b1,1f82390,464e47e now read. Universal variable assignments were output by name/add-delete only, withholding values; mechanisms are shell path/plugin ownership/colour/keybinding state, not credentialvalue inspection. One attempted bulkshow accidentally included already-represented snapshot deletions and was truncated; those truncated bytes received no new coverage credit, and pending small paths were reread separately.

The tmux import1f82390 registers ten plugin gitlinks and makes visible config names absolute symlinks to dot-prefixed originals, documenting why current visible-vs-dot file architecture looks odd. cc24b7e had removed the old whole-tmux gitlink before this import.464e47e introduces START_TMUX opt-out and default-session attach; e313e0e later supplies a missing end. c96950e switches Eww includes from hard-codedhome to relativepaths, while mutableuniversal colour state shrinks. e4c895e removes leftover merge markers from a generatedorigpalette, replaces urgentworkspace hard-squarecorner with4px, and suppresses defaultGTKbuttondecoration. Firebase debug log here records documentation MCP tool discovery/scopes, with nocredentialvalue propagated.

Latest coverage counts: {'read': 2239, 'pending': 1570, 'asset-inspected': 394, 'generated-classified': 2}.

## Normalized generated palette deltas

79 modified palette files were classified generated-only after reading both complete Git blob byte streams and proving exact structural equality when replacing only hexadecimal colour literals. Paths were restricted to known wallust-generated colourhandoffs (eww/kitty/rofi/waybar/wlogout/GTK/Hypr); changed comments, keys, spacing or any noncolour structure prevent classification. Colour choices themselves are not claimed individually semantically reviewed. This preserves a truthful generated boundary and does not classify arbitrary authored source changes.

## Foundation and early widget lifecycle

Remaining e2639e6,cfd0768,ebf9a2a,a8e816d deltas fully read. WhatsApp begins as domain types plus a minimal printing entrypoint; thin lost-event-is-only-latency assumption is present from its original Event definition, preceding later richer receipt behavior. Test runner source explicitly combines formatting, vet, tests and build, and is effectful rather than an audit command. cfd0768 fixes header label ellipsis by xalign0/hexpand instead of halign sizing, prevents panel extending below the screen after Waybar exclusivezone, and changes media click to focus actual player. a8e816d adds ArchPilot as a streaming bar module with quiet/down vs human-neededapproval colours and machine-specific Fish source seam. ebf9a2a's atomicuniversalfileleftovers and generatedpalette deletion foreshadow later explicitignorepolicies.

Exact historical full-file addition/deletion patches now also serve as semantic representatives for identical added/deletedblobs elsewhere. Modified-diff-only records are excluded from this reuse because hunks do not constitute a full-file semantic representative. Every propagated entry cites prior fullfilepatch identity.

Latest exact counts: {'read': 2330, 'pending': 1412, 'generated-classified': 69, 'asset-inspected': 394}.

## Delegated reachable OpenCode history

History investigator completed the full six-commit reachable OpenCode delta chain and all746 treepath occurrences/unique prior manifest-panel versions. Root ledger reconciliation checks every old/new Git blob SHA256 against that investigator's git:blob:path records, retaining generatedlockfile and image-asset boundaries. This merges explicit semanticdelta review, not tree metadata alone. The relevant sixcommits are45d6fb8,934e50c,36f9346,773cc65,c0f3156,8b472de; some include nonOpenCode changes reviewed separately here.

Latest exact counts after delegated merge: {'read': 2464, 'pending': 1274, 'generated-classified': 70, 'asset-inspected': 397}.

## ArchPilot safety sweep and residual contracts

Full 47-file448486f patch read, including all376 test-diff lines. The sweep adds explicit IPC frame/type/size checks, restricts runtime file ownership and permissions, atomic persistence, surfaced daemon errors, restored sessions, Codex history, counted Vim editing, shell argument heuristics, Lua compositor dispatch and more precise tests. It corrects earlier false-positive tests (subscription used cmd instead of op; manual mode merely asserted non-plan; sandbox checked absence of bypass instead of presence). These are source assertions, not passing test results.

Defensive breadth still has ownership/identity limits: failure cleanup resets the full Git index (INF012), restore ordering activates current first then adopts others (INF016), and Codex filename fallback takes only the final hyphen segment (INF018). Runtime Hyprland kill/plugin and brightness mutations remain explicitly allowed as policy judgment, so the policy is not a strict read-only boundary. Patch intent and current behavior are distinguished.

Latest exact counts: {'read': 2511, 'pending': 1227, 'generated-classified': 70, 'asset-inspected': 397}.

## Picker persistence and one-paint opening

Full b253b95 and d3511bc patches read. b253b95 trades the persistent inline key panel for a help overlay and grants preview most vertical space, uses shared live palette resolution, preserves name-based session ordering and starts from actual attached session rather than stale view metadata. Its fuzzy overlay searches collapsed panes across all workspaces; acceptance highlights before normal Enter activates, a deliberate two-stage navigation contract. Escape parsing is restricted in dialogs so one cancellation cannot consume the next interaction.

d3511bc batches header/owner/popup tmux commands and stages initial curses output in anonymous memfd until the full screen is ready; PID readiness now follows paint. Tag state comes from the fully expanded tree rather than current collapsed/filtered rows, ancestor conflicts are pruned, workspace-level operations deduplicate owning sessions, and deletion preserves exact tagged object scope. New workspaces become metadata-only; rescue sessions are created only for deletion continuity. Batch validation precedes sequential mutation, not an atomic server transaction. Test source records preservation of unrelated pane/server identities but was not executed here.

Latest exact counts: {'read': 2527, 'pending': 1211, 'generated-classified': 70, 'asset-inspected': 397}.

## Native folders to custom tree, preserving running work

Full92c0e07/592fe52/0cf9078/76dddc9 patches read. The first wraps native choose-tree with stable folder IDs, name-based restored membership, origin-aware Archive, atomic fsync+rename JSON under flock and additive9271 hooks. Folder deletion archives running sessions; purge is distinct and rechecks attachment/membership after confirmation. Menus/popups intentionally launch outside waiting state locks.592fe52 separates workspace-local history from client-global history, persists exact window/pane reconnect focus, identifies server by boot/PID/starttime, and retries readiness for Resurrect. It preserves theme hooks and local/inherited pane borders.

0cf9078 introduces custom curses tree because centered hierarchy, guide and preview were explicitly chosen; native mode remains fallback. Destruction tokens include exact object scope plus pane PIDs, clients move to rescue before killing a final object, and detached callbacks use hook client context.76dddc9 then restores familiar native row accelerators, wrap/half-page controls, marks/filter/command-on-tags and non-disruptive colour/cursor-aware split previews. Its parser accepts SGR into curses attributes while ignoring nonprintable controls; it does not emit captured raw escapes as WhatsApp inline preview does (WUI003).

These patches make preservation of existing processes/server identity an explicit interaction contract. Historical test/deployment claims are not current rerun evidence. Later commits refine empty-workspace policy and replace earlier status/preview choices.

Latest exact counts: {'read': 2551, 'pending': 1187, 'generated-classified': 70, 'asset-inspected': 397}.

## Engine exception and consolidated contributor doctrine

Full remaining f6ec198/7307f6f deltas read. OpenCode is deliberately added as a metered-provider exception to the earlier subscription-only rule, with agent names standing in for the absent sandbox/gate and own permission configuration taking effect. Effort remains a UI chip with no actual CLI mapping. Provider session identity persists at adoption-time; history row/replay redaction is a display/cross-vendor seam and does not rewrite original stored prompts. Focused-terminal cwd becomes opt-in for new sessions.

The new contributor guide explicitly favors ambient desktop context, real resumable CLI sessions rather than a silo, quiet notifications, structural safety before heuristics/undo, and observed state changes over accepted syntax. It is historical prose with internal stale pockets (including old CLI flag acceptance and fixed bugs repeated in file map), so no fact here is upgraded solely because the guide says verified. Later source/deltas control current conclusions.

Latest exact counts: {'read': 2567, 'pending': 1171, 'generated-classified': 70, 'asset-inspected': 397}.

## Early portability and installation drift

Full pending deltas ofbbe41ed,148f03f,a609efb,3f4039d,a8e1c60,4dd25fc,95fb881 read; e54d7b1 source and identical-blob directory-rename context read, nine image containers verified by metadata/integrity only. That asset boundary does not claim aesthetic/screenshot understanding. Fish universal assignment values withheld entirely; variable names and ownership/environment mechanisms were reviewed.

The chronology shows migration from machine-specific /home/bu paths back to scriptkid and tilde targets, automatic tmux attach replacing the Zellij chooser, plugin auto-updates explicitly disabled while persistence plugins become active, and clipboard/vi/history defaults enabled. Early generatedorig files carried unresolved merge markers, later cleaned. Neovim formatting timeout shrinks and theme notices are suppressed in early history, while embedded ESP32 language support temporarily replaces clangd. a609efb increases lock grace from10 to900; this is historical source, not proof of current exposure.95fb881 adds an explicit --run gate to remote SDDM installer and reachability tests because documented shell names had drifted from installed names. Its loose subcommand test checks token mention, so it cannot prove dispatch reachability (current INF007).

Refreshed all-team exact full-content representatives accounted for39 additional addition/deletion records (37semantic,2generated) after validating recordedSHA256/Gitblob identity; nested-repository blobs absent from root object DB were skipped. Modified deltas still require actual read.

Latest exact counts: {'read': 2650, 'pending': 1068, 'generated-classified': 72, 'asset-inspected': 415}.

## UI acceptance corrections in historical deltas

Fulla463517/259a52d/b179e9e/19065d3 pending deltas read. a463517 introduces explicit panel-open flags to gate polling and replaces network percentage with throughput/graph; later source resolves architecture.259a52d untracks palette/TPM log artifacts and separates fixed icon/number widths from expanding sliders. b179e9e moves calendar/city/VPN input to Rofi because layer exclusive keyboard capture is unacceptable, preserves masking for secret-shaped keys, and narrows selftest unsilence assertion to its own named app rather than requiring the user global rule list empty.

19065d3 is an instructive abandoned direction: it moves onclick from GtkButton to wrapping eventbox throughout widgets. Later actual-input proofs reverse this because GtkButton consumes the event, while hover still works. This patch is not evidence that eventbox clicks work; it documents exactly why visual/hover-only verification is insufficient. Source current behavior was reviewed separately. One initial four-commit output exceeded tool limits; only complete visible a463517 received credit until other commits were reread individually in bounded chunks.

Latest exact counts: {'read': 2689, 'pending': 1029, 'generated-classified': 72, 'asset-inspected': 415}.

## Revert evidence and discarded build experiment

20f7434 explicitly reverses19065d3 after real pointer evidence: wrapping-eventbox over plain box fires, wrapping-eventbox over GtkButton does not, GtkButton own onclick fires. Every eight pending path/mode/blob pair is exactly the inverse of the fully read prior delta; no approximation used. Other tool additions already had full source representatives. ff6e13f deletes the Zen hello-world build experiment, its cache manifests and ELF/object artifacts while temporarily reducing install to reload-only. Source/manifests read; historical compiled objects only header-classified as generated, not decompiled.

Latest exact counts: {'read': 2703, 'pending': 1010, 'generated-classified': 77, 'asset-inspected': 415}.

## Legibility and correct identity

Full43741bb/1a13360 pending deltas read.43741bb distinguishes rounded control fill from label-only text styling, so universal direct label rules no longer produce square hover fills; initial poll records gain every typed field, unsupported widget attributes are removed.1a13360 makes launcher surface opaque explicitly because dense word lists need legibility despite keeping glass on shape/number panels; removes redundant notification card outer surfaces/media placeholder, routes screenshot through the common clipboard/history/OCR wrapper, removes inactive-layout bindings, and matches saved Wi-Fi by carried SSID rather than profile display name. It pairs/trusts Bluetooth in the bare CLI route, but current panel adapter still bypasses that path (INF008). Historical emitter deletion leaves residual MPRIS declarations without selector; current implementation was reviewed separately by desktop investigator.

HIST-INF001 provenance enhancement: parent discovered a pre-rewrite bundle with original c2a credential-shaped helper/removal, while current rewritten reachable history lacks that path. See pre-rewrite-history.md and exact-diff map. Thus earlier conclusion is specifically current rewritten reachable history; original bundle establishes older provenance without reproducing values here.

Latest exact counts: {'read': 2722, 'pending': 991, 'generated-classified': 77, 'asset-inspected': 415}.

## Immediate feedback, historical adapter fork and visible settings

Full2c4f038/a1be271 deltas read.2c4f038 adds busy markers and immediate push after networking operations because a stale connected row invites an opposite second click; MPRIS metadata persists the paused state after PipeWire stream disappears. This is also the precise fork introducing current INF008: UI adapter waits on raw bluetoothctl connect, while later1a13360 improves the separate CLI pairing route only. a1be271 makes notification settings show DND/silenced state, adds one segmented VPN control instead of three independent wells, preserves neighboring calendar month cells, and exports zero-padded date data from backend to avoid widget binding complexity. It still uses reversed swaync enable flags historically, corrected later.

Latest exact counts: {'read': 2738, 'pending': 975, 'generated-classified': 77, 'asset-inspected': 415}.

## Fresh-install contracts and visual restraint

Full pending9c246b7/fbfe6ee deltas read.9c246b7 explicitly audits invoked commands against provisioned packages: polkit agent liveness uses truncated kernel comm, audio recording takes one PulseAudio source name rather than multiple wpctl object IDs, cancelled region selection is explicit, night light detaches before Eww update, and AUR bootstrap precedes AUR package phase. Catalogue checks catch ignored-but-required link sources. The changed autostart still has separate status-only lifecycle limits documented currently as INF002.

fbfe6ee narrows the panel, removes nested row-as-card decoration and empty sections, consolidates notification glyph ownership, treats durations as one segmented choice, and reserves tinted urgency for critical cards. The rationale is hierarchy/legibility and scarce attention, not decoration everywhere.3d195bc non-cache source deltas read; exact Zen source/manifests/artifacts reuse the full reads/generated classification from deletion ff6e13f, retaining binary boundary.

Latest exact counts: {'read': 2774, 'pending': 934, 'generated-classified': 82, 'asset-inspected': 415}.

## Registry seam, bus ownership and panel separation

Full pendingdd40f9c/95212aa/c3277ec/35de0bc deltas read. dd40f9c makes action names the shared keymap/validation/help seam and rejects nil handlers at startup; lock source was independently represented, with explicit UI-only rather than encrypted-store boundary.95212aa routes DND by actual D-Bus notification owner rather than installed binary and fixes inverted enable flags; an initial polling snapshot replaces startup-empty subscribe streams, while zero volume is visually silent even without mute flag.

c3277ec introduces detached handlers for the Eww callback/wait cycle and credential field helper, but deletes ts-exit/ts-dns/ts-routes dispatch while widgets remain: exact origin of current INF007. Its initial path-only privileged helper permits arbitrary new keys; later security patch adds per-key constraints.35de0bc replaces placeholder audio/network panels, keeps frequent sliders in control center and occasional device/app detail behind bar icons, centralizes includes to avoid duplicate textual splice, labels quick actions to avoid memorization, and removes clipped outer shadow because compositor blur already separates the panel.

Latest exact counts: {'read': 2811, 'pending': 897, 'generated-classified': 82, 'asset-inspected': 415}.

## Credential input lifecycle

Full14c7f15 pending deltas read value-free. It separates typed secret questions from ordinary exported answers, sends apply values through stdin, masks rendered text, adds missing/newline handling and explicit optional pairing. Initial sequencing applies secrets before package installation, later corrected by3475df0 so storage tools exist. Initial free-text handler also follows j/k navigation, explaining current input-key conflict. Commit prose about no command-line exposure is stronger than the original apply implementation: stdin reaches a shell that expands value into child Fish command text, later hardened source must be considered. Filename/pattern tests cover selected shapes and a2MB cutoff, not a universal guarantee of no credentials.

Latest exact counts: {'read': 2820, 'pending': 888, 'generated-classified': 82, 'asset-inspected': 415}.

## Sticky state and generated RGB palette boundary

934e50c remaining15 nonOpenCode deltas fully read; OpenCode delta chain delegated earlier. Fullscreen exclusion is removed because static tags outlive matched fullscreen state; root-owned wallust copy avoids installing a system command pointing into user-writeable home. Fish guard form changes were historical response to reported status mismatch, not rerun here.

Conservative normalized-generated proof extended to known theme emitter outputs: complete old/new bytes must match exactly after replacing only hex colour literals, Hypr RGB hex literals and RGB triplets in rgb/rgba functions. Alpha values, roles, comments, whitespace, layout and arbitrary numbers remain exact. 37 additional deltas classified generated-only; no claim to individual palette interpretation.

Latest exact counts: {'read': 2835, 'generated-classified': 119, 'pending': 836, 'asset-inspected': 415}.

## Progressive feedback and abandoned broad styling edits

Full pending791b05e/e1440be/b0915b5 deltas read.791b05e separates secret presence boolean from withheld secret value, reports VPN on/off rather than section name, aligns unique selection tick at trailing edge, and combines wrap with disabled ellipsize. e1440be is another failed/intermediate direction: calendar prebuilds every day pane to avoid handler lookups, blanket focus-ring removal misattributes label square fills, and a broad stylesheet edit deletes quick-action/app/busy/now-playing styles. Later b0915b5 restores single selected-day backend data, removes Eww get roundtrips by passing known month as argument, hides absent media through empty/singleton rendering, enlarges slider targets/endpoint clearance, makes tooltips opaque over arbitrary content, and uses one recognizable privileged prompt. Silent DND changes deliberately produce no self-defeating notification.

Current missing busy/now-playing selectors were sent to desktop investigator for cross-check; historical accidental deletion alone is not accepted as current visual proof.

Latest exact counts: {'read': 2867, 'generated-classified': 119, 'pending': 804, 'asset-inspected': 415}.

## Cost-aware telemetry and reload architecture

Full pendingb4be38b/875469e deltas read. Throughput becomes counter delta over actual elapsed interval with interface/reset guards; no sleep inside an already periodic poll, both RX/TX, rate gets a time graph rather than a percentage gauge. Brightness is deliberately removed from selftest because passing should not interrupt the real display. Workspace-disc fixes use measured fill rather than nominal minimum box dimensions. Container depth and control flatness are different visual roles.

875469e fans out independent consumer reloads only after all theme outputs exist, bounds Waybar wait by observed process exit, uses thumbnail palette extraction before configured-backend fallback, and trades very small speed wins against failure coverage. Wi-Fi signal/security share one leading glyph; unique active tick moves to trailing edge, Bluetooth variable-width device glyphs get fixed badges to align names. Historical performance numbers are not current measurements.

Latest exact counts: {'read': 2882, 'generated-classified': 119, 'pending': 789, 'asset-inspected': 415}.

## Migration proof limits

165428f remaining eight Lua-migration deltas fully read. Same modular split preserves comments and design intent; generated colours cross format boundary from shared tokens, repeated layer rules become one namespace table, content remains opaque while chrome owns translucency. The initial source assumes exec_raw can dispatch old dispatcher strings, short focus directions and drag flag forms; later afa8d01 proves/fixes those contracts. --verify-config is explicitly observed to execute autostart commands, so parsing/validation was not side-effect-free or sufficient behavior proof. The initial all-floating catchall also temporarily defeats tiling and affects screenshot overlay; later removals already read.

Latest exact counts: {'read': 2890, 'generated-classified': 119, 'pending': 781, 'asset-inspected': 415}.

## Early multiplexer consolidation

8ee41e1 remaining14 source deltas read, including full520-line removed Zellij configuration (modal vi/tmux mappings, plugin aliases and commented serialization/clipboard/web-sharing options). It follows automatic tmux attach by removing the alternative config, sets Fish as default shell/command, starts a minimal ignore policy for mutable universals/plugin trees, and changes monitor matching from DP-1 to any preferred output. Portability is uneven: some paths become HOME-relative while launcher/GTK target switch to another hard-coded user. Wallpaper fallback redirects cat output to /dev/null, so a readable cache yields an empty chosen path; later wallpaper lifecycle source determines current behavior.18 exact image-blob addition/deletion entries were linked to prior verified image-container representatives, retaining metadata-only inspection.

Latest exact counts: {'read': 2904, 'generated-classified': 119, 'pending': 749, 'asset-inspected': 433}.

## Notification backend migration

9b9edf4 remaining13 pending deltas fully read in bounded chunks. SwayNC provides explicit expandable actions; history recorder stays independent of notification daemon and survives replacement. Initial timed quiet uses transient user timers with expiry fallback after reboot, distinguishes muted from ignored apps, and expands actions to avoid repeated dismiss misclicks. Initial state writes and timer ownership are not transactional; initial application picker slices the selected label incorrectly, later corrected by b0915b5. Initial DND flags/subscription startup issues are corrected by95212aa. Missing-binary exceptions escape check=False but outer wrappers catch them. The197-line initial emitter establishes glass/card typography, action layout and DND/MPRIS integration; critical-card styling is later restrained.

Latest exact counts: {'read': 2917, 'generated-classified': 119, 'pending': 736, 'asset-inspected': 433}.

## Early integration before shared lifecycle

e0442b1 remaining18 source deltas read completely. Explicit Kitty socket makes editor padding wrappers tolerant of absent remote control, while plain tmux converges on one default session. Wallpaper starts from cached last choice with a daemon-start race rather than readiness handshake. Recording assumes a shell-visible find_internal_audio command. A compositor passthrough submap provides an escape from global bindings, and animations move into a module; large inherited example comments disappear. Editor SQL plugin addition accompanies extensive whitespace-only reformat, all read. Bar moves to bottom layer, circles become expanding active workspace pills, and audio gains an embedded drawer/slider. These are historical contracts, not live acceptance.

## Strudel notification suppression origin

7dc1d4e six pending source deltas fully read (847 patch lines). Filetype and write-triggered live update add Strudel workflow; remap/AI terminal code is extensively reformatted while preserving shell-string construction and terminal-state behavior. The new init.lua vim.notify replacement returns a no-op for every filetype, and the plugin wrapper captures that stub as real_notify, so its apparent targeted Strudel filter cannot restore other notifications. This is historical provenance; current source was separately repaired/reviewed by desktop owner.

## Calendar interaction grammar

c4d3a5b remaining eight deltas fully read: date half opens month/picker/day while time half opens world clocks, so triggers have distinct meaning and clocks no longer fall below expanding plans. Notes describe a day; checkbox plans require action. Sending a plan appends existing sticky-board syntax, avoiding another task store. Separate ring/fill/dots encode today/selection/pending/note with more than color alone. Backend emits picker rows because widget flat iteration and narrow year cells are unsuitable; explicit selector order keeps current-year text visible when selected. Polls run only while clock is open. Historical push-board reports success even if nonexistent target causes silent backend return; not exercised.

## Network identity and detail

f2661a1 nine pending deltas fully read. Pane navigation replaces expanding dropdowns to keep long lists within usable height. Security generation and band add useful state rather than generic locked status; MAC/channel remain detail. VPN profiles label tailnet rather than account because one account has several networks; absent backends remain visible but disabled. Initial VPN controls route through adapter and backend, later c3277ec dispatch deletion explains current INF007. Wi-Fi Python parser preserves escaped colons; its initial band condition makes6G unreachable and compares profile name to SSID (INF009). Historical QR construction interpolates raw SSID/password without WIFI URI escaping and retains temporary image, a contract separate from availability. No network/secret actions invoked.

## Earliest baseline

de2ee63 remaining21 initial source additions fully read, including inherited compositor examples and terminal mappings. Universal Fish variable values deliberately withheld; names/export/path mechanisms reviewed. The baseline combines manual swww and hyprpaper startup, independent daemon launch without readiness, broad global binding duplication (SUPER+M both exit and music), and wallpaper-driven Wallust outputs with hard-coded home paths. setwall fans reloads before lifecycle ownership was centralized, and pkill-waybar success gates restart. Terminal has extensive native tabs/layout mappings before tmux consolidation. aiman sends up to three400-line man pages to an external ai command with a source-only answer instruction. This establishes organic manual integration before later shared registry/theme/service contracts.

## Rofi expansion and inherited assets

042a3cd remaining15 source and16 image additions/deletions reviewed. Entire inherited configuration/styles read: normal tokenized matching, filebrowser/history, alternate Alt navigation, full-screen app icon grids tied to screen resolution, selected states and per-family imports. Some families use generated Wallust colors while applets/powermenus still import onedark; shared inheritance is not uniform. Earlier minimal theme and wallpaper-picker script are deleted.16 image containers passed format/dimension/mode and integrity checks (PNG/JPEG,520x155 through3000x3000); no aesthetic or screenshot-content understanding is inferred.

## Generated-state untracking and upstream tmux boundary

e5d98a1 remaining11 deltas fully read/structurally inspected, including442-line upstream README and189-line install shell; originals include unresolved conflict markers, removed rather than silently interpreted as a palette. Ignore rules expand from Fish universals/plugin contents to generated colors, originals and logs. Upstream tmux install supports backups and dry-run flags but still creates the XDG directory outside the dry-run guard; it is historical untracked tooling, not current project installer acceptance. README explicitly separates stock core from local customization and built-in TPM loading. Two SVG logos fully structurally inspected, no rendered visual claim. Exact old/new whole-file representatives also cover matching historical additions.

 f46a470 final pending509-line upstream local config fully read: preserves custom rather than stock bindings, retains pane path but not new window/session paths, advertises SSH reconnect optional, clipboard copying off, automatic plugin update and uninstall on. Later owned config disables automatic updates; this is a conscious divergence from inherited defaults. Commented network status helper examples remain inactive data, not invoked checks.

## Shared restyle patch checkpoint (dc63810 partial)

21 pending file deltas of dc63810 now fully read beyond its earlier exact representatives/assets: ignore/default contract, Thunar conflict cleanup, ArchPilot theme mapping/fallback, Cava, Eww shared SCSS/toggle/state/audio/network/shortcuts, compositor/Qt/Kitty/Mako and wallpaper scripts. Shared package owns arithmetic while each app owns placement; broken shared package falls back so the diagnostic interface still renders. Top-level outer shadows are removed because compositor owns external depth. Content keeps opaque text; chrome background alpha and namespace blur provide depth, with xray off and ignore-alpha thresholds to avoid broad ghost bands. Aggregated polls and visible-only device lists reduce process cost; mute and silent are distinct control/state concepts. Initial command lifecycle still assumes fixed daemon sleeps and suppresses many reload failures; later history already read improves fanout/readiness. Remaining dc63810 entries still pending, no whole-commit claim.

## Shared restyle patch complete

All remaining dc63810 deltas now read, including374-line initial usage guide,322-line bindings, every initial token output, tmux integration and515-line CSS migrations. Prefix is made immediate by disabling the script-intercepting transient status plugin; plain C-b reveals an otherwise quiet bar. Status variants need ordered application after the upstream asynchronous theme marker, with bounded wait. Generated tmux variables are spliced into the same file because shell/tmux scopes do not cross the source boundary as assumed. Numeric palette roles and alpha/type/motion tokens were all actually read in this initial version; later palette-only normalizations retain that semantic boundary. Waybar stylesheet becomes a thin token/variant loader; wlogout moves geometry to launcher and treats glyph plus fill as separate background layers, with destructive shutdown red. Initial cheat sheet is historical usage prose, not acceptance proof: count69 differs commit74; old Mako/no-root/snapshot coverage claims must be reconciled with current source findings. Two nested gitlinks are pointer changes; this does not certify arbitrary upstream histories.

## Abandoned GPT/learning examples (c11d3bb partial)

32 deleted GPT/learning example files fully read in972 patch lines. GPT has explicit popup helpers and visibility-gated polls but most data/visibility wiring is commented out, its top-level include is commented, and snippets retain unresolved AI citation placeholders. Shell JSON interpolation and naive nmcli colon splitting undermine claimed escaped handling; base64 is used only for passing Wi-Fi names downstream, not encryption. Cava child lifetime relies on broken-pipe behavior. Learning sample appends to a hard-coded test file and tails it through state/xargs; it is experimentation, not a product contract. These entire deleted blobs also provide exact content representatives for matching prior additions; remaining Cyber examples still pending.

Cyber script subset (16 files,1022 patch lines) now read: custom fixed theme paths and monitor-index startup, direct generated Yuck from active-window/notification metadata, MPD/MPRIS adapters and album-art temp files, ALSA-specific volume, per-weather cache files and credential-bearing OpenWeather request mechanism, fixed workspace icon state from socket events. Several commands are hard-coded to another theme or obsolete dependencies; emitted strings are not escaped for Yuck and lyric text is used as printf format. Weather fallback typo targets an unset cache variable. These are removed inherited examples, not currently reachable production problems. Root setwall duplicate is removed while scripts/setwall receives its GTK hook and historical wlgout typo.

Cyber example closure: remaining full631-line SCSS,519-line main Yuck,62-line notification panel,281-line sidebar and232-line system menu read; Thunar126-line initial accelerator dump read. Visual grammar is inherited Lovelace-like multicolor hardware modules and hover slide-outs rather than later restrained shared tokens. Hard-coded BAT0/Nvidia/ALSA, three fixed monitor windows and missing referenced helper scripts make these prototypes machine-specific. Notification clear restarts Dunst, unlike later independent recorder ownership. Five deleted image/icon containers verified as metadata/integrity only. c11d3bb all entries now covered; exact matching whole-file historical additions inherit only the corresponding semantic/asset coverage, not visual acceptance.

f0d189a all remaining source deltas except6257-line inherited sweet.css read. This is Qt QFA typo origin (laterQPA corrected), early fullbar-to-capsule restyle, wallpaper-derived GTK role expansion and portal dialog rules. Generic opacity still affects all content with browser exceptions; later shared restyle removes it. Fish export names/flags reviewed with universal values withheld. New SDDM gitlink is pointer provenance only; upstream history belongs its separate inventory. sweet.css remains explicitly pending unless exact fully read representative is confirmed.

Sweet baseline reconciled: desktop owner fully read current6252-line source (SHA25684c6c0c02dd635b5ed06213febf315bfbeb3b1354a665f0a80210a6328a8077b); complete historical delta is only missing import semicolon plus two opening banner comments. Read this entire delta and independently verified exact byte replacement produces current bytes. Historical6257-line source understanding is represented by full current semantic read plus complete delta, not file hashing alone. f0d189a now fully covered.

## Jan2 authored panel integration

b8dbcad remaining35 deltas now fully read, including initial Eww section/poll/widget scaffolding and874-line other configuration delta. Hardware assumptions predate later fixes: CPU multiplied100 despite percentage source, network throughput rendered as percentage gauge, mute glyphs decorative, WLAN interface fixed. Idle source and startup both explicitly disabled; no conclusion about current locking follows from that old edit. Global content opacity originates here, later removed. Editor adds CSS/SCSS/Rust tooling to edit the rice; blackwallcss filetype may separate CSS tooling despite parser registration. Waybar modules replace monolithic config and Wlogout becomes six direct power actions; CSS still has duplicate background declarations and hard-coded geometry before later fixes. Kickstart upstream license,241-line README and help read as deleted source, including lazy installation/network behavior and isolated NVIM_APPNAME guidance; none executed.

## First editor/shell import complete

3ea80d8 all remaining31 deltas read. Original Fish chooser mistakenly prompts noninteractive shells (latere044 corrects), while man-source answers and local Ollama bridge precede ArchPilot. Direct Kitty padding reset lacks remote error handling until later wrapper change. Initial editor is768-line Kickstart-derived plugin bootstrap plus local language/remap/theme modules. Startup may clone Lazy, build native extensions and install Mason/parser tools, explaining why audit never launches it. Completion uses Bun dynamic introspection/history with global helper names. Theme preview polls30ms and persists selected theme into tracked config; cancellation restores prior theme. OpenCode terminal path constructs double-quoted shell command text directly from file/selection/query content and reuses channel input; current desktop audit, not historical comments, governs risk status. Custom remaps can overwrite early baseline leader diagnostics mappings. Original private-scope VSCode notify stub differs later unconditional suppression. Entire initial Lua config plus all helper source read; no plugin operations executed.

## WhatsApp palette contract

81e5772 remaining six deltas fully read. One shared theme target emits opaque colors because terminal already composites background; named styles own palette usage, and monotonic generation invalidates render caches. Missing palette supports standalone binary via embedded fallback; malformed present file reports a useful error and partial palettes inherit defaults. Initial TestGeneratedPaletteLoads does not prove emitter output exists because missing file returns fallback, so a missing generated target can pass. Manifest/sum changes read as dependency declarations; no vendored source understanding inferred.

## WhatsApp subprocess seam

c786820 remaining four deltas fully read (783 lines). Typed client centralizes argv construction, account/store flags, timeouts, JSON envelopes and prose-error classification. Store writes delegate through wacli rather than opening its writable database. send mutex prevents overlap but does not itself promise goroutine arrival/FIFO order; test proves alternating starts/ends, not message order. No lock-wait follows measured historical delegation delay; doctor lock contention is explicitly warned against. Fake harness builds a Go binary and logs invocation boundaries, so even unit tests have build effects (not executed). Initial timeout/generic error includes full argv and therefore sent text; current W006 owns downstream handling. Missing binary errors fall back to exec text, while malformed JSON and canceled contexts retain separate limits.

## WhatsApp configuration foundation

7f11741 remaining six deltas fully read (813 lines). Embedded defaults are a single source, scalar overlays preserve missing values and explicit per-mode map merge lets empty strings disable bindings. Unknown config keys warn while malformed syntax and unknown action names reject; grammar target validity belongs modal engine. Setting reflection parses scalar types but initially does not constrain enum/range/duration semantics. Separate override file prevents TOML duplicate-table append and avoids dirtying a symlinked tracked base config. Defaults expose keyboard-first vi grammar, independent UI-only lock and background sync configuration; lock encryption boundary is explicit. Pinning fsnotify1.7 targets Go1.22 portability; this is historical declared support, not current host acceptance.

## Hot reload and terminal geometry correction

ef68286 thirteen pending deltas fully read. Previous config watcher callback did nothing; a coalescing reload channel now feeds actual app reload and watches base/overrides/theme plus palette files, directory-based for atomic saves. Missing directories are skipped permanently and arbitrary configured theme paths are not added dynamically; current contract audit distinguishes these limits. Go requirement rises1.22→1.25 with SQLite1.34.5→1.59 dependency update; suspected WAL issue in commit prose remains historical diagnostic hypothesis here. Multirow pill glyph/font seam motivates flat cards, extra vertical padding and matching hit/height calculations; one-line capsule survives and timestamp always floats beneath. ASCII-only circled avatar glyph fallback is explicit. Which-key root becomes paged list, preserving full labels rather than forcing truncated columns. Added tests describe these shapes; no visual or test execution performed.

## First runnable WhatsApp packaging

e53f170 thirteen pending deltas fully read (1372 lines). Compiled wa uses Make install rather than script symlink, preserves existing config, and documents external sync ownership/poll fallback and UI-only lock. Startup performs filesystem setup/open before preflight but enters alternate screen only afterwards; doctor shares setup, so it is not an inert parser. SIGHUP/CtrlC/TERM route cleanup to owned sync. Original hot-reload callback is actually empty despite guide claiming automatic reload (lateref68286 fixes). Batched terminal runes now traverse keys sequentially and queue tea commands; quit supersedes queued batch, matching later WUI005. Chat names coalesce chat/group/full-name/push-name/alias instead of raw JIDs. XDG documentation says overrides are state-local, actual helper places overrides in config directory. run-tests grep checks documentation/install target existence and default-byte equality, not end-to-end installability; no tests/builds run. Historical live-account acceptance prose is retained as old claim, not newly reproduced.

## WhatsApp renderer foundation

9742ed5 remaining ten deltas fully read (1400 lines), including all40/80/120-column textual goldens. Renderer is pure domain→terminal rows with row-to-message tags; grapheme segmentation and display-cell width avoid splitting emoji/CJK, media/quote/deleted placeholders wrap as body and footer space is reserved before measuring box. Fixed clock makes golden layouts stable. Initial ANSI parser skips to alphabetic byte and is not an escape sanitizer, while body wrapping has no trust boundary. Initial LRU keys ID/size/generation/revision, omitting chat/time/sender/direction: current WUI008 has this historical origin. Tests cover simple width/cache/delivery cases; receipt assertion in colorless mode depends on glyphs, not color-only distinction. Existing full render tests/goldens are source evidence, not newly passed runtime verification.

## Sync ownership and lossy-event assumption

bda1b49 seven remaining deltas fully read (1493 lines). Readiness uses delegation socket rather than connected event; doctor polling is avoided because it contests the actual store lock. Ownership modes distinguish spawned/adopted/external/poll/off, while only spawned child receives stop signals. Initial restart/state-error paths can leave child lifecycle gaps and initial Stop races cmd.Wait with Process.Wait; current parent source report owns corrected/remaining status. Private atomically replaced state carries PID/port/HMAC but PID liveness alone is not identity. Webhook binds loopback, verifies HMAC, caps reads, converts unknown payloads into invalidation and deliberately drops oldest under burst. Prose says loss only costs latency, but this assumes every event is reconstructible from SQLite: later receipt history is not, matching W008. Poll detects growth/max timestamp rather than every mutation, and concrete Close leaves channels open despite Source comment promising closure. Tests spawn sleep or loopback listeners if run, so no execution was performed.

## Modal engine provenance

258f312 five pending deltas fully read (1596 lines). Domain-independent engine emits Resolved action/motion/operator values; unified per-mode trie sees mixed action/motion prefixes, supports timeout ambiguity, count multiplication, register/character arguments and macro recording. Linear undo rationale is ephemeral chat draft, not file history. Macro implementation feeds every recorded key and returns one collected result batch before caller applies mode-changing actions: using same Feed path does not guarantee replay equivalence when caller feedback changes mode between keys. This is current W013 origin; initial tests only replay mode-preserving word deletion, so do not cover insert/change macros. Dot stores resolved edit rather than full insertion history. Keyscript miniature checks useful operator/buffer behavior but its separate apply dispatcher remains a test abstraction, not full UI end-to-end proof. Unbind leaves trie nodes, so prefix existence means structure, not necessarily a remaining bound descendant.

## Store fast-path foundation

a34fb18 eight remaining deltas fully read (1840 lines). SQLite read side avoids per-keystroke CLI startup, uses mode=ro and parameterized composite timestamp/rowid keyset cursors; schema fallback preserves a shared Reader interface, with visible degradation. CLI fallback has only timestamp cursors and omits some direct-reader filters, so interface satisfaction does not prove semantic equivalence. Initial Chats query appends an unparenthesized name-or-JID search expression after other AND filters, allowing the JID branch past archive/group predicates; current parent store review owns present status. Fixture older-schema tests merely insert fewer migration rows into current DDL, so acceptance of a genuinely older physical schema is not established by that test. Receipt values are synthesized Sent/Read from direction, reinforcing that live finer-grained receipts cannot be recovered by rereading this initial store. Tests use real temporary SQLite and build a fake CLI; none were executed.

## Conversation identity and draft intent

996835c six remaining deltas fully read (2362 lines). Selection follows JID/message ID as rows reorder or prepend; clamped navigation intentionally avoids list wrap, while search wraps matches. Hybrid absolute/relative gutter explicitly mirrors the owner Neovim habit. Per-chat buffers and undo reset after Take prevent resurrecting already-sent text. Optimistic sending reflects the measured historical delegation delay claim (not newly measured), with failure kept visibly. Initial Restore operates on current draft rather than captured chat, current WUI001 provenance; unit test restores without changing chats. Numeric search indexes survive prepend/refresh, WUI014 origin. Initial Refresh keeps older messages by strict timestamp and can regress receipt state on newly fetched Sent values; current source review owns present behavior. Fake-store tests omit real CLI timestamp boundary semantics and asynchronous cross-chat completion, so interface/test count does not establish those contracts.

## Root interaction architecture provenance

8055ffb fourteen remaining deltas fully read (4186 lines). One registry joins binding validation, discoverable actions and runtime dispatch. Two-stage Esc preserves normal-mode editing before returning to conversation; opening on list movement aims to feel like reading, while ambiguous names produce a picker rather than guessing. Predictable subsequence matching deliberately avoids fuzzy score ranking. Reversible chat flags use an inverse ring; sends/retractions are excluded from ordinary undo and revoke remains explicit. Current caveats already reported have origins here: applyConfig rebuilds engine/registers (WUI010), loadInitial mutates model from asynchronous Cmd (WUI015), timeout bypasses lock routing and discards commands (WUI011), jump navigation calls openChat which pushes and truncates history (WUI009), send failures restore current draft (WUI001). Initial action picker returns nil command after callback, so command queue semantics need explicit collection. Event prose treats every event as reconstructible hint despite receipts being finer than stored direction (W008). Historical test feed runs HandleKey directly and does not recursively dispatch BatchMsg, so its comment asserting event-loop equivalence exceeds its implementation. No tests executed.

## In-progress historical frontier

Original canonical scope remains 188 reachable commits at ccb0b49195cfcd4fc11ea86cb15294e603e2a753; parent owns newer concurrent browser commits 039deb4/8653401. Ledger has 206 pending paths across b98567d (72) and 8b472de (134). b98567d full pending-path patch has 10371 lines; lines 1–5500 have now been read in contiguous 500-line chunks, with remainder pending. This partial read is not yet positive file coverage. Initial installer claims checksum-required but actually warns and installs without checksum file; Go tarball path removes old installation before extracting unchecked download, and --check exits zero even when prerequisites absent. Current parent installer report owns present status. Corrected CLI JSON fixture explicitly documents that original invented snake_case test hid decoding failure, useful evidence against treating prior tests as production acceptance. Store identity adds canonical PN vs stored LID and advisory sent-quote memory. Initial media batch clears files/reply before async completion and failure only returns caption (WUI002 origin). Historical lock-stop test drops its fake socket within the work callback, so absence then does not independently prove pre-work lock release.

## Rich-message integration patch closed

b98567d all72 remaining paths now closed after contiguous full10371-line read (supersedes partial frontier above). Module moves blackwall→dotfiles, shipped config becomes an example so defaults can evolve, aliases keep renamed actions startup-compatible, and header/focus markers separate account/open conversation/keyboard focus. Rich media, replies, reactions, per-draft attachments, mouse selection and modal menus enter together. Frame-based copying deliberately includes visible gutter/time text; scroll wheel moves viewport without changing selected conversation. Half-block edges and grapheme widths reflect deliberate terminal aesthetics, with color-specific tests separate from text goldens.

Source origins of remaining UI gaps: menu overlays after locked frame (WUI006); layout omits link crumb while drawing subtracts it and quickfix SelectRow substitutes click row for actual viewport height (WUI007); download-on-open queues async fetch then immediately checks path (WUI012); bulk cancellation breaks without counting unattempted files and can report them downloaded (WUI013). Async sends clear attachments/reply before success (WUI002), and failures have no captured chat. New tests now follow returned commands but still do not recursively dispatch BatchMsg, while mouse press helpers discard returned Cmd except picker helper. Help overlay now owns dismissal instead of leaking underlying engine bindings. Contract tests inspect real CLI help if installed and skip otherwise; they hardcode expected calls rather than derive all actual callsites, and establish argument availability, not live action success. No archived commands, tests, helpers or openers executed.

## Final original-scope commit checkpoint

8b472de original134-path pending patch is18438 lines. Original lines1–3355 fully read:39 paths closed, including credential-bearing Fish state only by value-free variable-name/mechanism inspection, values deliberately withheld. Ten full additions (six installer files, autostart, WA mix/pill-tests/whichkey) closed with positively reviewed current SHA256 baselines plus the complete1443-line historical-to-current semantic diff, all four chunks read and baseline hashes reverified afterward. This does not assert old and current blobs are identical. Remaining85 modified paths pending; next packet is git show of those latest-pending paths only, starting line1. Historical intent: installer expands from reload script to explicit plan, local overrides and guarded restore; generated design rules unify body/UI/mono/icon faces, inset rims and 20px panel gutter. Older cheatsheet retains conflicting autostart/no-auto-media prose, so is not source truth. Codex integration retains separate transcripts and bounded replay; its no-hook sandbox distinction is a declared adapter contract, not proof every CLI version honors every flag.

8b472de narrowed85-path packet lines1–1800 read; every complete delta before README (through1775) now closed. The25-line opening of WhatsApp README is partial only and will be reread from that path in the next narrowed packet. Desktop theme changes include point/pixel type alignment, translucent launcher return after hyprglass contrast handling, shared gaps and inset rings, global GTK3 menu exception, removed duplicate CSS and repaired swaync missing selector/function interpolation. Script deltas include OCR omitting image clipboard write, multiple preprocessed tesseract attempts selected by alphanumeric length, one-capture ArchPilot staging and notification action progress. This is historical source reasoning, not live screenshot/clipboard proof.


Checkpoint: original 58-path 8b472de packet read contiguously through line 4500/9152; files through app_test.go fully read and credited, chatlist.go partial begins4352. Includes receipt decoder actual field shapes and batch IDs, SQLite parenthesized chat search fix, contact/statistics queries, palette source precedence, shared terminal writer, font fallback installer, which-key geometry/interaction, animated lock setup, focused editing and bulk registrations. Existing OSC52 external-option mismatch is introduced here. Historical tests include real opener-spawning paths; none executed. Remaining entries stay pending.


Original reachable root patch frontier closed: all 4,205 change records across the original 188-commit graph at ccb0b49195cfcd4fc11ea86cb15294e603e2a753 are reconciled: 3,607 semantic read, 479 asset-inspected, 119 generated-classified, zero pending. This is source/history coverage, not runtime acceptance; no tests, launchers, installers, services, clipboard actions, or device operations were run. Later concurrent browser commits 039deb4 and 8653401 remain separately parent-owned.

The final 8b472de remainder was read in full: the 58-path packet through app_test.go, then the complete 4,875-line 35-path packet. It unifies WhatsApp with the desktop's shape/icon/spacing vocabulary; moves prominence from dividers to focused chips/surfaces; adds which-key discovery/backtracking, per-message mark presentation and bulk commands, contacts/favourites, receipt state, explicit media expiry/size explanations, in-app password setup and an animated lock, real-terminal QR handoff, executable discovery beyond PATH, and generated-palette precedence. Existing WUI cache/geometry and write-quit findings remain source-relevant; the clipboard `external` forwarding mistake is introduced in this patch. Tests intentionally preserve square default styles for old layout baselines, so passing square-oriented assertions would not itself establish pill geometry. Archived test opener paths were read without execution.
