package link.e4steam.lan;

/** The existing retro Steam lobby capacity, including the local world owner. */
public final class LanSettings {
    private static final int LOBBY_CAPACITY = 8;

    private LanSettings() { }

    public static int steamLobbyCapacity() { return LOBBY_CAPACITY; }

    public static int steamGuestLimit() { return LOBBY_CAPACITY - 1; }
}
