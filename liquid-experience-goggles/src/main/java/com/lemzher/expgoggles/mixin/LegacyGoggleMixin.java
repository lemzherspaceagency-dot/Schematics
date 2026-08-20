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
 * Goggle hook for Create 0.5.0 and earlier, where the interface lived in
 * {@code content.contraptions.goggles} before the 0.5.1 repackaging.
 *
 * <p>The method signature is byte-for-byte the same as the modern one, so only the owning
 * class name differs between the two hooks.
 */
@Mixin(targets = "com.simibubi.create.content.contraptions.goggles.IHaveGoggleInformation", remap = false)
public interface LegacyGoggleMixin {

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
