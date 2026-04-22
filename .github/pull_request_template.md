# Pull Request

## Summary

- Describe what changed and why.

## Validation

- [ ] `make quality-gate`
- [ ] Any additional feature-specific checks were run

## Secure Coding Checklist

- [ ] External requests include explicit timeout/retry behavior
- [ ] Inputs are validated at API/tool boundaries
- [ ] No secrets added to code, fixtures, or logs
- [ ] No dynamic shell/subprocess with untrusted input
- [ ] Any `noqa`/Bandit suppression has narrow scope and rationale
