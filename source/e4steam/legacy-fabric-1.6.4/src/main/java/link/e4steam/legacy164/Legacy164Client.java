package link.e4steam.legacy164;

import net.fabricmc.api.ClientModInitializer;
import link.e4steam.retro.RetroBootstrap;
import link.e4steam.retro.RetroPlatform;
import java.lang.ref.WeakReference;
import java.net.InetSocketAddress;
import java.util.concurrent.ConcurrentLinkedQueue;

public final class Legacy164Client implements ClientModInitializer,RetroPlatform {
    private static final ConcurrentLinkedQueue<Runnable> TASKS=new ConcurrentLinkedQueue<>();
    private static WeakReference<Object> reportsNotice = new WeakReference<>(null);
    @Override public void onInitializeClient(){RetroBootstrap.install("1.6.4",this);System.out.println("[e4steam Legacy164] Source-built transport initialized.");}
    @Override public void execute(Runnable action){TASKS.add(action);}
    public static void tick(){Runnable task;int count=0;while(count++<1024&&(task=TASKS.poll())!=null)task.run();}
    public static void submit(Runnable action){TASKS.add(action);}
    @Override public void connect(InetSocketAddress local,String name) {
        Object mc=R.minecraft(),parent=R.get(mc,"field_3816");
        Object screen=R.create("net.minecraft.class_472",parent,mc,local.getAddress().getHostAddress(),local.getPort());
        R.call(mc,"method_2928",screen);
    }
    @Override public void showMessage(String message){
        Object gui=R.get(R.minecraft(),"field_3820");
        if(gui!=null)R.call(R.call(gui,"method_983"),"method_898",message);
    }
    @Override public boolean copyToClipboard(String text){R.call(R.type("net.minecraft.class_388"),"method_1036",text);return true;}
    @Override public boolean tracksMinecraftLogin(){return true;}
    @Override public void joinTimedOut(String reason){
        Object mc=R.minecraft(),screen=R.get(mc,"field_3816");
        if(screen!=null&&screen.getClass().getName().equals("net.minecraft.class_472")){
            link.e4steam.steam.SteamRuntime.get().cancelClientConnection();
            Object handler=R.get(screen,"field_1631");if(handler!=null)R.call(handler,"method_1204");
        }
        new Legacy164Client().showMessage(reason);
    }
    public static void updatePauseAction(Object screen) {
        Object mc = R.get(screen, "field_1229");
        if (!Boolean.TRUE.equals(R.call(mc, "method_2908"))) return;
        Object server = R.call(mc, "method_2909");
        if (server == null || !Boolean.TRUE.equals(R.call(server, "method_1638"))) return;
        for (Object button : (java.util.List<?>) R.get(screen, "field_1232")) {
            if (((Integer) R.get(button, "field_1054")) == 7) {
                R.set(button, "field_1053", LegacyMessages.reportsTitle(LegacyMessages.language(mc)));
                return;
            }
        }
    }
    public static boolean isReportsNotice(Object screen) {
        return reportsNotice.get() == screen;
    }
    public static boolean handlePauseAction(Object screen,Object button){
        if(((Integer)R.get(button,"field_1054"))!=7||!Boolean.TRUE.equals(R.get(button,"field_1055")))return false;
        Object mc=R.get(screen,"field_1229");
        if (!Boolean.TRUE.equals(R.call(mc, "method_2908"))) return false;
        Object server=R.call(mc,"method_2909");
        if(server==null)return false;
        if (Boolean.TRUE.equals(R.call(server, "method_1638"))) {
            String language = LegacyMessages.language(mc);
            // This native notice wraps the message and returns to the exact
            // pause screen. It has no side effect on the world or reports.
            Object notice = R.create("net.minecraft.class_475", screen,
                LegacyMessages.reportsTitle(language), LegacyMessages.reportsUnavailable(language), new Object[0]);
            reportsNotice = new WeakReference<>(notice);
            R.call(mc, "method_2928", notice);
            return true;
        }
        // Initialize the native screen and invoke its native Start action;
        // loader/mod callbacks retain ownership of the publication settings.
        Object share=R.create("net.minecraft.class_393",screen);
        R.call(share,"method_1028",mc,R.get(screen,"field_1230"),R.get(screen,"field_1231"));
        for(Object action:(java.util.List<?>)R.get(share,"field_1232"))if(((Integer)R.get(action,"field_1054"))==101&&Boolean.TRUE.equals(R.get(action,"field_1055"))){R.call(share,"method_1027",action);return true;}
        throw new IllegalStateException("The native Share Start action is unavailable");
    }
}
