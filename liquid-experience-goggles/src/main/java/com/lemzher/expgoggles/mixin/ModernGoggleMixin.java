package com.lemzher.expgoggles.mixin;

import java.util.List;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import com.lemzher.expgoggles.ExperienceTooltip;

import net.minecraft.network.chat.Component;
import net.minecraftforge.common.util.LazyOptional;
import net.minecraftforge.fluids.capability.IFluidHandler;

/**
 * Goggle hook for Create 0.5.1 and later, where the interface lives in
 * {@code content.equipment.goggles}.
 *
 * <p>Enabled by {@link com.lemzher.expgoggles.ExpGogglesMixinPlugin} only when that class
 * is actually present, so an older Create simply gets {@link LegacyGoggleMixin} instead.
 */
@Mixin(targets = "com.simibubi.create.content.equipment.goggles.IHaveGoggleInformation", remap = false)
public interface ModernGoggleMixin {

    @Inject(method = "containedFluidTooltip", at = @At("RETURN"), remap = false)
    private void expgoggles$appendExperienceLevels(List<Component> tooltip, boolean isPlayerSneaking,
                                                   LazyOptional<IFluidHandler> handler,
                                                   CallbackInfoReturnable<Boolean> cir) {
        if (!cir.getReturnValueZ()) {
            return;
        }
        ExperienceTooltip.append(tooltip, isPlayerSneaking, handler);
    }
}
