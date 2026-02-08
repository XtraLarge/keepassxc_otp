"""The KeePassXC OTP integration."""
from __future__ import annotations

import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_OTP_SECRETS, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the KeePassXC OTP component."""
    # Create base directory for file placement
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
    
    # Register services
    await async_setup_services(hass)
    
    person_name = entry.data.get("person_name")
    _LOGGER.info(
        "Set up KeePassXC OTP for person %s with %d OTP secrets",
        person_name,
        len(entry.data.get(CONF_OTP_SECRETS, {}))
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


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for KeePassXC OTP integration."""
    
    # Check if services are already registered to avoid duplicates
    if hass.services.has_service(DOMAIN, "copy_token"):
        _LOGGER.debug("Services already registered, skipping")
        return
    
    async def handle_copy_token(call: ServiceCall) -> None:
        """Handle the copy_token service call."""
        entity_id = call.data.get("entity_id")
        
        # Get the entity state
        state = hass.states.get(entity_id)
        if not state:
            _LOGGER.error("Entity %s not found", entity_id)
            return
        
        token = state.state
        person_name = state.attributes.get("person_name", "Unknown")
        
        # Fire event that frontend can listen to for clipboard copy
        hass.bus.async_fire(
            "keepassxc_otp_copy_token",
            {
                "entity_id": entity_id,
                "token": token,
                "name": state.attributes.get("friendly_name", ""),
            }
        )
        
        # Also send a persistent notification as fallback
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": f"✅ OTP Token Copied ({person_name})",
                "message": f"Token for {state.attributes.get('friendly_name', entity_id)}:\n\n**{token}**\n\nClick to dismiss.",
                "notification_id": f"keepassxc_otp_{entity_id}",
            },
            blocking=False,
        )
        
        _LOGGER.debug("Copy token service called for %s (person: %s)", entity_id, person_name)
    
    async def handle_get_all_entities(call: ServiceCall) -> dict:
        """Handle the get_all_entities service call."""
        entity_reg = er.async_get(hass)
        
        # Find all entities for this integration
        entities = []
        for entry in entity_reg.entities.values():
            if entry.platform == DOMAIN:
                state = hass.states.get(entry.entity_id)
                if state:
                    entities.append({
                        "entity_id": entry.entity_id,
                        "name": state.attributes.get("friendly_name", entry.entity_id),
                        "issuer": state.attributes.get("issuer"),
                        "account": state.attributes.get("account"),
                        "time_remaining": state.attributes.get("time_remaining"),
                        "period": state.attributes.get("period"),
                    })
        
        _LOGGER.debug("Found %d OTP entities", len(entities))
        return {"entities": entities}
    
    # Register services
    hass.services.async_register(
        DOMAIN,
        "copy_token",
        handle_copy_token,
    )
    
    hass.services.async_register(
        DOMAIN,
        "get_all_entities",
        handle_get_all_entities,
    )
    
    _LOGGER.info("Registered KeePassXC OTP services")


