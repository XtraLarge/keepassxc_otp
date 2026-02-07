"""The KeePassXC OTP integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up KeePassXC OTP from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Clean up old entities from this integration before creating new ones
    await _async_cleanup_old_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_cleanup_old_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove old entities created by this integration."""
    entity_registry = er.async_get(hass)
    
    # Get all entities for this config entry
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    
    # Remove all entities
    for entity_entry in entries:
        _LOGGER.debug("Removing old entity: %s", entity_entry.entity_id)
        entity_registry.async_remove(entity_entry.entity_id)
