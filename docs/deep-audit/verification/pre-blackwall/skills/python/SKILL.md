1: ---
2: name: python
3: description: Python development. Use when working with .py/.pyi files — type errors, lint, pytest, virtualenvs.
4: ---
5: 
6: # Python
7: 
8: - Diagnostics via the `pyright` LSP entry (`pyright-langserver` in
9:   `~/.bun/bin`). Prefer CLI feedback: `pyright`, `ruff check`, `pytest -x -q`.
10: - Prefer the project's venv (`.venv/`, `uv`) over system python. Never
11:   `pip install` into system site-packages — use `uv`/`pipx`/venv.
12: - ML/data libs (torch, transformers) may be installed per-project; check
13:   `requirements*.txt` / `pyproject.toml` before assuming availability.
