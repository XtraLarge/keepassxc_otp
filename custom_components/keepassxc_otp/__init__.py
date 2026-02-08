"""The KeePassXC OTP integration."""
from __future__ import annotations

import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the KeePassXC OTP component."""
    # Create directory for file placement
    storage_dir = hass.config.path("keepassxc_otp")

    def _ensure_directory(path: str) -> None:
        """Ensure directory exists with proper permissions."""
        os.makedirs(path, mode=0o755, exist_ok=True)

    await hass.async_add_executor_job(_ensure_directory, storage_dir)
    _LOGGER.info("Created/verified KeePassXC OTP storage directory: %s", storage_dir)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up KeePassXC OTP from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store the OTP secrets for this entry
    hass.data[DOMAIN][entry.entry_id] = entry.data
    
    # Forward setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    _LOGGER.info(
        "Set up KeePassXC OTP integration with %d OTP secrets",
        len(entry.data.get("otp_secrets", {}))
    )
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.
    
    This is called during reconfiguration to remove all existing entities
    before creating new ones with updated data.
    """
    _LOGGER.info("Unloading KeePassXC OTP integration (removing all entities)")
    
    # Unload all platforms (this removes all entities)
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Remove the stored data
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Successfully unloaded KeePassXC OTP integration")
    else:
        _LOGGER.error("Failed to unload KeePassXC OTP integration")
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry.
    
    This is called during reconfiguration to cleanly reload the integration
    with new OTP secrets.
    """
    _LOGGER.info("Reloading KeePassXC OTP integration with updated configuration")
    
    # First, unload the entry to remove all entities
    if not await async_unload_entry(hass, entry):
        _LOGGER.error("Failed to unload entry during reload, aborting reload")
        return
    
    # Then set it up again with the new configuration
    await async_setup_entry(hass, entry)

