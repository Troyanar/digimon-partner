package de.knuschti.partner;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.Settings;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONArray;

/**
 * Digimon-Gerät: zeigt die Partner-Seite im Vollbild auf einem eigenen Handy.
 * Bildschirm bleibt an, Ton ohne Antippen, Vibration und Helligkeit über window.Geraet (siehe static/device.js).
 */
public class MainActivity extends Activity {
    private static final String HOME = BuildConfig.PARTNER_URL + "/";
    private WebView web;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        web = new WebView(this);
        web.setBackgroundColor(0xFF0C0D0F);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);   // das Digimon darf sich von selbst melden
        s.setUserAgentString(s.getUserAgentString() + " DigimonGeraet/" + BuildConfig.VERSION_NAME);

        CookieManager.getInstance().setAcceptCookie(true);
        web.addJavascriptInterface(new Bridge(), "Geraet");
        web.setWebChromeClient(new WebChromeClient());   // für confirm()-Abfragen der Seite
        web.setWebViewClient(new Client());

        if (state != null) web.restoreState(state);
        else web.loadUrl(HOME);
        hideBars();
    }

    /** Eigene Seiten bleiben in der App, alles andere (z. B. die Rezepte-Seite) öffnet im Browser. */
    private class Client extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri url = request.getUrl();
            Uri home = Uri.parse(HOME);
            if (url.getHost() != null && url.getHost().equals(home.getHost())) return false;
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, url));
            } catch (Exception ignored) {
                // kein Browser vorhanden
            }
            return true;
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            if (!request.isForMainFrame()) return;
            // Kein Netz oder Server weg: kurze Meldung, nach 15 Sekunden neuer Versuch
            String html = "<html><body style='background:#0c0d0f;color:#f4f5f6;font-family:sans-serif;display:flex;"
                    + "align-items:center;justify-content:center;height:100vh;margin:0;text-align:center'>"
                    + "<div><p style='font-size:22px'>Keine Verbindung zum Digimon …</p>"
                    + "<p style='color:#a3a8b0'>Neuer Versuch in 15 Sekunden.</p></div>"
                    + "<script>setTimeout(function(){location.href='" + HOME + "'},15000)</script></body></html>";
            view.loadDataWithBaseURL(null, html, "text/html", "utf-8", null);
        }
    }

    /** Für die Seite: window.Geraet.vibrate("[200,100,200]"), window.Geraet.setBrightness(0.01 | -1) */
    private class Bridge {
        @JavascriptInterface
        public void vibrate(String json) {
            try {
                JSONArray a = new JSONArray(json);
                long[] pattern = new long[a.length() + 1];
                for (int i = 0; i < a.length(); i++) pattern[i + 1] = a.getLong(i);   // [Pause, an, aus, an, …]
                Vibrator v = (Vibrator) getSystemService(VIBRATOR_SERVICE);
                if (v == null) return;
                if (Build.VERSION.SDK_INT >= 26) v.vibrate(VibrationEffect.createWaveform(pattern, -1));
                else v.vibrate(pattern, -1);
            } catch (Exception ignored) {
                // falsches Muster: nichts tun
            }
        }

        @JavascriptInterface
        public void setBrightness(final float value) {
            runOnUiThread(() -> {
                WindowManager.LayoutParams lp = getWindow().getAttributes();
                lp.screenBrightness = value < 0 ? WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE : Math.min(1f, value);
                getWindow().setAttributes(lp);
            });
        }

        @JavascriptInterface
        public void openSettings() {
            runOnUiThread(() -> startActivity(new Intent(Settings.ACTION_SETTINGS)));
        }

        @JavascriptInterface
        public void chooseHome() {
            runOnUiThread(() -> startActivity(new Intent(Settings.ACTION_HOME_SETTINGS)));
        }
    }

    private void hideBars() {
        if (Build.VERSION.SDK_INT >= 30) {
            WindowInsetsController c = getWindow().getInsetsController();
            if (c != null) {
                c.hide(WindowInsets.Type.systemBars());
                c.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) hideBars();
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    protected void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();   // Anmeldung bleibt nach einem Neustart erhalten
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        // Ein Gerät hat kein "Zurück aus der App": nur innerhalb der Seite zurück
        if (web.canGoBack()) web.goBack();
    }
}
