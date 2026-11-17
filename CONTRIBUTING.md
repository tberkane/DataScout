# Contributing

Thanks for your interest in DataScout. Issues and pull requests are welcome.

## Development setup

```bash
git clone https://github.com/tberkane/DataScout && cd DataScout
python -m venv .venv && source .venv/bin/activate     # Python ≥ 3.10
pip install -e ".[dev]"
```

## Checks (the same ones CI runs)

```bash
ruff check . && ruff format --check .   # lint and formatting
mypy                                     # type checks
pytest                                   # tests with coverage
mkdocs build --strict                    # documentation
```

## Guidelines

- **Tests run offline.** They must not need API keys or network access: mock the LLM, HTTP,
  crawler and OCR clients with the fakes in `tests/conftest.py`.
- **Never execute LLM output.** Schemas and replies are parsed and validated.
- **Never commit API keys**, including in notebook outputs.
- **Public API** changes need type hints, docstrings and a CHANGELOG entry under "Unreleased".
- Every pull request is reviewed before merging.

## Reporting security issues

Please follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
