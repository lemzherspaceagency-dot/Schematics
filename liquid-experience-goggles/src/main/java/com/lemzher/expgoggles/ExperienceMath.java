package com.lemzher.expgoggles;

/**
 * The vanilla experience curve, and its inverse.
 *
 * <p>These are the same formulas Minecraft uses in {@code Player}, unchanged since 1.8:
 * a level costs {@code 2L+7} below 15, {@code 5L-38} from 15 to 29, and {@code 9L-158}
 * from 30 up. Create: Enchantment Industry mirrors them in its own {@code ExperienceHelper},
 * so a tank's contents convert exactly the way the mod would award them.
 *
 * <p>All totals are computed in {@code long}. A tank can legitimately hold up to
 * {@link Integer#MAX_VALUE} mB, and the cumulative cost of the resulting level
 * (around 21,800) overflows a 32-bit int.
 */
public final class ExperienceMath {

    private ExperienceMath() {}

    /** Experience points needed to get from {@code level} to {@code level + 1}. */
    public static int xpForNextLevel(int level) {
        if (level >= 30) return 9 * level - 158;
        if (level >= 15) return 5 * level - 38;
        return 2 * level + 7;
    }

    /** Cumulative experience points needed to reach {@code level} from zero. */
    public static long xpForTotalLevel(int level) {
        if (level <= 0) return 0L;
        long l = level;
        if (level >= 31) return (9L * l * l - 325L * l) / 2L + 2220L;
        if (level >= 16) return (5L * l * l - 81L * l) / 2L + 360L;
        return l * l + 6L * l;
    }

    /**
     * The level a given number of experience points reaches.
     *
     * <p>Solved by the closed-form root of the cumulative curve, then corrected onto the
     * exact integer boundary. The correction is not optional: {@code Math.sqrt} lands a
     * fraction below the true root for inputs that sit exactly on a level boundary, which
     * would report 29 for a tank holding precisely enough for level 30.
     */
    public static int levelForXp(long points) {
        if (points <= 0L) return 0;
        double x = (double) points;
        double approx;
        if (points < 352L)       approx = -3.0 + Math.sqrt(9.0 + x);
        else if (points < 1507L) approx = (Math.sqrt(40.0 * x - 7839.0) + 81.0) / 10.0;
        else                     approx = (Math.sqrt(72.0 * x - 54215.0) + 325.0) / 18.0;

        int level = (int) Math.floor(approx);
        if (level < 0) level = 0;
        while (level > 0 && xpForTotalLevel(level) > points) level--;
        while (xpForTotalLevel(level + 1) <= points) level++;
        return level;
    }

    /** Experience points a player is carrying, counting the partial bar. */
    public static long playerExperience(int experienceLevel, float experienceProgress) {
        return xpForTotalLevel(experienceLevel)
                + Math.round(experienceProgress * xpForNextLevel(experienceLevel));
    }
}
