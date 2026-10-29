# Shared e4steam component for LANMinecraft

This is MarkZamore's single GitHub delivery location for e4steam used by LANMinecraft packs. The active `native-lan-ui-v1` profile removes the extra LAN Settings button and intermediate form from six modern artifacts while retaining Steam connections and invitations. Thirteen retro artifacts already lack that UI and retain exact author bytes. The author is Kamilchik, [Kamilhik/e4steam](https://github.com/Kamilhik/e4steam); the official project page is [e4steam on CurseForge](https://www.curseforge.com/minecraft/mc-mods/e4steam).

Runtime JARs are release assets; pinned source and build tooling are in this Git tree. Historical author binaries remain immutable. Modified modern artifacts use distinct filenames, hashes and a separate release tag; original in-JAR mod version metadata remains unchanged for API compatibility and does not identify a derivative as unmodified. Forge, NeoForge and Fabric/Quilt retain separate platform artifacts.

| Release | Payload | Reason |
| --- | --- | --- |
| `v0.3.4` | 6 modern author JARs for supported Minecraft 1.17–26.3 branches | Current author release |
| `v0.3.2` | 13 older author JARs for remaining Forge/Fabric branches | Latest compatible files; the author published no retro JARs in 0.3.4 |
| `native-lan-ui-v1` | 6 explicit modern UI derivatives, plus a profile index selecting all 19 targets | Static build-time UI removal; retro references still use exact historical assets |

`components.json` is the canonical schema-2 index of all 19 selections. It separates author version/filename/SHA/URL from delivery tag/filename/SHA/URL and records the exact derivation. `SHA256SUMS.txt` covers these same selections; `profiles/native-lan-ui-v1.json` freezes this profile. `author-components.json` and frozen `releases/v<VERSION>.json` preserve the original source inventory independently. Historical assets are never replaced or deleted.

The launcher downloads from:

```text
https://github.com/MarkZamore/e4steam/releases/download/native-lan-ui-v1/<DERIVATIVE-FILENAME>
```

Unchanged retro entries retain their `v0.3.2/<AUTHOR-FILENAME>` URLs. The launcher verifies size and SHA-256, caches each selected component globally under `Minecraft/Launcher/ManagedComponents/e4steam`, and installs it into the prepared instance's `mods` directory. The UI policy is already part of the delivered artifact; the launcher does not patch its JAR at startup. Minecraft and the loader remain separately versioned runtime components.

## Historical exact-author mirror

Python 3.12+, Git, and GitHub CLI are sufficient. No game launch, account change, Steam call or private API key is required.

```powershell
python -B tools/components.py stage --cache <verified-author-jar-cache>
# Without --cache, fetch the exact author URLs named by components.json.
python -B tools/components.py verify
python -B -m unittest discover -s tools -p test_components.py
python -B tools/components.py publish
python -B tools/components.py verify-remote
```

Staging checks every JAR's exact bytes and retained license/notice entries. Publishing uploads all JARs first, checksums next and the release manifest last. Existing versioned assets are never overwritten or deleted; a conflicting existing file stops publication. Remote verification downloads every selected JAR from this account's release URLs and hashes the received bytes before launcher delivery URLs are activated.

Author license, NOTICE and third-party records for both source releases are preserved in `upstream-notices`, with source URLs and SHA-256 in `upstream-notices/sources.json`. Derivatives keep every embedded author/dependency notice and add a downstream modification notice. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [NATIVE-UI.md](NATIVE-UI.md). This repository does not claim authorship of e4steam or a new complete manual Steam gameplay matrix.

## Native LAN UI profile source

The separate [native-lan-ui-v1 profile](NATIVE-UI.md) removes the extra LAN Settings button and combined form while retaining Steam transport and invitations. Its pinned author source and small downstream patch are in `source`; `tools/native_ui.py` only prepares declared derivative artifacts at build time. Original author releases remain immutable. `author-components.json` preserves the source inventory used by the original mirror tool; no per-launch JAR edit implements this UI policy.

```powershell
# JDK 21.0.12.1+1; the workflow also builds on Linux and Windows.
cd source/e4steam
.\gradlew.bat --no-daemon apiChecks test headlessEntrypointAudit releaseJars
cd ../..
python -B -m unittest discover -s tools -p "test_*.py"
python -B tools/components.py stage --out dist/originals
python -B tools/native_ui.py stage --originals dist/originals
python -B tools/native_ui.py verify --originals dist/originals
```
