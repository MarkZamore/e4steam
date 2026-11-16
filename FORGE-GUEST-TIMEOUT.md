# Modern Forge guest login

Forge can open temporary server-status connections while the actual player
connection logs in. Tracking only the most recent connection can leave the
two-minute join timeout active after a successful login. The guest now tracks
pending connections by identity and keeps the one that completes Minecraft
login. A genuinely incomplete connection still times out.

The downstream release `forge-modern-guest-v1` derives from the exact modern
Forge V2 JAR. It retains the filename, original metadata and Minecraft range
from 1.18.2 through 1.20.2. The build receipt records three changed class entries.
The recipe verifies the stock archive, Java sources and Forge compilation
inputs, preserves unrelated methods and verifies all other archive entries
against the stock JAR.

```powershell
python -B tools/forge_guest_timeout_build.py --stock $stock --libraries $libraries --java-home $jdk17 --out $output
python -B tools/forge_guest_timeout_build.py --stock $stock --out $output --verify-only
```

Use Temurin 17.0.20.1 and a shared libraries root containing the recorded
Forge 1.19.2 SRG input, ASM and SLF4J. The receipt identifies the compiled
sources and bytecode inputs needed to reproduce the build. Keep its exact
bytes alongside the released JAR.

`tools/ForgeGuestTimeoutProbe.java` is a Java 17 agent for an isolated Forge
1.19.2 client. It checks the installed JAR, the transformed login hook and the
real timeout code with local synthetic connections. Use
`link.e4steam.qa.ForgeGuestTimeoutProbe` as the agent's Premain-Class. Supply
an owned run containing `RUN.json`, a game directory under its `game` subtree,
a fresh evidence directory under `evidence` and these JVM properties.

| Property | Value |
| --- | --- |
| `lanminecraft.steamqa.run` | Owned run path |
| `lanminecraft.steamqa.game` | Fixture game path |
| `lanminecraft.steamqa.evidence` | Fixture evidence path |
| `e4steam.guestqa.mode` | `stock` or `candidate` |
| `e4steam.guestqa.jar` | Installed e4steam basename |
| `e4steam.guestqa.sha256` | Exact installed JAR hash |

Read `guest-timeout-probe.json` together with the process exit code. The stock
test expects the authenticated connection to close at 120 seconds. The
candidate test expects it to survive and checks that unfinished login still
times out. The probe does not require another Steam account or use a player's
world.

Stage the catalog with `tools/forge_guest_profile.py` using the verified
receipt and exact source commit. Publish the JAR and receipt at the new
immutable tag before switching the root index. Run `tools/active_profile.py`
on the staged selection, verify the public bytes and check installation through
the launcher. Rollback reselects the frozen V6 catalog and its checksums.
