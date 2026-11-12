package link.e4steam.retro.forge;

import java.util.Objects;
import link.e4steam.steam.SteamLanWorld;
import net.minecraft.client.server.LanServer;

/** A Steam result in the native transient list, separate from saved ServerData. */
public final class LauncherLanServer extends LanServer {
    private final String worldName;

    public LauncherLanServer(SteamLanWorld world) {
        super(world.playerName(), world.address());
        worldName = world.worldName();
    }

    public String worldName() {
        return worldName;
    }

    @Override
    public boolean equals(Object other) {
        if (!(other instanceof LauncherLanServer)) return false;
        LauncherLanServer entry = (LauncherLanServer) other;
        return getAddress().equals(entry.getAddress())
                && getMotd().equals(entry.getMotd())
                && worldName.equals(entry.worldName);
    }

    @Override
    public int hashCode() {
        return Objects.hash(getAddress(), getMotd(), worldName);
    }
}
