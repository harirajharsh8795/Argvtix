# Contributing to ARGVTIX 🛡️

Thank you for contributing to the **Enterprise AI Reliability Platform (ARGVTIX)**.

## Development Setup

1. **Clone & Environment**:
   ```bash
   git clone <repo-url> argvtix
   cd argvtix
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

3. **Run Tests**:
   ```bash
   pytest tests/ -v
   ```

4. **Linting & Code Style**:
   ```bash
   ruff check .
   ruff format .
   ```

## Commit Guidelines

- Format: `<type>(<scope>): <summary>`
- Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`
- Example: `feat(watchdog): add duplicate refund detection rule`

## Pull Request Checklist

- [ ] All unit and integration tests pass (`pytest tests/ -v`).
- [ ] Code formatted with `ruff format .`.
- [ ] No lint warnings with `ruff check .`.
- [ ] New functionality covered by unit tests.
