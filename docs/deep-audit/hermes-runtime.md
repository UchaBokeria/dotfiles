# Installed Hermes runtime — opened source frontier

This is the NousResearch installed repository at ~/.hermes/hermes-agent, HEAD59a3866ea5a07290afd9a1d137d52d679b77f3ab, distinct from the cloud Hermes coordinator project and the completed setup-session review. The exact tracked-path inventory is hermes-runtime-coverage.jsonl. Inventory entries are pending semantic classification unless expressly read; size/list/hash do not count as understanding. Root has fully read AGENTS.md and SECURITY.md only. Earlier isolated permission functions are positive narrow evidence in hermes-infra.md, without implying their entire containing modules are read. No imports, CLI, plugins, providers, tests or services executed.

## HR001 — Frozen conversation state is an explicit upstream invariant

The installed development guide treats per-conversation prompt caching as a design constraint: changing historical context, toolsets, memory or prompt mid-conversation breaks the cached prefix, with compression as the named exception. Prompt-state changes normally defer to a new session. This is an upstream instruction, not yet verified across runtime implementations. It explains why writing a memory file or mirroring SOUL instructions cannot alone prove an already-running agent learned it. Actual loading/invalidation paths remain pending.

The core/edge split aims to keep model-sent tool surface narrow: CLI+skill, gated tool, plugin and catalog MCP precede adding a core tool. Profile isolation is intentional; unbound environment/global/import-time reads can select the launch profile in a multi-profile process. Facade/sibling modules and late imports matter when tracing actual production call sites or evaluating test mocks. Counts and guide rules describe intended architecture, not code acceptance.

## HR002 — Isolation and approval are explicitly different authority layers

SECURITY.md distinguishes terminal-backend confinement from wrapping the whole process tree. A sandboxed terminal backend does not claim to confine host-side code execution, MCP processes or imported plugins/hooks. Approval patterns, output redaction and skill scanning are documented accident-prevention heuristics, not containment against adversarial model output. Plugins execute with the agent's privileges. External network surfaces require authorization; session IDs are routing handles, and permitted callers are equally trusted within one adapter.

These are policy claims to reconcile with selected backend, actual source and deployed surface. They do not establish which sandbox is active on this host or authorize a change. The older setup session's broad hands-off permission and later draft-only messaging restriction remain separate owner intent evidence. No vulnerability exploitation or external reporting occurred.
