# Sonata console reference and corrective design record

Read-only source review of root inventory indices 37–41: five tracked files, 158,766 raw bytes. Every sanitized character was read in bounded displays; raw file SHA256 was reverified before and after. No app, browser, build, service or provider was invoked. This is checkout/design evidence, not proof of the serving release. The HTML's inline SVG structures were read; all 32 symbols' path values exactly match the already visually reviewed current Material Symbols atlas (sonata-console-symbols.json). No browser rendering or external Google Fonts request occurred.

## SCH001 — explicit readb visual ancestry

`docs/console-mockup.html:8–15` directly credits readb-web's tokens, base, glass, shell, command palette and component/page structures, re-skinned in Claude Code colours. This is stronger provenance than visual resemblance. The four palette pairs, Inter/JetBrains Mono, restrained warm Claude accent, rounded surfaces, spacing scale and optional layered glass explain the current UI source reviewed in sonata-ui.md. The mockup references remote Google Fonts; the corrective status in `console-redesign.md:19,51` says the implemented build bundles fonts/icons. Current UI font files were separately inventoried and reviewed. This establishes design inheritance, not a Blackwall wallpaper-generator integration or proof of owner approval of every detail.

## SCH002 — a corrective status appendix supersedes substantial original specification

`console-redesign-plan.md:5–26` proposes exactly three handwritten web files, router-token-or-origin write authentication, fixed 60-minute limit cooldown, fixed six-hour account-setting cooldown, and thirteen sequential tasks. `console-redesign.md:11–46` explicitly records deviations: React/Vite, cookie + per-process CSRF + Origin, window-dependent gateway cooldown/probe, candidate cooldown, additional conversation-shape fallback, covered/free budget exceptions, slash-command spelling, and charts that were **not built**. The original surfaces/API/alerts sections below still describe the older authentication, stdin-or-last-argument alerts, waterfall/value chart and old cooldowns. Read the dated corrective section with those proposals; isolated original paragraphs are stale implementation guidance. The current reviewed React views and API client align with the corrective shape, while backend authority remains the parent/history source reports. “All thirteen tasks on master, unreleased” is the document author's recorded status, not an audit execution or deployment result.

## SCH003 — sample explanatory copy is not router evidence

The mockup explicitly marks sample data at `console-mockup.html:2760,3405`; the latter says nothing is wired to a live router. Routing switches merely flip DOM ARIA/data attributes; budget input has no persistence/writer. Only appearance uses localStorage. Requests, account reset/usage, models, dollar values, run times and retry explanations are static fixtures. Its healthy badge tooltip says “Every account answers” (`:2761`), materially stronger than current backend health evidence. Account “Serving” and covered/value language are design antecedents of SU001/SU004, not independent account/provider acceptance. At phone width the top sample-tag class is hidden (`:2525`), although the Settings disclaimer remains. Keep sample status explicit when using this reference to explain the product.

## SCH004 — separate inherited weaknesses from corrected chart copy

The mockup has the same tablet icon-nav naming and mobile button sizing patterns discussed in SU005, and its meter has minimum width 4px (`:1039`), ancestry for SU007's visible zero sliver. Dialog/command palette set aria-modal but do not trap Tab or make background inert, like SU006; dialog restores last focus, palette does not. These are source contracts, not fresh visual/assistive-technology tests.

Conversely, the mockup labels model scores 0–100 (`:3136`) while drawing the best score 55.1 as 100% and 48.1 as 87% (`:3143–3154`). The **current** `ui/src/lib/catalog.ts` explicitly divides by best shown, and `ui/src/views/Console.tsx` explicitly tells the reader that bars are relative to the best score. That caption discrepancy was corrected in the implemented UI; do not carry it forward as a current defect.

## SCH005 — mockup explanation text contains literal HTML entities

The static CALLS array stores strings such as `429 &rarr; 200`, `&mdash;` and `&ldquo;`. `openCall` assigns descriptions and key/value cells with `textContent` (`console-mockup.html:3673–3740`), so those entities remain literal text in those generated dialog nodes rather than being HTML-decoded. This is a prototype source defect; it does not establish the same bug in the current API-backed Explain view. Its global page animation comment says “without a layout thrash”, immediately followed by `void main.offsetWidth` (`:3662–3663`): that operation deliberately forces layout to restart animation. Neither observation required executing the mockup.

## SCH006 — documentation publication boundary is narrower than its comment

`docs/.vitepress/config.mts:5–22` says the site publishes only the user guide and keeps design history in the repository; it excludes internals, superpowers, reviews, HANDOFF and a few other files. It does not name `console-redesign.md` or `console-redesign-plan.md`. Those Markdown design records therefore have no exclusion in this config; no published artifact/build was inspected, so actual publication is not claimed. `theme/custom.css:1–3` deliberately unifies documentation branding with terminal init via muted terracotta, while the dashboard uses its brighter Claude palette. This is deliberate family resemblance in source, not exact shared token generation.

## Omission recovery and limits

None of the parent's 35 whole-line omission records belongs to indices 37–41. Separately, the assigned 34 omissions in all 59 already reviewed `docs/superpowers/**` design files were raw-line SHA verified and safe surrounding prose/code recovered in `sonata-design-omissions-recovery.json`. Every recovered context was read; credential-shaped/auth values remain explicitly excluded. The sole CHANGELOG omission stays parent-owned. The recovery confirms previously recorded fetchModels timeout/error fallback, deferred auth_header config and subscription/key ledger tests; it introduces no new implementation acceptance claim.

This pass adds SCH001–SCH006. Other package/runtime/history frontiers remain assigned elsewhere; no global zero-new or exhaustive-system completion is asserted.
