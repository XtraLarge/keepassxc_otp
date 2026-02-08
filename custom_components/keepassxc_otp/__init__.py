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
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

