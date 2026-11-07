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

## Disconnect delivery audit, 2026-11-08

Reviewed base: `faa25063441b83f589caab505dfefda8932e4fe4`.
The game may enqueue its final Disconnect and then close/reset the local stream
in one worker poll. The previous implicit NetConnection drop used linger=false,
discarding unsent reliable messages. An established receiver also rejected a
terminal Steam state before draining its queued messages. The bridge now
explicitly flushes and closes local EOF/reset with linger=true, drains received
tail bytes after a remote close, and bounds that nonblocking receive drain to
two seconds if the local game is backpressured. Existing identity, membership,
generation, cancellation and claim checks remain in place.

Terminal diagnostic snapshots include the separate game connection's state,
end reason, pending/unacknowledged reliable bytes, ping and local buffers. They
exclude payloads, account identities and sharing-generation secrets. The game's
30-second KeepAlive watchdog is unchanged. Missing KeepAlive replies in the
reported incident cannot be assigned a root cause from the available logs.

Validation: `cargo test --locked --all-targets` passed 16 tests, zero failed or
ignored. Six new regressions cover final data before EOF/reset, send
backpressure, batches and partial local writes after remote closure, a reset
local writer with a readable final packet, invalid wire frames, and bounded
terminal draining. `cargo clippy --locked --all-targets -- -D warnings`,
`cargo fmt` and `git diff --check` passed. This is a component test, not a new
two-account Steam/game run; overlay, relay and exact-client acceptance remain
the consuming pack's responsibility.

Follow-up review: an already authenticated guest may drain received tail bytes
when lobby ownership changes, but sends no new game bytes and cannot start a
handshake with the changed owner. Pre-READY ownership checks stay strict.
The guaranteed scope is forwarding bytes already available on an established
connection during an ordinary per-peer EOF/timeout while the host listener is
alive. Whole-world withdrawal is best effort: Valve closes accepted connections
ungracefully when its listen socket is destroyed. We do not retain that listener
after unpublish, because doing so would block immediate sharing on virtual port
481. Two-account world-shutdown delivery remains NOT RUN.

## Overlay invitation handoff audit, 2026-11-08

Previously the overlay callback could reach the frontend only if its target was
already present in the periodic rich-presence directory. The subsequent Join
command required the same directory entry again after saving the current world.
This incorrectly coupled explicit invitations to an independent listing cache.
It also treated the friend joined through as the owner, rejecting invitations
sent by a guest even when the actual host was another immediate friend.

An invitation now resolves the advertised owner from fresh lobby metadata and
validates both the inviter's friendship and the host's friendship, metadata and
exact variant. The verified lobby/owner pair is retained in one bounded slot,
consumed once by the normal join and expires after the existing 30-second
handshake period. Manual joins retain directory validation. Joined-lobby actual
ownership, membership, sharing generation and one-use identity claims are
unchanged. Compact callback/handoff events distinguish an unreceived invitation
from rejection or failure to enter the game; they contain no account identities.

Validation: `cargo test --locked --all-targets` passed 19 tests, zero failed or
ignored. Three new handoff regressions cover a delayed frontend without a
directory entry, one-shot/target binding, replaced intent, expiry and clearing.
These are component regressions, not a two-account overlay acceptance result.
Valve documents the inviter field as the friend joined through:
https://partner.steamgames.com/doc/api/isteamfriends#GameLobbyJoinRequested_t

The combined follow-up passed 20 native tests (zero failed or ignored) and
Clippy with warnings denied. The additional owner-change regression verifies
that a still-connected handle cannot send new game bytes after ownership
changes. A newer explicit invitation also revokes an older pending frontend
handoff while its own fresh metadata is being checked.
