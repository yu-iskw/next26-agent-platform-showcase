# Strict Python Agent Harness

This repository uses a strict quality gate for Python agent code. The goal is to prevent regressions in quality, typing, and security before merge or deployment.

## Canonical Local Gate

Run one command:

```bash
make quality-gate
```

This gate runs:

- `ruff format --check` for formatting conformance
- `ruff check` for lint, complexity, modernization, and selected security rules
- `pyright` with staged strict typing policy for static analysis
- `bandit` for Python security scanning
- `osv-scanner` through Trunk for dependency vulnerability checks

Optional deeper security checks:

```bash
make quality-gate-optional
```

## Complexity and Suppression Policy

- Max cyclomatic complexity is capped by Ruff (`max-complexity = 10`).
- Refactor first when complexity violations occur.
- Use suppressions only when there is a clear, documented reason.
- Always scope suppressions to the narrowest line/file.

Allowed suppression style:

```python
# noqa: S603 - subprocess args are static and validated in _build_cmd()
```

## Secure Coding Checklist

- [ ] External HTTP calls define explicit timeout and retry behavior.
- [ ] Inputs are validated at API and tool boundaries.
- [ ] No secrets are committed in source code, fixtures, or logs.
- [ ] Shell and subprocess calls avoid dynamic untrusted arguments.
- [ ] Any `noqa` or Bandit suppression includes rationale and narrow scope.

## CI Enforcement

CI runs `make quality-gate` as a required quality stage. Code must pass this stage before merge.
