package link.e4steam.legacy164;

public final class LegacyMessages {
    private LegacyMessages() {}

    public static String language(Object minecraft) {
        Object manager = R.call(minecraft, "method_5573");
        return (String) R.call(R.call(manager, "method_5942"), "method_5935");
    }

    public static String publishKey(String language, String nativeKey) {
        // The 1.6.4 translator formats an unknown key as a literal template.
        // Retain the port argument and the original key for every other locale.
        return "ru_RU".equals(language) && "commands.publish.started".equals(nativeKey)
            ? "Порт локального сервера: %s" : nativeKey;
    }

    public static String reportsTitle(String language) {
        return "ru_RU".equals(language) ? "Жалобы" : "Player Reporting";
    }

    public static String reportsUnavailable(String language) {
        return "ru_RU".equals(language)
            ? "Жалобы на игроков в этой версии недоступны."
            : "Player reporting is unavailable in this version.";
    }

    public static Object[] commandNames(String key, Object[] values) {
        if (key == null || !key.startsWith("commands.") || values == null) return values;
        Object[] result = values;
        for (int index = 0; index < values.length; index++) {
            if (!(values[index] instanceof String name)) continue;
            String display = LegacyRegistry.displayName(name);
            if (display.equals(name)) continue;
            if (result == values) result = values.clone();
            result[index] = display;
        }
        return result;
    }
}
