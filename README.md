# Shared e4steam component for LANMinecraft

This is MarkZamore's GitHub delivery location for the shared e4steam component.
The active `native-lan-ui-v3` index selects twenty loader/Minecraft targets.
It retains all nineteen V2 selections and adds the declared source-built
Legacy Fabric 1.6.4 port described in [the platform notes](LEGACY-FABRIC-164.md).
Six modern derivatives hide the extra LAN Settings button/form and apply only
current configured `lanOnlineMode` before native integrated publication.
The thirteen older variants never had that form/applier and retain exact author
bytes. Native game mode, commands, PvP, capacity and port are preserved by the
modern hook. Those nineteen selections retain the author Steam authentication,
transport, invitation and native-library entries. The additional source port
reuses the pinned shared source with declared legacy adapters; its provenance
is a source build rather than an original author artifact.

The author is Kamilchik, [Kamilhik/e4steam](https://github.com/Kamilhik/e4steam).
The official page is [e4steam on CurseForge](https://www.curseforge.com/minecraft/mc-mods/e4steam).
Derivative filenames, hashes, source patches and delivery tags are explicit;
in-JAR author version metadata remains unchanged for API compatibility. These
are declared downstream distributions, not unmodified author releases.

| Release | Status |
| --- | --- |
| `v0.3.2` | Immutable thirteen selected retro author JARs |
| `v0.3.4` | Immutable six modern author JARs |
| `native-lan-ui-v1` | Immutable historical six UI derivatives and nineteen-target index |
| `native-lan-ui-v2` | Immutable six UI/authentication-lifecycle derivatives and historical nineteen-target index |
| `legacy-fabric-164-v1` | Immutable source-built Legacy Fabric 1.6.4 payload and build receipt |
| `native-lan-ui-v3` | Current twenty-target canonical index and frozen profile |

`components.json` is the canonical schema2 index, and `SHA256SUMS.txt` covers its
exact selections. Rows retain author provenance separately from delivery
filename/SHA/size/URL/tag. Three capabilities preserve hidden or absent extra LAN
UI, configured modern native-publish online mode, and original Steam authentication.
[The frozen V3 profile](profiles/native-lan-ui-v3.json) must match the active
selection. Author inventories and older profiles remain immutable history.

The canonical index is
`https://raw.githubusercontent.com/MarkZamore/e4steam/main/components.json`.
Modern payloads use this account's `native-lan-ui-v2` URLs; unchanged retro payloads
retain `v0.3.2` URLs. The new source port uses `legacy-fabric-164-v1` URLs and
does not claim a nonexistent original author JAR. A compatible launcher verifies/caches this shared index and
JAR pins. Launcher429 predates the index consumer and requires the separate
launcher update; publishing V2 does not change its compiled V1 pins. UI/auth
behavior belongs to the delivered JAR, without a per-launch JAR rewrite or
pack-name rule.

[V2 behavior and checks](NATIVE-UI-V2.md) describe the exact four changed modern
entries. [Upstream updates](UPSTREAM-UPDATE.md) retain the last verified patched
selection when author bytes, required behavior or target compatibility change.
The receipt pins both source patches and author inventory. Linux/Windows CI,
frozen-profile reproduction, immutable conflicts and actual public-byte checks
precede activation. New author releases require explicit review instead of
silently replacing patched delivery.

```powershell
# JDK21, including the source build's Java16 legacy targets.
cd source/e4steam
.\gradlew.bat --no-daemon apiChecks test headlessEntrypointAudit releaseJars
cd ../..
python -B -m unittest discover -s tools -p "test_*.py"
python -B tools/components.py stage --out dist/originals
python -B tools/native_ui_v2.py stage --originals dist/originals
python -B tools/native_ui_v2.py verify --originals dist/originals
python -B tools/active_profile.py
```

[Validation scope](profiles/native-lan-ui-v2-validation.json) separates source,
native target application and complete public-download evidence from gameplay.
All nineteen selected JARs were downloaded and verified; all eleven V2 release
assets were checked by full size/SHA and actual metadata bytes. This does not
claim a new complete two-account/full-game matrix across every version and OS.
Raw user logs, identifiers and personal worlds are not release assets.

[The V3 validation record](profiles/native-lan-ui-v3-validation.json) and
[actual public-byte verification](profiles/native-lan-ui-v3-public-verification.json)
record the exact four-job source CI run, all four immutable port release assets
and all twenty selected public JAR downloads. Legacy Fabric has native
one-account client/world/publication and untrusted-login evidence; two-account
Steam gameplay and remote player/cape visuals remain NOT RUN. The source port
has its own pinned JDK 25.0.2 Linux/Windows reproduction job; modern JDK 21
builds and historical V2 tooling remain separate.

Author license/NOTICE/third-party records remain in every JAR and `upstream-notices`.
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [historical V1](NATIVE-UI.md),
and source provenance in `source`.
