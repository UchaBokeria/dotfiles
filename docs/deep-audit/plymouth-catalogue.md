# Retained Plymouth theme catalogue

Current tree `/home/scriptkid/.config/plymouth-adi1090`:11,310non-Git files,247text files and11,063PNG assets. Clean unshallow Git checkout HEAD5d8817458d764bff4ff9daae94cf1bbaabf16ede with47reachablecommits; history separately assigned toinfra. All247textfiles have semantic coverage through160distinct full baselines/complete deltas plus87byte-exact references to reviewed representatives. Full rootGPLv3, per-theme license changes, README, source template, descriptors and preview script were read. No setup,showplymouth,initramfs or daemon command executed. Ledger plymouth-catalogue-coverage.json.

## PC001 — Shared implementation, distinct animated artwork

Each concrete script preloads progress-N.png frames,centers the first image by window origin/size,and registers a refresh callback that increments a counter and selects floor(progress/speed) modulo frame count. Speed andcount vary; the counter is refresh-callback based, not actual boot progress. Normal/question/password/message callbacks manage centered text and white asterisk sprites near the screen bottom. `state.status` is changed to pause/play but refresh_callback never consults it, so its name alone does not prove animation pauses during a password request. Window dimensions/centering are computed once; no resize handler is shown. The template intentionally retains NUM/SPEED placeholders; it is not a concrete runnable theme. Descriptors point to installed /usr/share/plymouth theme paths, not this retained checkout.

The catalogue comes from upstream Android-boot-animation ports. Its imagery includes centered geometric loops, monocolor sci-fi HUDs,particles,metal/organic spheres,vendor logos,rainbow rings and stylized faces. Every93asset directory has its first/middle/last frame (single root previewoneframe) visually reviewed on11labelled sheets. Large_icons directories retain alternate resolution frames. These are upstream alternatives, not93owner-selected favourites. They do not establish active boot visuals: current GRUB and initramfs inputs have no Plymouth hook or splash argument (etc-system.md).

## PC002 — Complete frame structure reveals catalogue imperfections

All11,063PNGs were fully decoded and their format,size,mode recorded; zero decoding failures. This is per-file structural inspection, not a claim of visually viewing11,063frames or running animations. Cross-checking every concrete script's declared load range against filenames finds seal_2 declares400butprogress-5.png is missing; its399otherframes decode. cuts includes1extra numberedframe,hexagon_dots_alt51extra,androg55extra beyondloadedrange. The working tree is clean, so these are retained tree contents rather than observed uncommitted owner edits. No active machine defect is inferred. The three inspected points do not prove temporal smoothness or every interiorframe'svisualcontent.

## PC003 — Preview is effectful

showplymouth.sh insists onroot,starts plymouthd,shows splash,repeatedlyupdates andsleeps,thenquits. A source read is appropriate; invoking it would touch the live desktop/boot service path. Root check failure exits without explicit nonzero status, duration lacks validation and cleanup has no trap, but no preview failure was reproduced. README's installation examples copy into system themes and rebuild initramfs; none was followed.

New catalogue findings reset no global counter because discoverycycle1 remains open. That historical frontier is now closed separately in [plymouth-history.md](plymouth-history.md) and plymouth-history.json (47 commits; exact current baselines plus complete historical semantic deltas).
