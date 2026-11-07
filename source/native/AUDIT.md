# Native Steam bridge audit, 2026-11-07

Reviewed base: `9d6d980e120957e718eda6f7f23bb914ab633d32`, Windows x64,
Rust 1.98.1, locked Steamworks 0.13.1 / steamworks-sys 0.13.0.

Two verified ordering defects were fixed:

- `unpublish()` used a blocking send into the bounded UI command queue. A full
  queue could freeze the caller; older publication requests could reopen a
  withdrawn world. Cancellation now advances an independent sharing epoch.
  Queued requests and lobby-creation callbacks from earlier epochs cannot publish.
- The host sent READY before installing the guest's one-use loopback identity
  claim. A fast guest could begin login first. The claim now exists before READY;
  a failed READY send removes it.

The reviewed design retains the active Steam-account check, exact runtime
variant, direct-friend membership, post-join owner verification, authenticated
remote SteamID, random per-publication generation and one-use loopback claims.
The tunnel holds at most one inbound batch (16 frames of at most 16 KiB) and
one outbound frame, retaining outgoing bytes when Valve reports backpressure.
No new transport protocol or content-mod rules were added.

Validation: `cargo test --locked --offline --all-targets` passed 10 tests,
with zero failed or ignored cases. `cargo clippy --locked --offline --all-targets
-- -D warnings` passed. `cargo fmt` and `git diff --check` passed.
Tests cover queue saturation/cancellation, publication retry, READY ordering
and failure cleanup, one-use loopback claims, generations and metadata parsing.

The Valve DLL used for linking/tests has SHA-256
`eb17909a76668cf9ae0b92a618a34a50f6c73d3a6787cb4dd8ce36a8b10bfb75`;
the verification script also checked its Valve signature. Real overlay
invitations, two-account Steam relay, world persistence and network performance
under chunk streaming remain NOT RUN by this component audit. The exact pack
clients must complete their own acceptance before publication.
