package com.lemzher.expgoggles;

import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Which fluids count as experience, and how much a millibucket of each is worth.
 *
 * <p>The two built-in entries are read from Create: Enchantment Industry's own source.
 * {@code ExperienceFluid} is constructed with {@code xpRatio = 1} and
 * {@code HyperExperienceFluid} calls {@code super(10, properties)}, so Liquid Experience
 * is 1 point per mB and Liquid Hyper Experience is 10. Those ratios are identical on every
 * CEI release for 1.18.2 through 1.21.1; the Hyper fluid simply stops existing in CEI 2.x.
 *
 * <p>Ratios are kept as an exact {@code points/millibuckets} fraction rather than a
 * double, because other mods' experience fluids run the other way — 20 or 25 mB to the
 * point — and rounding those would misreport a tank by whole levels.
 */
public final class ExperienceFluids {

    /** An exact points-per-millibucket ratio. */
    public record Ratio(int points, int millibuckets) {
        public long pointsFor(long amount) {
            return amount * points / millibuckets;
        }

        /** True when a millibucket is worth exactly one point, i.e. mB and XP read the same. */
        public boolean isOneToOne() {
            return points == millibuckets;
        }
    }

    private static final Map<String, Ratio> BUILT_IN = Map.of(
            "create_enchantment_industry:experience", new Ratio(1, 1),
            "create_enchantment_industry:hyper_experience", new Ratio(10, 1)
    );

    private static volatile Map<String, Ratio> ratios = new HashMap<>(BUILT_IN);

    private ExperienceFluids() {}

    /** The ratio for a fluid id, or {@code null} if it is not an experience fluid. */
    public static Ratio get(String fluidId) {
        return ratios.get(fluidId);
    }

    /**
     * Rebuilds the lookup from the built-in entries plus user-configured ones.
     * Config entries win, so a pack can correct a ratio without a code change.
     *
     * <p>Accepted forms: {@code modid:fluid=10} (10 points per mB) and
     * {@code modid:fluid=1/20} (1 point per 20 mB).
     */
    public static void reload(List<? extends String> extra) {
        Map<String, Ratio> next = new HashMap<>(BUILT_IN);
        for (String entry : extra) {
            Ratio parsed = parse(entry);
            if (parsed != null) {
                next.put(key(entry), parsed);
            }
        }
        ratios = next;
    }

    private static String key(String entry) {
        return entry.substring(0, entry.indexOf('=')).trim().toLowerCase(Locale.ROOT);
    }

    private static Ratio parse(String entry) {
        int eq = entry.indexOf('=');
        if (eq <= 0 || eq == entry.length() - 1) return null;
        String value = entry.substring(eq + 1).trim();
        try {
            int slash = value.indexOf('/');
            int points = Integer.parseInt(slash < 0 ? value : value.substring(0, slash).trim());
            int millibuckets = slash < 0 ? 1 : Integer.parseInt(value.substring(slash + 1).trim());
            if (points <= 0 || millibuckets <= 0) return null;
            return new Ratio(points, millibuckets);
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
