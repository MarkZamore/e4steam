# Native LAN UI profile v2

This reviewed-source candidate keeps v1's removed extra LAN button/form and
restores one consequence of the removed form: applying the configured
`lanOnlineMode` when Minecraft publishes an integrated world through its native
path. The original form applied this preference through
`LanServerSettingsApplier.apply`; the direct native publication path did not.
An offline-session client could therefore be asked to authenticate with Mojang
even when the saved e4steam LAN preference was false.

The required publish HEAD injection reads the current tracked
`Config.INSTANCE.lanOnlineMode` and invokes an online-only setter bridge before
the native listening socket is opened. It preserves the native selected game
mode, command permission, port, PvP and player capacity. It does not call the
full settings applier or change config files. A missing setter fails visibly
before bind. If publication itself subsequently fails, the requested online
flag remains set on that unpublished integrated server.

The scope is all six modern Forge, NeoForge and Fabric/Quilt artifacts whose
extra form was removed. The thirteen retro selections never had that form or
applier and retain their exact author bytes. Their original per-connection
authenticated-Steam exception remains unchanged; this candidate does not add
a new global offline LAN setting to those older variants.

Each derivative is built from its exact frozen author JAR. Four entries may
change: `PauseScreenMixin.class`, `e4steam.mixins.json`,
`IntegratedServerLanMixin.class` and `LanServerSettingsApplier.class`. A
downstream notice is added. Every other uncompressed author entry, including
Config, Steam authentication/admission/transport, invitations, native libraries,
metadata and licenses, must remain byte-identical. Historical v1/profile and
author release assets are immutable.

The two source patches in `source/native-lan-auth-v2.json` apply in order at
`source/e4steam`: the historical UI patch, then the new authentication-lifecycle
patch. Source pins are checked before staging. `tools/native_ui_v2.py` stages and
reproduces candidates. Publication additionally requires successful Linux and
Windows native-profile CI for the exact clean source commit. Conflicting release
assets are rejected before upload; payloads precede the release index.

```powershell
cd source/e4steam
.\gradlew.bat --no-daemon apiChecks test headlessEntrypointAudit releaseJars
cd ../..
python -B -m unittest discover -s tools -p "test_*.py"
python -B tools/native_ui_v2.py stage --originals <frozen-author-cache>
python -B tools/native_ui_v2.py verify --originals <frozen-author-cache>
python -B tools/native_ui_v2.py publish --originals <frozen-author-cache> --ci-run <passed-run>
python -B tools/native_ui_v2.py verify-remote --originals <frozen-author-cache> --downloads <new-private-directory>
```

Source, unit, native symbol and complete byte-preservation checks do not establish
a new full-game or two-account Steam acceptance run for every supported target.
Staging/building does not publish or activate a candidate. Only after all nineteen
selected JARs and all V2 assets have been downloaded and verified may the reviewed
`components.json` and `SHA256SUMS.txt` replace the active root index. Main-branch
CI rejects an unpatched author index or a selection different from the frozen
reviewed profile. See [the upstream update workflow](UPSTREAM-UPDATE.md).
