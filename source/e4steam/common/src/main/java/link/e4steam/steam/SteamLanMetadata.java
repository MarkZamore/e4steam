package link.e4steam.steam;

import com.codedisaster.steamworks.SteamID;
import com.codedisaster.steamworks.SteamMatchmaking;

import java.util.Map;
import java.util.WeakHashMap;

/** Metadata belongs to one hosting generation and is published before it is joinable. */
public final class SteamLanMetadata {
    private static final Map<SteamSession, SteamLanWorld> DESCRIPTIONS = new WeakHashMap<>();

    private SteamLanMetadata() { }

    public static synchronized void describe(SteamSession owner, String worldName, String playerName) {
        SteamLanWorld description = new SteamLanWorld(0, 0, worldName, playerName);
        if (!description.worldName().isEmpty() && !description.playerName().isEmpty()) {
            DESCRIPTIONS.put(owner, description);
        }
    }

    static boolean publish(SteamSession owner, SteamMatchmaking matchmaking, SteamID lobby) {
        SteamLanWorld description;
        synchronized (SteamLanMetadata.class) {
            description = DESCRIPTIONS.get(owner);
        }
        if (description == null) return true;
        return matchmaking.setLobbyData(lobby, SteamLanWorld.WORLD_KEY, description.worldName())
                && matchmaking.setLobbyData(lobby, SteamLanWorld.PLAYER_KEY, description.playerName())
                && matchmaking.setLobbyData(lobby, SteamLanWorld.DISPLAY_KEY, "1");
    }
}
