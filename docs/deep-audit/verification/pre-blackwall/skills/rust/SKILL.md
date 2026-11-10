1: ---
2: name: rust
3: description: Rust development. Use when working with .rs files, Cargo.toml, cargo builds, clippy, or rust-analyzer diagnostics.
4: ---
5: 
6: # Rust
7: 
8: - System toolchain (`rustc`, `cargo` from Arch repos) + `rust-analyzer`
9:   in `~/.local/bin` (wired as the `rust` LSP entry).
10: - Diagnostics via LSP; prefer CLI feedback: `cargo check`, `cargo clippy
11:   -- -D warnings`, `cargo test`, `cargo fmt --check`.
12: - `target/` is scratch — never commit it; check `Cargo.lock` policy per
13:   project (bins commit it, libs usually don't).
