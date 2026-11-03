package app.mikoshi;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import androidx.appcompat.app.AppCompatActivity;
import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeWebViewClient;

public class FallbackWebViewClient extends BridgeWebViewClient {

    private final Bridge capBridge;
    private final AppCompatActivity activity;

    public FallbackWebViewClient(Bridge bridge, AppCompatActivity activity) {
        super(bridge);
        this.capBridge = bridge;
        this.activity = activity;
    }

    @Override
    public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
        super.onReceivedError(view, request, error);
        if (!request.isForMainFrame() || capBridge.getServerUrl() == null) {
            return;
        }
        SharedPreferences prefs = activity.getSharedPreferences(
            ServerConfigPlugin.PREFS,
            Context.MODE_PRIVATE
        );
        prefs.edit().putBoolean(ServerConfigPlugin.KEY_FALLBACK, true).apply();
        new Handler(Looper.getMainLooper()).post(activity::recreate);
    }
}
