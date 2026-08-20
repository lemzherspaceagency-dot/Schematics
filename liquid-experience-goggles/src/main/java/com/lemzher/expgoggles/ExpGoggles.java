package com.lemzher.expgoggles;

import net.minecraftforge.fml.IExtensionPoint;
import net.minecraftforge.fml.ModLoadingContext;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.config.ModConfig;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
import net.minecraftforge.network.NetworkConstants;

/**
 * Adds an experience readout to Create's Engineer's Goggles for tanks holding
 * Create: Enchantment Industry's Liquid Experience.
 *
 * <p>This is a client-only mod. It registers no blocks, items, fluids or packets, and reads
 * only block entity data the server already sends for rendering. The DisplayTest extension
 * point below tells Forge not to require it on the other side of a connection, so it works
 * on servers that do not have it installed.
 */
@Mod(ExpGoggles.ID)
public class ExpGoggles {

    public static final String ID = "expgoggles";

    public ExpGoggles() {
        ModLoadingContext context = ModLoadingContext.get();

        // Never demand this mod of a server, and never refuse a server for lacking it.
        context.registerExtensionPoint(IExtensionPoint.DisplayTest.class,
                () -> new IExtensionPoint.DisplayTest(
                        () -> NetworkConstants.IGNORESERVERONLY,
                        (remoteVersion, isFromServer) -> true));

        context.registerConfig(ModConfig.Type.CLIENT, ExpGogglesConfig.SPEC);

        var modBus = FMLJavaModLoadingContext.get().getModEventBus();
        modBus.addListener(ExpGogglesConfig::onLoad);
        modBus.addListener(ExpGogglesConfig::onReload);
    }
}
