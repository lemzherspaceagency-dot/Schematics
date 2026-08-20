package com.lemzher.expgoggles;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.objectweb.asm.tree.ClassNode;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;
import org.spongepowered.asm.service.MixinService;

import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.loading.FMLEnvironment;

/**
 * Picks the goggle hook that matches whichever Create is installed.
 *
 * <p>Create has moved {@code IHaveGoggleInformation} twice. The method this mod injects
 * into, {@code containedFluidTooltip(List, boolean, LazyOptional)}, is unchanged between
 * those moves, so the only thing that varies is the class to attach to. Rather than pin
 * one Create release, the mixin config declares no mixins up front and this plugin adds
 * whichever hook resolves against the classes actually on disk.
 *
 * <p>Targets are probed through the Mixin bytecode provider rather than
 * {@code Class.forName}, so nothing is class-loaded prematurely — doing that during mixin
 * setup would freeze those classes before other mods get to transform them.
 */
public class ExpGogglesMixinPlugin implements IMixinConfigPlugin {

    private static final Logger LOGGER = LogManager.getLogger("expgoggles");

    /** Create class name -> the hook that fits it, newest layout first. */
    private static final Map<String, String> HOOKS = new LinkedHashMap<>();

    static {
        // Create 0.5.1 and later (1.18.2, 1.19.2, 1.20.1)
        HOOKS.put("com.simibubi.create.content.equipment.goggles.IHaveGoggleInformation",
                "ModernGoggleMixin");
        // Create 0.5.0 and earlier, before the repackaging
        HOOKS.put("com.simibubi.create.content.contraptions.goggles.IHaveGoggleInformation",
                "LegacyGoggleMixin");
    }

    @Override
    public List<String> getMixins() {
        // Mixins contributed by a plugin bypass the config's "client" list, so the physical
        // side is checked here: on a server the hook would fail on the first client-only
        // class it touches.
        //
        // This deliberately fails OPEN. Mixin configs are processed very early, and
        // FMLEnvironment.dist can still be unset at that point; testing for "not CLIENT"
        // treats that unset value as a server and silently disables the whole mod. Only a
        // definite DEDICATED_SERVER skips.
        if (isDedicatedServer()) {
            LOGGER.info("Dedicated server detected, no goggle hooks applied.");
            return List.of();
        }

        List<String> selected = new ArrayList<>(1);
        for (Map.Entry<String, String> hook : HOOKS.entrySet()) {
            if (isPresent(hook.getKey())) {
                LOGGER.info("Create goggle interface found at {}, applying {}.",
                        hook.getKey(), hook.getValue());
                selected.add(hook.getValue());
                break;
            }
            LOGGER.info("No Create goggle interface at {}.", hook.getKey());
        }
        if (selected.isEmpty()) {
            LOGGER.error("No known Create goggle interface found, so experience readouts will "
                    + "be absent. Looked for: {}", HOOKS.keySet());
        }
        return selected;
    }

    /** True only when Forge definitely reports a dedicated server. Anything else counts as a client. */
    private static boolean isDedicatedServer() {
        try {
            Dist dist = FMLEnvironment.dist;
            LOGGER.info("Physical side reported as {}.", dist);
            return dist == Dist.DEDICATED_SERVER;
        } catch (Throwable t) {
            LOGGER.info("Physical side not determinable yet ({}), assuming client.", t.toString());
            return false;
        }
    }

    /**
     * Whether a class exists, without loading it.
     *
     * <p>Neither probe initialises the class. That matters: force-loading Create's goggle
     * interface here would freeze it before this very mixin gets to transform it.
     *
     * <p>Two probes rather than one, because the bytecode provider does not always see
     * another mod's jar this early in startup, and a probe that answers "no" for both
     * layouts silently disables the whole mod.
     */
    private static boolean isPresent(String className) {
        try {
            if (MixinService.getService().getBytecodeProvider().getClassNode(className) != null) {
                return true;
            }
        } catch (ClassNotFoundException e) {
            // Fall through to the resource probe; the class may simply not be visible yet.
        } catch (Exception | LinkageError e) {
            LOGGER.warn("Bytecode probe for {} failed ({}), falling back to a resource lookup.",
                    className, e.toString());
        }
        return hasClassResource(className);
    }

    /** Looks for the .class file on the classpath. Never defines or initialises the class. */
    private static boolean hasClassResource(String className) {
        String path = className.replace('.', '/') + ".class";
        ClassLoader loader = ExpGogglesMixinPlugin.class.getClassLoader();
        try {
            if (loader != null && loader.getResource(path) != null) {
                LOGGER.info("Found {} via classpath resource lookup.", className);
                return true;
            }
            ClassLoader context = Thread.currentThread().getContextClassLoader();
            if (context != null && context != loader && context.getResource(path) != null) {
                LOGGER.info("Found {} via context classloader resource lookup.", className);
                return true;
            }
        } catch (Exception | LinkageError e) {
            LOGGER.warn("Resource probe for {} failed: {}", className, e.toString());
        }
        return false;
    }

    @Override
    public void onLoad(String mixinPackage) {
        LOGGER.info("Liquid Experience Goggles mixin plugin loaded for package {}.", mixinPackage);
    }

    @Override
    public String getRefMapperConfig() {
        return null;
    }

    @Override
    public boolean shouldApplyMixin(String targetClassName, String mixinClassName) {
        return true;
    }

    @Override
    public void acceptTargets(Set<String> myTargets, Set<String> otherTargets) {}

    @Override
    public void preApply(String targetClassName, ClassNode targetClass, String mixinClassName,
                         IMixinInfo mixinInfo) {}

    @Override
    public void postApply(String targetClassName, ClassNode targetClass, String mixinClassName,
                          IMixinInfo mixinInfo) {}
}
