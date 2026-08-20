package com.lemzher.expgoggles;

import java.util.List;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import net.minecraft.ChatFormatting;
import net.minecraft.client.Minecraft;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.network.chat.TextComponent;
import net.minecraft.network.chat.TranslatableComponent;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.player.Player;
import net.minecraftforge.common.util.LazyOptional;
import net.minecraftforge.fluids.FluidStack;
import net.minecraftforge.fluids.capability.IFluidHandler;
import net.minecraftforge.registries.ForgeRegistries;

/**
 * Builds the extra goggle lines describing a tank's experience contents.
 *
 * <p>Deliberately written against vanilla component classes rather than Create's
 * {@code Lang} builders. Create reorganised that utility package more than once, and
 * moved it out to Catnip entirely in Create 6; depending on it would tie this mod to one
 * Create release for no benefit. Vanilla's components are stable for the whole of 1.18.2,
 * so the only Create-specific thing left in this mod is the mixin's target name.
 *
 * <p>Client-side only: it is reached solely from the goggle overlay, which never runs on a
 * server, and it reads the local player to work out the projection.
 */
public final class ExperienceTooltip {

    private static final Logger LOGGER = LogManager.getLogger("expgoggles");

    /** Logged once, so a silent mod can be told apart from an attached hook seeing no experience. */
    private static final AtomicBoolean ANNOUNCED = new AtomicBoolean();

    /** Create indents goggle lines by four spaces, plus one per indent level. */
    private static final String INDENT = "     ";

    private ExperienceTooltip() {}

    /**
     * Appends the experience readout for whatever the handler is holding.
     * Does nothing when the tank holds no recognised experience fluid.
     */
    public static void append(List<Component> tooltip, boolean isPlayerSneaking,
                              LazyOptional<IFluidHandler> capability) {
        if (ANNOUNCED.compareAndSet(false, true)) {
            LOGGER.info("Goggle hook is attached and running.");
        }

        if (!ExpGogglesConfig.showLevels()) {
            return;
        }

        IFluidHandler tank = capability.resolve().orElse(null);
        if (tank == null) {
            return;
        }

        // Sum every experience fluid in the block. Multi-tank machines can hold more than
        // one, and a machine holding Liquid and Hyper at once should read as their total.
        long points = 0L;
        long millibuckets = 0L;
        for (int i = 0; i < tank.getTanks(); i++) {
            FluidStack stack = tank.getFluidInTank(i);
            if (stack.isEmpty()) {
                continue;
            }
            ExperienceFluids.Ratio ratio = ratioOf(stack);
            if (ratio == null) {
                continue;
            }
            points += ratio.pointsFor(stack.getAmount());
            millibuckets += stack.getAmount();
        }

        if (points <= 0L) {
            return;
        }

        appendWorth(tooltip, points, millibuckets);
        appendProjection(tooltip, isPlayerSneaking, points);
    }

    /** "30 levels", plus the raw point count when a millibucket is not simply one point. */
    private static void appendWorth(List<Component> tooltip, long points, long millibuckets) {
        int level = ExperienceMath.levelForXp(points);

        MutableComponent line = translate(level == 1 ? "level" : "levels", number(level))
                .withStyle(ChatFormatting.GOLD);

        // For Liquid Experience the millibuckets already are the point count, so repeating
        // it would be noise. Hyper Experience and foreign fluids genuinely differ.
        if (points != millibuckets) {
            line.append(new TextComponent("  "))
                .append(translate("points", number(points)).withStyle(ChatFormatting.DARK_GRAY));
        }

        addLine(tooltip, line);
    }

    /** "You: 12 -> 34 (+22)" — where the tank would leave the player who is looking at it. */
    private static void appendProjection(List<Component> tooltip, boolean isPlayerSneaking, long points) {
        if (!ExpGogglesConfig.showProjection()) {
            return;
        }
        if (ExpGogglesConfig.projectionRequiresSneak() && !isPlayerSneaking) {
            return;
        }

        Player player = Minecraft.getInstance().player;
        if (player == null) {
            return;
        }

        int before = player.experienceLevel;
        long carried = ExperienceMath.playerExperience(before, player.experienceProgress);
        int after = ExperienceMath.levelForXp(carried + points);

        MutableComponent line = translate("projection", number(before), number(after))
                .withStyle(ChatFormatting.GREEN)
                .append(new TextComponent(" "))
                .append(translate("gain", number(after - before)).withStyle(ChatFormatting.DARK_GRAY));

        addLine(tooltip, line);
    }

    private static void addLine(List<Component> tooltip, MutableComponent content) {
        tooltip.add(new TextComponent(INDENT).append(content));
    }

    private static MutableComponent translate(String key, Object... args) {
        return new TranslatableComponent(ExpGoggles.ID + "." + key, args);
    }

    private static String number(long value) {
        return String.format(Locale.ROOT, "%,d", value);
    }

    private static ExperienceFluids.Ratio ratioOf(FluidStack stack) {
        ResourceLocation id = ForgeRegistries.FLUIDS.getKey(stack.getFluid());
        return id == null ? null : ExperienceFluids.get(id.toString());
    }
}
