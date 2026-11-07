package link.e4steam.legacy164;

import link.e4steam.E4steamClient;
import link.e4steam.retro.RetroBootstrap;
import link.e4steam.steam.SteamSession;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

/** Rich controls on native 1.6.4 chat lines; no browser links or global text matching. */
public final class LegacySharingChat {
    private static final AtomicInteger NEXT_ID = new AtomicInteger(0x4e410000);
    private static final Map<Integer, Message> MESSAGES = new HashMap<>();
    private record Action(int start, int end, String command) {}
    private record Message(SteamSession session, String plain, List<Action> actions) {}

    public static void show(String endpoint) {
        SteamSession session = E4steamClient.session;
        if (session == null || session.state() != SteamSession.State.STARTED) return;
        boolean russian = "ru_RU".equals(LegacyMessages.language(R.minecraft()));
        String invite = russian ? "[Пригласить друзей Steam]" : "[Invite Steam friends]";
        String stop = russian ? "[Закрыть доступ]" : "[Stop sharing]";
        Object chat = chat();
        MESSAGES.clear();
        R.call(chat,"method_898",russian ? "Адрес Steam готов:" : "Steam address ready:");
        String address = "[" + endpoint + "]";
        print(chat, session, "\u00a7a" + address + "\u00a7r", address,
            List.of(new Action(0,address.length(),"/e4steam copy")));
        String buttons = invite + " " + stop;
        print(chat, session, "\u00a79" + invite + " \u00a7c" + stop + "\u00a7r", buttons,
            List.of(new Action(0,invite.length(),"/e4steam invite"),
                new Action(invite.length()+1,buttons.length(),"/e4steam stop")));
    }

    private static void print(Object chat, SteamSession session, String formatted, String plain, List<Action> actions) {
        int id = NEXT_ID.incrementAndGet();
        MESSAGES.put(id,new Message(session,plain,actions));
        R.call(chat,"method_899",formatted,id);
    }

    private static Object chat() { return R.call(R.get(R.minecraft(),"field_3820"),"method_983"); }
    static String plain(String text) { return text.replaceAll("\u00a7.",""); }

    static String commandAt(String full, List<String> fragments, int fragment, int x,
                            List<String> labels, List<String> commands,
                            java.util.function.ToIntFunction<String> width) {
        int cursor=0;
        for(int index=0;index<fragments.size();index++) {
            String text=plain(fragments.get(index));
            int offset=full.indexOf(text,cursor);
            if(offset<0)return null;
            cursor=offset+text.length();
            if(index!=fragment)continue;
            for(int action=0;action<labels.size();action++) {
                int start=full.indexOf(labels.get(action));
                int from=Math.max(start,offset),to=Math.min(start+labels.get(action).length(),cursor);
                if(start>=0&&from<to&&x>=width.applyAsInt(text.substring(0,from-offset))
                        &&x<width.applyAsInt(text.substring(0,to-offset)))return commands.get(action);
            }
        }
        return null;
    }

    public static boolean click(int button) {
        if(button!=0)return false;
        Object mouse=R.type("org.lwjgl.input.Mouse");
        return clickAt((Integer)R.call(mouse,"getX"),(Integer)R.call(mouse,"getY"),button);
    }

    public static boolean clickAt(int x, int y, int button) {
        if(button!=0)return false;
        Object chat=chat();
        Object hit=R.call(chat,"method_897",x,y);
        if(hit==null)return false;
        Object line=R.get(hit,"field_1175");
        int id=(Integer)R.call(line,"method_836");
        Message message=MESSAGES.get(id);
        if(message==null)return false;
        if(E4steamClient.session!=message.session || message.session.state()!=SteamSession.State.STARTED) {
            MESSAGES.remove(id);return false;
        }
        List<Object> lines=new ArrayList<>();
        for(Object candidate:(List<?>)R.get(chat,"field_5713"))
            if(((Integer)R.call(candidate,"method_836"))==id)lines.add(candidate);
        Collections.reverse(lines);
        List<String> fragments=new ArrayList<>();
        int fragment=-1;
        for(int index=0;index<lines.size();index++) {
            if(lines.get(index)==line)fragment=index;
            fragments.add((String)R.call(lines.get(index),"method_834"));
        }
        Object font=R.get(R.minecraft(),"field_3814");
        List<String> labels=new ArrayList<>(),commands=new ArrayList<>();
        for(Action action:message.actions) {
            labels.add(message.plain.substring(action.start,action.end));commands.add(action.command);
        }
        String command=commandAt(message.plain,fragments,fragment,(Integer)R.get(hit,"field_1176"),
            labels,commands,text -> (Integer)R.call(font,"method_954",text));
        return command!=null&&RetroBootstrap.handleClientCommand(command);
    }
    private LegacySharingChat() {}
}
