# Development

Local dev setup, unit test commands, and integration test configuration for
contributors to `teardrop-sdk`.

```bash
# install dev deps
pip install -e ".[dev]"

# run tests
pytest

# run tests with coverage
pytest --cov=teardrop --cov-report=term-missing
```

## Admin Client Checks

The dedicated admin surface has async endpoint coverage, sync delegation coverage, and a
spec-shaped route/model check:

```bash
venv\Scripts\python -m pytest tests/test_admin_client.py tests/test_admin_sync_client.py -q
venv\Scripts\python -m pytest -q
venv\Scripts\python -m ruff check .
venv\Scripts\python -m ruff format --check .
```

## Integration Tests

Integration tests make real HTTP requests against the Teardrop API. Set the following environment variables to enable them:

```bash
export TEARDROP_TEST_URL="https://api.teardrop.dev"
export TEARDROP_TEST_EMAIL="you@example.com"
export TEARDROP_TEST_SECRET="your-password"

pytest tests/integration/ -v
```

Without those variables set, all integration tests are skipped automatically.

---

**Related:** [README](../README.md) · [tests/](../tests/) · [tests/integration/](../tests/integration/)
