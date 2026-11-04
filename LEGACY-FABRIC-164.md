# Legacy Fabric 1.6.4 source port

This downstream module targets Minecraft 1.6.4 / Fabric Loader 0.18.2 with
Legacy Fabric intermediary mappings. It is built from source; there is no
claimed author JAR for this previously unpublished platform. Shared Steam/TCP,
native loading, lobby authorization and connection ownership come from the
vendored Kamilhik/e4steam v0.3.4 source commit
`bdcea00e30ca519fa8190c0c5c04785d42b31dbc`. The nineteen existing delivery JARs
are retained byte for byte, with their original source and author provenance.

The isolated `source/e4steam/legacy-fabric-1.6.4` module owns version-specific
native symbols, client-thread dispatch, lifecycle, login, discovery and labels.
The build explicitly includes the neutral API/lobby/pacer source closure which
the upstream retro recipe does not include. Three neutral retro adapters are
extended with the matching current callbacks: loader pacing, optional native
login tracking, and join-timeout dispatch. Existing adapters opt out of native
login tracking unless their platform implements it.

## Ownership and native behavior

Remote identity is derived only from the authenticated live Steam bridge
owning the exact native TCP remote endpoint. Login rechecks the binding before
native player creation; admission checks again before native NBT loading.
An unknown loopback endpoint or an alias registry entry does not grant trust.
Duplicate account admission refuses the new connection before the native
duplicate-player kick path. The native name is `s` followed by thirteen
zero-padded unsigned base36 Steam ID digits, within the legacy username limit.

The local owner is proven through the actual integrated listener's paired
MemoryConnection and its native NetClientHandler/Minecraft owner objects.
Only that native local path may use the launcher's cached local profile while
Steam is unavailable. When the runtime knows the current Steam account it must
match that binding. This exception cannot authenticate TCP guests.

`minecraft.portable.legacy.registry` points at UTF-8 rows
`steamID|nativeName|displayNameBase64UTF8|portableUUID`. The local profile UUID
is the existing `minecraft.portable.identity.localPlayer` property. The
registry supplies labels and skin/profile IDs; it cannot create a live bridge.
Native storage, ownership, scoreboard keys and protocol names remain canonical.
Chat/entity display and tab labels use the display name. Single-token unique
online aliases work in native player lookups/completion. Ambiguous names and
historical names containing whitespace retain usable canonical command tokens;
the native command parser is not replaced.

The Open to LAN pause action initializes the actual native Share screen and
invokes its native Start action without displaying the intermediate form.
The module does not hardcode Nightmare settings or replace the pause menu.
Native/author callbacks, including Nightmare's no-escape restrictions, remain.
The listener binds explicitly to IPv4 loopback, matching the common Steam
bridge. Shutdown closes the relay and local proof. Discovery adds transient
Steam friends' worlds to the real multiplayer list; stale synthetic addresses
are consumed and never sent to DNS. Friendship, lobby owner, protocol and exact
Minecraft compatibility are checked before the normal author join path.

Log4j 2.19.0 remains the platform's explicitly declared dependency. The port
does not bundle Log4j classes or downgrade BTW's nested libraries. Steamworks4j
1.10.0 and the required desktop JNA/native subset are pinned by the recipe.
Mixin implementation classes stay in the mandatory Mixin configuration and
are excluded from direct helper preloading, as required by Knot.

## Reproduction and publication

Build with JDK 25.0.2, targeting Java 17:

```text
python -B tools/legacy_fabric_164.py --java-home C:/Tools/jdk-25.0.2
```

The build emits the deterministic JAR, source/class/dependency/recipe receipt
and runs ownership-negative policy checks. These checks do not claim a real
authenticated Steam session. Full client and native integration results belong
to the pack's QA report; two-account Steam gameplay requires actual accounts.

After committing the reviewed source, stage the new frozen twenty-target
profile without changing the active index or publishing:

```text
python -B tools/legacy_fabric_164_profile.py --source-commit <full40commit>
```

The staging command verifies that every build input exists byte for byte in
that commit, verifies the class pins, and retains all nineteen prior payload
and provenance fields. Only their active profile label advances to V3.
The new target uses the immutable `legacy-fabric-164-v1` delivery tag; its
receipt has its own size/SHA. Publish payload and receipt before the index.
Do not activate the profile or the pack card merely because compilation passed.
