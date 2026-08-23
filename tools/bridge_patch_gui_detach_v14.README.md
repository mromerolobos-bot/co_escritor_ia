# Bridge V1.4 GUI detach patch

One-off deterministic helper for updating a local V1.3 daemon so GUI programs do not block the bridge. It adds explicit `DETACH:` support plus automatic detaching for a small GUI executable allowlist, and adds regression tests. Runtime source changes are expected to be reviewed and committed separately after live validation.