package link.e4steam.retro.forge;

import link.e4steam.steam.SteamLanWorld;
import net.minecraft.client.network.LanServerInfo;

/** A transient multiplayer row with no token or saved server-file entry. */
public final class SteamLanServerInfo112 extends LanServerInfo {
    private final String title;

    public SteamLanServerInfo112(SteamLanWorld world) {
        super(world.playerName(), world.address());
        title = world.worldName();
    }

    public String title() { return title; }
}
