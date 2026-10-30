# StackOS C3 update robot (6-hour schedule)

This is a **read-only audit** foundation, not an unattended package publisher.

- Runs on GitHub-hosted runners every six hours (best-effort GitHub schedule) and on manual dispatch.
- Validates HTTPS with the runner's default trust store.
- Fetches InRelease and checks the SHA256 of the APT Packages index against its metadata.
- Checks whether Mesa-related package names are listed.
- Reports failures in GitHub Issues; no changes to PCs or ISO.
- Does **not** verify the GPG signature of InRelease yet. Hash verification against an unverified release file is not sufficient to trust packages.
- Does **not** compile, install, sign or publish packages.
- Before adding publishing: require verified GPG metadata, reproducible C3 build, dependency tests, Mesa/RADV runtime tests, protected signing secrets, and a staged promotion gate.
- The installed PC's TLS failure may not reproduce on GitHub-hosted Ubuntu runners; correcting the C3 image trust-store packaging requires a separate fix.

Deployment: review branch `feature/c3-update-robot-6h`, test via workflow_dispatch, and merge only after review. GitHub Actions schedules on the default branch only.
