> **Scope update — 2026-11-08 16:35 +04:** The owner removed the three-zero-cycle requirement and requested a bounded closeout for development. See [development handover](closeout.md). Older cycle counters and pending lists below preserve history; they are not an active instruction to continue exhaustive expansion.

# Blackwall audit — development handover

Requested2026-11-08. **Concluded under the owner's revised bounded scope.** Large installed upstream areas remain explicitly unread; exhaustive closure is not claimed. This directory is the durable evidence and checklist, not a claim that every byte of the machine has been understood. No repairs/deployments/services/syncs/remote-device operations were performed.

Start with [development handover](closeout.md), then the historical [plan](plan.md), [architecture map](architecture-map.md), [taste and future development](taste-and-development.md), then the component reports. Evidence separates direct owner requests, agent narratives, source facts, controlled reproduction and live observations. Exact hashes support deduplication only when a representative has actually been read.

| Report | Scope |
|---|---|
| [Desktop](desktop.md) | Hyprland/Lua/glass, Eww, Waybar/Rofi, Nvim, themes, SDDM, assets |
| [Infrastructure](infrastructure.md) | Installer, scripts, Fish/tmux/plugin trees, ArchPilot and tests |
| [History and intent](history-intent.md) | Original docs, Remember, snapshots, owner session archaeology, OpenCode/mobile |
| [Machine](machine.md) | Actual deployment/config links, units, session state, installed tools and provenance |
| [Machine helpers](machine-helpers.md) | Release/watchdog/resource guard, sync/clipboard helpers, complete local Hyprland control package |
| [WhatsApp](whatsapp.md) | All non-UI Go source/tests, config/store/daemon/modal/media/theme contracts |
| [WhatsApp UI](whatsapp-ui.md) | All UI/render source/tests/goldens and end-to-end interaction defects |
| [Concurrent browser](concurrent-browser.md) | New full-desktop/page terminal browser, installed Casty source and bounded pure probe |
| [ArchPilot chronology](archpilot-session-chronology.md) | Owner intent, archived tool evidence and corrected historical claims |
| [Desktop session chronology](opencode-desktop-session.md) | Mobile/browser session chronology and visual evidence frontier |
| [Reachable Git patches](root-patches.md) | All original reachable commit patches and causal evolution |
| [Git refresh](git-refresh.md) | Full317unreachable commit graph, trees and blobs, synthetic snapshots distinguished |
| [Archived research review](opencode-desktop-root-research.md) |196research references, failed acquisitions, recovered public bodies and missing tails |
| [Machine configuration continuation](machine-config-root.md) | Retained desktop/remote settings and Code store evidence |
| [Sonata source](sonata-source.md) | All202authoredsourcefiles, tenant/budget/auth/restart contracts |
| [Sonata UI](sonata-ui.md) | All55UIpaths and visualsource boundaries |
| [Sonata design history](sonata-design-history.md) | All59permanent specs/plans and corrective appendices |
| [Sonata operating docs](sonata-operating-docs.md) |24guide/internal documents reconciled against source |
| [Sonata console history](sonata-console-history.md) | Mockup, readb ancestry and implemented deviations |
| [Sonata tests](sonata-tests.md) | All258test paths fully read; no suite execution |
| [Hermes setup history](hermes-infra.md) |1086parts, direct owner refinements and acceptance gaps |
| [Spark theme history](spark-theme-session.md) |2236parts, model/image/theme/account-removal chronology |
| [Spark emitter provenance](spark-emitter-provenance.md) | WIP implementation, surviving theme and unresolved replacement cause |
| [Installed Hermes runtime](hermes-runtime.md) | Active17,751tracked-path inventory and runtime-source frontier |
| [Installed Omnigent](omnigent-runtime.md) | Completed assigned source review; runtime acceptance limits remain |
| [Sonata remaining docs/source](sonata-root.md) | All153rootbucketpaths: loopplugin, release/design/docs and provenance |
| [Administrative policy](administrative-policy.md) | Effective sudo, local/shipped polkit, shell profiles and enabled unit source |
| [System configuration](etc-system.md) | GRUB/kernel/initramfs, ESP automount, SSH and package-modified settings |
| [Previous OpenCode installation](opencode-pre-blackwall.md) | All136backup paths with source/asset/credential dispositions |
| [Machine visual configuration](machine-visual-configs.md) | Installed GTK/Qt/Spotify assets and selection limits |
| [External Rofi catalogue](external-rofi.md) | Upstream alternatives, previews and shallow Git boundary |
| [Plymouth catalogue](plymouth-catalogue.md) | All current text, decoded animation structure and representative frames |
| [Plymouth history](plymouth-history.md) | All47availablecommits, source evolution and original frame anomalies |
| [SDDM history](sddm-history.md) | All98commits and installed-versus-repository selection |
| [Small Neovim/docs histories](root-small-db.md) | Persistence causality, positive restoration and historical overclaims |
| [Desktop boundary review](cross-review-desktop-boundaries.md) | Shared terminal graphics ownership and report reconciliation |
| [Infrastructure boundary review](cross-review-infra-drift.md) | Current drift, backend scopes and effective-policy limits |
| [Unreachable root](dangling-root.md) | Stash content including index/untracked trees, docs/scripts/installer/tmux/WhatsApp |
| [Unreachable desktop](dangling-desktop.md) | Historical visual deltas and generated palette roles |
| [Unreachable ArchPilot](dangling-archpilot.md) | Additional36source versions beyond older snapshot closure |

