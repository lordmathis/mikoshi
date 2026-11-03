package app.mikoshi;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public final class AllowNavigation {

    private AllowNavigation() {}

    public static List<String> allowNavigationFor(String host) {
        List<String> entries = new ArrayList<>();
        if (host == null || host.isEmpty() || host.contains(":")) {
            return entries;
        }
        String[] labels = host.split("\\.");
        if (isIpv4(labels)) {
            return entries;
        }
        for (int i = 1; i <= labels.length - 2; i++) {
            String suffix = String.join(".", Arrays.copyOfRange(labels, i, labels.length));
            entries.add("*." + suffix);
            entries.add(suffix);
        }
        return entries;
    }

    private static boolean isIpv4(String[] labels) {
        if (labels.length != 4) {
            return false;
        }
        for (String label : labels) {
            if (!label.matches("\\d{1,3}")) {
                return false;
            }
        }
        return true;
    }
}
