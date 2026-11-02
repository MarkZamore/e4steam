# Preserve the shared delivery policy on author updates

The active shared index selects a reviewed derivative, separately from the
immutable author mirror. Do not replace it with an author's latest-release index
or let a missing/failed build select an unpatched author modern JAR. Keep the last
verified patched selection while preparing a new version on a source branch.

The V2 source receipt pins the author inventory, both source patches and the
reviewed UI/authentication sources. New author bytes stop staging until an
operator reviews and rebases them. Source/native CI verifies all six modern
artifacts, and publication compares the complete result with the frozen profile.
The required features are hidden/absent extra LAN UI, configured online mode
before modern native publication, and retained author Steam authentication.
The thirteen retro JARs have no removed form/applier and stay exact author bytes.

For an author update:

1. Preserve the existing author releases, source receipts and profile assets.
   Prepare the new author inventory/source in an independent branch with exact
   platform ranges, source/JAR hashes and original notices.
2. Rebase both retained features. Review the native publish aliases, descriptor
   and actual Mixin application on a concrete supported target. Do not call the
   full settings applier or reset the native world options.
3. Update explicit source pins and tests. If a retro author adds a new panel or
   settings applier, reassess that variant; do not keep its old no-op exemption.
4. Allocate a new immutable downstream profile/tag for changed payloads. Never
   overwrite `native-lan-ui-v1`, V2 or historical author assets. Freeze the reviewed
   profile and preserve the three index capability names for compatible readers.
5. Pass the source, native build, byte-preservation and profile-reproduction CI
   on both Linux and Windows for the exact commit. Unknown author inventory or
   missing retained behavior fails publication instead of rebasing automatically.
6. Publish verified payloads before metadata and the release index. Download all
   selected JARs from this account's release URLs; verify full size/SHA and the
   declared derivative entries. Check all release API digests and metadata bytes.
7. After review of that public-byte proof, activate the exact frozen root index
   and checksum file. `verify-active` rejects an author fallback, missing policy
   capabilities or changed coverage. Failed preparation/publication leaves the
   prior verified selection in place.

The canonical index is
`https://raw.githubusercontent.com/MarkZamore/e4steam/main/components.json`.
Schema2 retains the existing platform/version/size/SHA/URL row fields and declares
the required capabilities at the top level. A compatible launcher verifies and
caches that index; unavailable or rejected updates retain its last verified
patched index, then the embedded patched snapshot. Launcher429 predates this
consumer and needs the separate shared-component consumer update once; simply
publishing V2 does not change its compiled V1 pins.

Updating a pack from its author does not authorize changing this shared selection
or dropping these source policies. No pack-name exception or per-launch JAR
rewrite implements these changes.