The initial inventory contained46,104 paths /1.51GB. Every initial path now has a non-pending disposition after reconciliation; generated, asset and storage classification does not mean semantic source review. Generated/dependency/build artifacts and binaries retain separate classifications. Current owned desktop and infrastructure source reads, copied67skills, canonical reachable Git patches, refreshed unreachable objects and the large mobile transcript are disposition-closed. DCP/statusbar, Spark/theme, remoteadb and installed Hermes agent supplied-history frontiers are closed, with deliberate value exclusions and unavailable original tails retained. Sonata's668trackedpaths/9,345,581bytes have full source202/UI55/docs-other153dispositions;258 test files were fully read in a separate ledger; no broad suite was executed. Installed Omnigent received a completed 946-Python-file source review; installed Nous Hermes (17,751 tracked paths in the frozen inventory) ends with explicit partial upstream coverage. Effective administrative policy111records is covered; selected configuration closure does not imply all installed application internals were read. See per-file `*-coverage.jsonl`, coverage-reconciliation.json, Git object inventories and worker reports for the exact moving frontier. Do not sum overlapping ledgers as distinct files.

Root snapshots were read as560distinct full baselines/deltas across13,483paths; ArchPilot snapshots as90distinct blobs across671paths. Original reachable root history has188commits; two concurrent browser commits were added and reviewed separately. Initial unreachable inventory found156danglingcommit tips with58distincttrees; refresh expanded this to317unreachablecommits,363trees and242blobs, all separately accounted for. All-parent tree inspection added versions ordinary first-parent patches omit. Submodules include shallow histories whose unavailable predecessors are explicit limits.

Controlled checks include source-to-output exact comparison for21theme emitters, six authored radius checks, read-only live compositor/system metadata, one current-workspace screenshot, installed binary build-info parsing, and an audit-only pure Go editing probe. These do not substitute for live UI, reboot, installation or physical-device acceptance. Broad suites were not run because source review found desktop/state side effects.

Another session is adding terminal-browser functionality. Preserve its files and interpret new inventory changes as concurrent development until verified. Existing dirty changes are recorded in initial-git-status.txt and have not been reset, stashed or committed by this audit.

[Nous provider and ACP source review](hermes-provider-acp.md): all17 frozen paths fully read, with separate exact coverage ledger and source-only findings.

[Nous CLI source review](hermes-cli-root.md): active673path source frontier, including routing, launcher/update recovery and active-session ownership contracts.
