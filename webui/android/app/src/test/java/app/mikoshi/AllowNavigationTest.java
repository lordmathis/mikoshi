package app.mikoshi;

import static org.junit.Assert.assertEquals;

import java.util.List;
import org.junit.Test;

public class AllowNavigationTest {

    @Test
    public void fourLabelHost_walksUpToTwoLabelFloor() {
        List<String> entries = AllowNavigation.allowNavigationFor("mikoshi.home.example.com");
        assertEquals(
            List.of("*.home.example.com", "home.example.com", "*.example.com", "example.com"),
            entries
        );
    }

    @Test
    public void threeLabelHost() {
        List<String> entries = AllowNavigation.allowNavigationFor("mikoshi.example.com");
        assertEquals(List.of("*.example.com", "example.com"), entries);
    }

    @Test
    public void twoLabelHost_emitsNothing() {
        List<String> entries = AllowNavigation.allowNavigationFor("example.com");
        assertEquals(List.of(), entries);
    }

    @Test
    public void ipLiterals_emitNothing() {
        assertEquals(List.of(), AllowNavigation.allowNavigationFor("192.168.1.10"));
        assertEquals(List.of(), AllowNavigation.allowNavigationFor("::1"));
    }

    @Test
    public void nullAndEmpty_emitNothing() {
        assertEquals(List.of(), AllowNavigation.allowNavigationFor(null));
        assertEquals(List.of(), AllowNavigation.allowNavigationFor(""));
    }
}
