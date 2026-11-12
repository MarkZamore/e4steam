"""Verify the reviewed Java 8 Forge JARs and emit their component index rows."""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import zipfile


ROOT = pathlib.Path(__file__).resolve().parent.parent
VERSION = "0.3.2-lanmc.1"
FORGE_165_VERSION = "0.3.2-lanmc.2"
MIXIN_ROOT = "link/e4steam/retro/mixin/"
REQUIRED_CLASSES = {
    "link/e4steam/retro/RetroBootstrap.class",
    "link/e4steam/steam/SteamLanMetadata.class",
    "link/e4steam/steam/SteamLanWorld.class",
    "link/e4steam/steam/SteamLobbyManager.class",
    "link/e4steam/steam/SteamRuntime.class",
}
PLATFORMS = {
    "1.12.2": (
        "mcmod.info", {"GuiMultiplayerManagedLan112Mixin", "IntegratedServerManagedLan112Mixin",
                       "PlayerListManagedLan112Mixin", "ServerListEntryManagedLan112Mixin",
                       "ThreadLanServerPingManaged112Mixin", "WorldInfoManagedLan112Mixin"},
    ),
    "1.16.5": (
        "META-INF/mods.toml", {"LauncherIntegratedServerMixin", "LauncherJoinMultiplayerScreenMixin",
                              "LauncherLanPingerMixin", "LauncherNetworkServerEntryMixin",
                              "LauncherOptionsScreenMixin", "LauncherPauseScreenMixin",
                              "LauncherPlayerListMixin"},
    ),
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify_jar(jar, metadata, expected_mixins, version):
    with zipfile.ZipFile(jar) as contents:
        names = contents.namelist()
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate JAR entries in {jar.name}")
        required = REQUIRED_CLASSES | {
            metadata, "META-INF/LICENSE-e4steam.txt", "META-INF/NOTICE-e4steam.txt",
            "META-INF/LANMINECRAFT-LAN-NOTICE.txt", "META-INF/THIRD_PARTY_NOTICES.md",
            "e4steam.retro.mixins.json", "e4steam.retro.mixins-refmap.json", "e4steam-version.properties",
        }
        required.update(MIXIN_ROOT + mixin + ".class" for mixin in expected_mixins)
        if not required.issubset(names):
            raise ValueError(f"Incomplete {jar.name}: {sorted(required.difference(names))}")
        mixins = json.loads(contents.read("e4steam.retro.mixins.json"))
        if (mixins.get("compatibilityLevel") != "JAVA_8"
                or mixins.get("refmap") != "e4steam.retro.mixins-refmap.json"
                or not expected_mixins.issubset(mixins.get("client", ()))):
            raise ValueError(f"Missing required client mixins in {jar.name}")
        if metadata == "META-INF/mods.toml":
            timeout = "ServerGamePacketListenerForge165Mixin"
            if timeout not in mixins.get("mixins", ()) or MIXIN_ROOT + timeout + ".class" not in names:
                raise ValueError(f"Missing the Forge 1.16.5 timeout compatibility mixin in {jar.name}")
        properties = contents.read("e4steam-version.properties").decode("utf-8").splitlines()
        if f"version={version}" not in properties:
            raise ValueError(f"Unexpected e4steam version in {jar.name}")
        pinned = {}
        for name in sorted(names):
            if not name.endswith(".class") or name.startswith("META-INF/versions/"):
                continue
            data = contents.read(name)
            if len(data) < 8 or data[:4] != b"\xca\xfe\xba\xbe" or int.from_bytes(data[6:8], "big") > 52:
                raise ValueError(f"Java 8 cannot load {jar.name}!{name}")
            if name.startswith("link/e4steam/"):
                pinned[name] = sha256(data)
        if not REQUIRED_CLASSES.issubset(pinned):
            raise ValueError(f"Missing launcher Steam classes in {jar.name}")
        return pinned


def revision():
    # Class pins must name an exact source tree rather than a dirty worktree.
    git = ["git", "-C", str(ROOT)]
    if subprocess.check_output([*git, "status", "--porcelain"], text=True).strip():
        raise ValueError("Commit the exact derivative source before writing the index")
    return subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()


def build_rows(artifacts, profile, tag, source, upstream, version, forge_165_version):
    for game, (metadata, mixins) in PLATFORMS.items():
        lane_version = forge_165_version if game == "1.16.5" else version
        major, minor, patch = map(int, game.split("."))
        file = f"e4steam-forge-mc{major}.{minor}.x-v{lane_version}.jar"
        jar = artifacts / f"forge-{game}" / "libs" / file
        data = jar.read_bytes()
        pins = verify_jar(jar, metadata, mixins, lane_version)
        yield {
            "version": lane_version, "authorVersion": lane_version, "profile": profile,
            "fileName": file, "sizeBytes": len(data), "sha256": sha256(data),
            "deliveryTag": tag, "metadataPath": metadata, "loaders": ["Forge"],
            "downloadUrl": f"https://github.com/MarkZamore/e4steam/releases/download/{tag}/{file}",
            "minimumMinecraftVersion": [major, minor, patch],
            "exclusiveMaximumMinecraftVersion": [major, minor, patch + 1],
            "derivation": {
                "type": "source-built-java8-forge-world-sharing",
                "sourceCommit": source, "upstreamSourceCommit": upstream,
                "sourceBuiltClassSha256": pins,
            },
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-output", required=True, type=pathlib.Path)
    parser.add_argument("--version", default=VERSION)
    parser.add_argument("--forge-165-version", default=FORGE_165_VERSION)
    parser.add_argument("--delivery-tag", required=True)
    parser.add_argument("--base-index", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()
    if not re.fullmatch("[a-zA-Z0-9][a-zA-Z0-9._+-]{0,99}", args.delivery_tag):
        parser.error("Use an immutable GitHub release tag")
    for version in (args.version, args.forge_165_version):
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}-lanmc\.[0-9]+", version):
            parser.error("Use the downstream versions passed to Gradle")
    index = json.loads(args.base_index.read_text(encoding="utf-8"))
    upstream = json.loads((ROOT / "source/UPSTREAM.json").read_text(encoding="utf-8"))["upstreamCommit"]
    rows = list(build_rows(args.build_output, index["profile"], args.delivery_tag, revision(), upstream,
                           args.version, args.forge_165_version))
    kind = "source-built-java8-forge-world-sharing"
    index["builds"] = [row for row in index["builds"] if row["derivation"]["type"] != kind]
    index["java8Builds"] = rows
    args.output.write_text(json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    for row in rows:
        print(row["sha256"], row["sizeBytes"], row["fileName"])


if __name__ == "__main__":
    main()
