# Shared e4steam component for LANMinecraft

This is MarkZamore's single GitHub delivery location for the e4steam JARs used by every LANMinecraft pack. It republishes exact, unmodified author binaries from [Kamilhik/e4steam](https://github.com/Kamilhik/e4steam), created by Kamilchik. The official project page is [e4steam on CurseForge](https://www.curseforge.com/minecraft/mc-mods/e4steam).

No JAR is stored in this Git tree or duplicated inside a pack repository. Each distinct author build occurs once in this repository's immutable versioned release assets. Forge, NeoForge and Fabric/Quilt require different author binaries; there is no invented universal JAR.

| Release | Payload | Reason |
| --- | --- | --- |
| `v0.3.4` | 6 modern author JARs for supported Minecraft 1.17–26.3 branches | Current author release |
| `v0.3.2` | 13 older author JARs for remaining Forge/Fabric branches | Latest compatible files; the author published no retro JARs in 0.3.4 |

`components.json` is the canonical index of the 19 selected builds: loader, exact Minecraft range, original author URL, MarkZamore delivery URL, size and SHA-256. `SHA256SUMS.txt` covers the same 19 exact files. Frozen `releases/v<VERSION>.json` inventories preserve each release's payload and metadata independently of future active-catalog changes. Each release carries that frozen manifest and its checksums. Old versioned assets remain available after future updates.

The launcher downloads from:

```text
https://github.com/MarkZamore/e4steam/releases/download/v<VERSION>/<AUTHOR-FILENAME>
```

The launcher verifies size and SHA-256, caches each selected component globally under `Minecraft/Launcher/ManagedComponents/e4steam`, and installs it into the prepared instance's `mods` directory. Packs reuse this component instead of shipping separate e4steam payloads. Minecraft and the loader remain versioned runtime components; this repository contains neither the game nor a replacement tunnel or server.

## Reproduce and verify

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

The original author license, NOTICE and third-party notices for both source releases are preserved in `upstream-notices`, with source URLs and SHA-256 in `upstream-notices/sources.json`. The original JARs retain all embedded notices, including bundled dependency notices and the MIT SkinRestorer notice where present. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Mirroring these files does not claim authorship of e4steam or certify gameplay compatibility; no Minecraft client or world was started to prepare this delivery repository.
