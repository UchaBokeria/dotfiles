---
name: rust
description: Rust development. Use when working with .rs files, Cargo.toml, cargo builds, clippy, or rust-analyzer diagnostics.
---

# Rust

- System toolchain (`rustc`, `cargo` from Arch repos) + `rust-analyzer`
  in `~/.local/bin` (wired as the `rust` LSP entry).
- Diagnostics via LSP; prefer CLI feedback: `cargo check`, `cargo clippy
  -- -D warnings`, `cargo test`, `cargo fmt --check`.
- `target/` is scratch — never commit it; check `Cargo.lock` policy per
  project (bins commit it, libs usually don't).
