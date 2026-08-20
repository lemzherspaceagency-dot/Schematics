package com.lemzher.expgoggles;

import java.util.List;

import net.minecraftforge.common.ForgeConfigSpec;
import net.minecraftforge.fml.event.config.ModConfigEvent;

/** Client-side settings. Nothing here is synced, because nothing here leaves this client. */
public final class ExpGogglesConfig {

    public static final ForgeConfigSpec SPEC;

    private static final ForgeConfigSpec.BooleanValue SHOW_LEVELS;
    private static final ForgeConfigSpec.BooleanValue SHOW_PROJECTION;
    private static final ForgeConfigSpec.BooleanValue PROJECTION_NEEDS_SNEAK;
    private static final ForgeConfigSpec.ConfigValue<List<? extends String>> EXTRA_FLUIDS;

    static {
        ForgeConfigSpec.Builder builder = new ForgeConfigSpec.Builder();

        builder.comment("Liquid Experience Goggles — all settings are client-side only.")
                .push("goggles");

        SHOW_LEVELS = builder
                .comment("Show what a tank's experience fluid is worth in levels.")
                .define("showLevels", true);

        SHOW_PROJECTION = builder
                .comment("Also show the level you would reach if you drank the whole tank.")
                .define("showProjection", true);

        PROJECTION_NEEDS_SNEAK = builder
                .comment("Only show that projection while sneaking, matching Create's other",
                         "sneak-to-expand goggle tooltips.")
                .define("projectionRequiresSneak", true);

        builder.pop();

        builder.comment("Experience fluids from other mods, as 'modid:fluid=points' or",
                        "'modid:fluid=points/millibuckets'. For example 'cofh_core:experience=1/25'",
                        "means 25 mB is worth one experience point. Create: Enchantment Industry's",
                        "own fluids are built in and do not need an entry here.")
                .push("fluids");

        EXTRA_FLUIDS = builder.defineList("additionalExperienceFluids",
                List.of(),
                entry -> entry instanceof String s && s.indexOf('=') > 0);

        builder.pop();

        SPEC = builder.build();
    }

    private ExpGogglesConfig() {}

    public static boolean showLevels() {
        return SHOW_LEVELS.get();
    }

    public static boolean showProjection() {
        return SHOW_PROJECTION.get();
    }

    public static boolean projectionRequiresSneak() {
        return PROJECTION_NEEDS_SNEAK.get();
    }

    public static void onLoad(final ModConfigEvent.Loading event) {
        refresh(event);
    }

    public static void onReload(final ModConfigEvent.Reloading event) {
        refresh(event);
    }

    private static void refresh(final ModConfigEvent event) {
        if (event.getConfig().getSpec() == SPEC) {
            ExperienceFluids.reload(EXTRA_FLUIDS.get());
        }
    }
}
