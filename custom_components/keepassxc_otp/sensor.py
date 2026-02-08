"""Sensor platform for KeePassXC OTP integration."""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

import pyotp

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import slugify

from .const import (
    ATTR_ACCOUNT,
    ATTR_ENTRY_NAME,
    ATTR_ISSUER,
    ATTR_PERIOD,
    ATTR_TIME_REMAINING,
    CONF_OTP_SECRETS,
    DOMAIN,
    UPDATE_INTERVAL,
    sanitize_entity_name,
)

_LOGGER = logging.getLogger(__name__)


class KeePassXCOTPCoordinator(DataUpdateCoordinator):
    """Class to manage OTP code generation."""

    def __init__(
        self,
        hass: HomeAssistant,
        otp_secrets: dict[str, dict[str, Any]],
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.otp_secrets = otp_secrets

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Generate TOTP codes from stored secrets."""
        return await self.hass.async_add_executor_job(self._generate_otp_codes)

    def _generate_otp_codes(self) -> dict[str, dict[str, Any]]:
        """Generate current TOTP codes."""
        otp_data = {}

        for entry_uuid, secret_data in self.otp_secrets.items():
            try:
                # Get algorithm and convert to hashlib digest function
                algorithm_name = secret_data.get("algorithm", "SHA1").lower()
                
                # Map algorithm name to hashlib function
                digest_map = {
                    "sha1": hashlib.sha1,
                    "sha256": hashlib.sha256,
                    "sha512": hashlib.sha512,
                }
                digest = digest_map.get(algorithm_name, hashlib.sha1)
                
                totp = pyotp.TOTP(
                    secret_data["secret"],
                    digits=secret_data.get("digits", 6),
                    interval=secret_data.get("period", 30),
                    digest=digest,
                )

                current_code = totp.now()
                period = secret_data.get("period", 30)
                time_remaining = period - (int(time.time()) % period)

                otp_data[entry_uuid] = {
                    "code": current_code,
                    "name": secret_data["name"],
                    "issuer": secret_data.get("issuer"),
                    "account": secret_data.get("account"),
                    "period": period,
                    "digits": secret_data.get("digits", 6),
                    "time_remaining": time_remaining,
                    "entity_id_suffix": slugify(secret_data["name"]),
                }
            except Exception as err:
                _LOGGER.error(
                    "Error generating OTP for %s: %s", secret_data["name"], err
                )

        return otp_data


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KeePassXC OTP sensors from a config entry."""
    otp_secrets = config_entry.data.get(CONF_OTP_SECRETS, {})
    person_entity_id = config_entry.data.get("person_entity_id")
    person_name = config_entry.data.get("person_name")
    person_id = config_entry.data.get("person_id")

    if not person_entity_id:
        _LOGGER.error("No person_entity_id in config entry")
        return

    if not otp_secrets:
        _LOGGER.warning("No OTP secrets found for person %s", person_name)
        return
    
    coordinator = KeePassXCOTPCoordinator(hass, otp_secrets)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Create exactly one entity per unique UUID
    entities = [
        KeePassXCOTPSensor(coordinator, entry_uuid, person_entity_id, person_name, person_id)
        for entry_uuid in otp_secrets.keys()
    ]

    _LOGGER.info(
        "Creating %d OTP sensor entities for person %s",
        len(entities),
        person_name
    )
    async_add_entities(entities, update_before_add=True)


class KeePassXCOTPSensor(CoordinatorEntity, SensorEntity):
    """Representation of a KeePassXC OTP sensor."""

    def __init__(
        self,
        coordinator: KeePassXCOTPCoordinator,
        entry_uuid: str,
        person_entity_id: str,
        person_name: str,
        person_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry_uuid = entry_uuid
        self._person_entity_id = person_entity_id
        self._person_name = person_name
        self._person_id = person_id
        
        # Get initial data from coordinator
        otp_data = coordinator.data.get(entry_uuid, {})
        
        # Create person-specific entity ID using person ID (from person.alice -> alice)
        base_name = otp_data.get("name", "Unknown OTP Entry")
        entity_name = sanitize_entity_name(base_name)
        
        self._attr_unique_id = f"{person_id}_{entry_uuid}"
        self.entity_id = f"sensor.{DOMAIN}_{person_id}_{entity_name}"
        
        # Include person name in friendly name
        self._attr_name = f"{base_name} ({person_name})"
            
        self._attr_icon = "mdi:key-chain"
        
        _LOGGER.debug(
            "Created sensor %s for person %s (entity: %s)",
            self.entity_id,
            person_name,
            person_entity_id
        )
        
        # Log warning if OTP data is missing
        if not otp_data:
            _LOGGER.warning(
                "OTP data missing for entry UUID %s during sensor initialization",
                entry_uuid,
            )

    @property
    def native_value(self) -> str | None:
        """Return the current TOTP code."""
        otp_data = self.coordinator.data.get(self._entry_uuid)
        if not otp_data:
            return None

        # Get the code and ensure it's zero-padded
        code = otp_data.get("code")
        if code is None:
            return None

        digits = otp_data.get("digits", 6)
        return str(code).zfill(digits)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        otp_data = self.coordinator.data.get(self._entry_uuid)
        if not otp_data:
            return {}

        attributes = {
            ATTR_ENTRY_NAME: otp_data.get("name"),
            ATTR_TIME_REMAINING: otp_data.get("time_remaining", 0),
            ATTR_PERIOD: otp_data.get("period", 30),
        }

        if otp_data.get("issuer"):
            attributes[ATTR_ISSUER] = otp_data["issuer"]

        if otp_data.get("account"):
            attributes[ATTR_ACCOUNT] = otp_data["account"]
        
        # Add person information
        attributes["person_entity_id"] = self._person_entity_id
        attributes["person_name"] = self._person_name

        return attributes
