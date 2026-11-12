package link.e4steam.retro.forge;

import net.minecraft.world.storage.WorldInfo;

import java.util.Collections;
import java.util.Set;
import java.util.WeakHashMap;

/** Only an integrated server's already-loaded world is protected, not world creation. */
public final class WorldCommandPolicy112 {
    private static final Set<WorldInfo> LIVE = Collections.newSetFromMap(new WeakHashMap<>());

    private WorldCommandPolicy112() { }

    public static synchronized void protect(WorldInfo world) { LIVE.add(world); }

    public static synchronized boolean protectedWorld(WorldInfo world) { return LIVE.contains(world); }
}
