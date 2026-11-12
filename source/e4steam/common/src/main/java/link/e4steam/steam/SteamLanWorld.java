package link.e4steam.steam;

/** One authenticated friend's world advertised by the launcher. */
public final class SteamLanWorld {
    static final String PLAYER_KEY = "lanminecraft_player";
    static final String WORLD_KEY = "lanminecraft_world";
    static final String DISPLAY_KEY = "lanminecraft_display";
    private final long lobbyId;
    private final long friendId;
    private final String worldName;
    private final String playerName;

    SteamLanWorld(long lobbyId, long friendId, String worldName, String playerName) {
        this.lobbyId = lobbyId;
        this.friendId = friendId;
        this.worldName = clean(worldName);
        this.playerName = clean(playerName);
    }

    public long lobbyId() { return lobbyId; }
    public long friendId() { return friendId; }
    public String worldName() { return worldName; }
    public String playerName() { return playerName; }
    public String address() {
        return "portable-steam-" + Long.toUnsignedString(lobbyId) + "-" + Long.toUnsignedString(friendId);
    }

    static String clean(String value) {
        if (value == null) return "";
        String cleaned = value.replaceAll("[\\p{Cc}\\p{Cf}]", "").trim();
        return cleaned.length() <= 96 ? cleaned : cleaned.substring(0, 96);
    }
}
