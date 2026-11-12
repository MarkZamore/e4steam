# Forge world sharing on Java 8

The launcher opts in with `link.e4steam.launcherManagedLan=true` and supplies
`link.e4steam.launcherPlayerName`. The derivative applies to Forge 1.12.2 and
1.16.5. A native publication uses the saved world game mode and command flag.
When the world has commands disabled, both host and guests are denied.
Worlds created with commands enabled retain vanilla sharing permissions.
A failed publication clears its pending loopback relay before a retry.

Forge 1.16.5 defers to higher-priority keep-alive and login timeout
modifications, including Connectivity in All in One. When vanilla still owns
the constant, e4steam extends it only for Steam-authenticated connections.
The authentication and identity hooks remain required.

The pause button opens the integrated world in one click. After publication,
the slot opens the Steam recent players overlay. These two Minecraft versions
do not include the Mojang reporting screen. The existing e4steam chat actions
provide copy address, invite and close. Only authenticated Steam friend worlds
appear in the transient automatic list. The saved server list is independent.

Build with the pinned Gradle wrapper and Java 8 toolchain. Pass a verified
Java 8 JDK path and use a Java 21 Gradle JVM. The output is the remapped
`e4steam-forge-mc*.jar` from each target's `libs` directory.

```powershell
cd source/e4steam
.\gradlew.bat -p retro "-Porg.gradle.java.installations.paths=$java8" `
  '-PlanminecraftRetroVersion=0.3.2-lanmc.1' `
  :forge-1.12.2:build :core:test
.\gradlew.bat -p retro "-Porg.gradle.java.installations.paths=$java8" `
  '-PlanminecraftRetroVersion=0.3.2-lanmc.3' `
  :forge-1.16.5:build :core:test
```

When refreshing the author source, replay the downstream commits from the
previous source revision recorded in the release index. Review the Forge method
descriptors, Mixin targets, native listener lifecycle and current Steam library
before building the new revision. Retest both runtimes. Generate the index
with `tools/java8_world_sharing.py` from the committed source and freshly built
JARs. The tool verifies the required classes, mixins, Java 8 bytecode and notices.
Repeat a clean build and compare both complete SHA256 hashes before publishing.
Use the previous index as `--base-index` to keep the delivery tag and source
revision for byte-identical builds. Give new bytes a new version and immutable
delivery tag.
