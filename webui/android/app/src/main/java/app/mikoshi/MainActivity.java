package app.mikoshi;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.CapConfig;
import java.util.List;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Config and plugin registration must precede super.onCreate():
        // BridgeActivity builds the Bridge inside it, and later additions
        // are silent no-ops.
        SharedPreferences prefs = getSharedPreferences(ServerConfigPlugin.PREFS, Context.MODE_PRIVATE);
        String url = prefs.getString(ServerConfigPlugin.KEY_URL, null);
        boolean fallback = prefs.getBoolean(ServerConfigPlugin.KEY_FALLBACK, false);
        if (url != null && !fallback) {
            List<String> allowNavigation = AllowNavigation.allowNavigationFor(Uri.parse(url).getHost());
            this.config = new CapConfig.Builder(this)
                .setServerUrl(url)
                .setAllowNavigation(allowNavigation.toArray(new String[0]))
                .create();
        }
        registerPlugin(ServerConfigPlugin.class);
        super.onCreate(savedInstanceState);
        bridge.setWebViewClient(new FallbackWebViewClient(bridge, this));
    }
}
