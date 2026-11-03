package app.mikoshi;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "ServerConfig")
public class ServerConfigPlugin extends Plugin {

    static final String PREFS = "mikoshi_server";
    static final String KEY_URL = "server_url";
    static final String KEY_FALLBACK = "local_fallback";

    @PluginMethod
    public void getServerUrl(PluginCall call) {
        JSObject result = new JSObject();
        result.put("url", prefs().getString(KEY_URL, null));
        call.resolve(result);
    }

    @PluginMethod
    public void setServerUrl(PluginCall call) {
        String raw = call.getString("url");
        if (raw == null || raw.trim().isEmpty()) {
            call.reject("url is required");
            return;
        }
        String normalized = raw.trim();
        if (!normalized.contains("://")) {
            normalized = "https://" + normalized;
        }
        normalized = normalized.replaceAll("/+$", "");
        Uri uri = Uri.parse(normalized);
        String scheme = uri.getScheme();
        String host = uri.getHost();
        if (scheme == null || host == null || host.isEmpty()
                || (!scheme.equals("http") && !scheme.equals("https"))) {
            call.reject("Not a valid http(s) URL: " + normalized);
            return;
        }
        SharedPreferences.Editor editor = prefs().edit();
        editor.putString(KEY_URL, normalized);
        editor.putBoolean(KEY_FALLBACK, false);
        editor.apply();
        call.resolve();
        getActivity().runOnUiThread(() -> getActivity().recreate());
    }

    private SharedPreferences prefs() {
        return getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}
