# Process

- No code without a spec. If a spec does not exist or does not cover the change, create or update it first.
- Always run `uv run pytest` before closing a change. Do not archive if tests are failing.
- Use `uv` only — never `pip` or `pip install`.
