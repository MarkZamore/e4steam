package link.e4steam.legacy164;

import link.e4steam.steam.SteamRuntime;
import java.lang.ref.WeakReference;
import java.util.*;
import java.util.concurrent.*;

/** Transient Steam friends' worlds inside the native 1.6.4 multiplayer list. */
public final class LegacyDiscovery {
    private static final String PREFIX="e4steam-legacy-";
    private static final Map<Object,Poll> POLLS=Collections.synchronizedMap(new WeakHashMap<>());
    private static final Map<Object,Poll> MANAGED_LISTS=Collections.synchronizedMap(new WeakHashMap<>());
    private static final Map<Object,World> DISPLAY_ENTRIES=Collections.synchronizedMap(new WeakHashMap<>());
    private record World(long lobby,long friend,String player,String world){String address(){return PREFIX+Long.toUnsignedString(lobby)+".invalid";}}
    private LegacyDiscovery(){}
    public static void begin(Object screen){synchronized(POLLS){Poll existing=POLLS.get(screen);if(existing!=null){existing.apply(existing.worlds);return;}Poll p=new Poll(screen);POLLS.put(screen,p);p.apply(Map.of());p.thread.start();}}
    public static void end(Object screen){Poll p=POLLS.remove(screen);if(p!=null){p.close();synchronized(MANAGED_LISTS){MANAGED_LISTS.values().removeIf(value->value==p);}}}
    public static boolean nativeDiscoveryManaged(Object list){Poll p=MANAGED_LISTS.get(list);return p!=null&&p.active&&p.screen.get()!=null;}
    public static boolean managedScreen(Object screen){Poll p=POLLS.get(screen);return p!=null&&p.active;}
    public static String worldTitle(String original,Object entry){World world=DISPLAY_ENTRIES.get(entry);return world==null?original:world.world;}
    public static String displayAddress(String original,Object entry){return DISPLAY_ENTRIES.containsKey(entry)?"Steam":original;}
    public static Object entryAt(Object renderer,int index){Object screen=R.get(renderer,"field_1200");List<?> entries=(List<?>)R.get(screen,"field_1181");int offset=(Integer)R.call(R.get(screen,"field_1186"),"method_1281");return entries.get(index-offset);}
    /** Exact common display protocol, with no Steam-persona fallback. */
    public static String[] description(String enabled,String player,String world){if(!"1".equals(enabled))return null;player=LegacyPublication.cleanName(player);world=LegacyPublication.cleanName(world);return player.isEmpty()||world.isEmpty()?null:new String[]{player,world};}
    public static boolean join(Object screen,Object data){
        String address=(String)R.get(data,"field_1687");if(!address.startsWith(PREFIX))return false;
        Poll p=POLLS.get(screen);World w=p==null?null:p.worlds.get(address);
        if(w!=null&&p.active)submit(p.runtime,()->{
            Object social=R.get(p.runtime,"lobbyManager");
            if(social!=null)R.call(social,"requestJoin",steamId(w.lobby),steamId(w.friend),false);
            return null;
        });
        return true; // A stale synthetic entry must never reach DNS or plain TCP.
    }
    private static Object steamId(long id){return R.call(R.type("com.codedisaster.steamworks.SteamID"),"createFromNativeHandle",id);}
    @SuppressWarnings("unchecked") private static <T> CompletableFuture<T> submit(SteamRuntime runtime,Callable<T> action){return (CompletableFuture<T>)R.call(runtime,"submitSteamTask",action);}
    private static long nativeId(Object id){return (Long)R.call(R.type("com.codedisaster.steamworks.SteamNativeHandle"),"getNativeHandle",id);}
    private static final class Poll implements Runnable,AutoCloseable {
        final WeakReference<Object> screen;final SteamRuntime runtime=SteamRuntime.get();final SteamRuntime.Activity lease;
        final Thread thread;volatile boolean active=true;volatile Map<String,World> worlds=Map.of();
        Poll(Object screen){this.screen=new WeakReference<>(screen);lease=runtime.acquireActivity();thread=new Thread(this,"e4steam-legacy-world-discovery");thread.setDaemon(true);}
        @Override public void run(){
            boolean reported=false;
            try {
                while(active&&screen.get()!=null){
                    try {
                        runtime.awaitReady();Map<String,World> found=submit(runtime,this::read).get(8,TimeUnit.SECONDS);
                        if(!found.equals(worlds)){worlds=found;Legacy164Client.submit(()->apply(found));}reported=false;
                    }catch(InterruptedException stopped){Thread.currentThread().interrupt();return;}
                    catch(Exception failure){if(!active)return;if(!reported)System.err.println("[e4steam Legacy164] Steam discovery temporarily unavailable: "+failure.getClass().getSimpleName());reported=true;if(!worlds.isEmpty()){worlds=Map.of();Legacy164Client.submit(()->apply(Map.of()));}}
                    try{Thread.sleep(3000);}catch(InterruptedException stopped){Thread.currentThread().interrupt();return;}
                }
            }finally{lease.close();}
        }
        Map<String,World> read(){
            Map<String,World> found=new LinkedHashMap<>();Object social=R.get(runtime,"lobbyManager");if(social==null)return Map.of();
            Object friends=R.get(social,"friends"),matchmaking=R.get(social,"matchmaking");Object immediate=R.get(R.type("com.codedisaster.steamworks.SteamFriends$FriendFlags"),"Immediate");
            int count=Math.min(2048,(Integer)R.call(friends,"getFriendCount",immediate));String protocol=String.valueOf(R.get(R.type("link.e4steam.steam.SteamProtocol"),"VERSION"));
            for(int i=0;active&&i<count;i++){
                Object friend=R.call(friends,"getFriendByIndex",i,immediate);if(friend==null)continue;
                R.call(friends,"requestFriendRichPresence",friend);String connect=(String)R.call(friends,"getFriendRichPresence",friend,"connect");
                if(connect==null||!connect.matches("e4steam-lobby:[1-9][0-9]{0,19}"))continue;
                long lobby;try{lobby=Long.parseUnsignedLong(connect.substring("e4steam-lobby:".length()));}catch(NumberFormatException invalid){continue;}
                Object id=steamId(lobby);R.call(matchmaking,"requestLobbyData",id);
                if(!protocol.equals(R.call(matchmaking,"getLobbyData",id,"e4steam_protocol"))||!"1.6.4".equals(R.call(matchmaking,"getLobbyData",id,"e4steam_minecraft")))continue;
                Object owner=R.call(matchmaking,"getLobbyOwner",id);long peer=nativeId(friend);if(owner==null||nativeId(owner)!=peer)continue;
                String[] description=description((String)R.call(matchmaking,"getLobbyData",id,LegacyPublication.DISPLAY_KEY),(String)R.call(matchmaking,"getLobbyData",id,LegacyPublication.PLAYER_KEY),(String)R.call(matchmaking,"getLobbyData",id,LegacyPublication.WORLD_KEY));
                if(description==null)continue;
                World world=new World(lobby,peer,description[0],description[1]);found.put(world.address(),world);
            }
            return Map.copyOf(found);
        }
        @SuppressWarnings("unchecked") void apply(Map<String,World> found){
            Object current=screen.get();if(!active||current==null||POLLS.get(current)!=this)return;
            Object list=R.get(current,"field_1197");if(list==null)return;
            synchronized(MANAGED_LISTS){MANAGED_LISTS.values().removeIf(value->value==this);MANAGED_LISTS.put(list,this);}
            synchronized(list){
                List<Object> servers=(List<Object>)R.get(list,"field_2225");servers.clear();
                for(World w:found.values()){Object value=R.create("net.minecraft.class_606",w.player,w.address());DISPLAY_ENTRIES.put(value,w);servers.add(value);}
                R.set(list,"field_2224",true);
            }
        }
        @Override public void close(){active=false;thread.interrupt();lease.close();}
    }
}
