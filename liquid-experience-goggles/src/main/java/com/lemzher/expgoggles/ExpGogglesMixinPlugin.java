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
        // side has to be checked here. Without this, dropping the jar into a server's mods
        // folder would hook the tooltip and then fail on the first client-only class it
        // touches. Nothing this mod does is meaningful server-side anyway.
        if (FMLEnvironment.dist != Dist.CLIENT) {
            LOGGER.info("Not a physical client — no goggle hooks applied.");
            return List.of();
        }

        List<String> selected = new ArrayList<>(1);
        for (Map.Entry<String, String> hook : HOOKS.entrySet()) {
            if (isPresent(hook.getKey())) {
                LOGGER.info("Create goggle interface found at {}, applying {}",
                        hook.getKey(), hook.getValue());
                selected.add(hook.getValue());
                break;
            }
        }
        if (selected.isEmpty()) {
            LOGGER.warn("No known Create goggle interface found — experience readouts will be "
                    + "absent. This build knows about: {}", HOOKS.keySet());
        }
        return selected;
    }

    private static boolean isPresent(String className) {
        try {
            return MixinService.getService().getBytecodeProvider().getClassNode(className) != null;
        } catch (ClassNotFoundException e) {
            return false;
        } catch (Exception | LinkageError e) {
            LOGGER.debug("Could not probe {}: {}", className, e.toString());
            return false;
        }
    }

    @Override
    public void onLoad(String mixinPackage) {}

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
