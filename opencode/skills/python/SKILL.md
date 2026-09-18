---
name: python
description: Python development. Use when working with .py/.pyi files — type errors, lint, pytest, virtualenvs.
---

# Python

- Diagnostics via the `pyright` LSP entry (`pyright-langserver` in
  `~/.bun/bin`). Prefer CLI feedback: `pyright`, `ruff check`, `pytest -x -q`.
- Prefer the project's venv (`.venv/`, `uv`) over system python. Never
  `pip install` into system site-packages — use `uv`/`pipx`/venv.
- ML/data libs (torch, transformers) may be installed per-project; check
  `requirements*.txt` / `pyproject.toml` before assuming availability.
