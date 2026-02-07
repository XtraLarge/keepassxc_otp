"""Sensor platform for KeePassXC OTP integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import re
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from pykeepass import PyKeePass
from pykeepass.exceptions import CredentialsError
import pyotp

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import slugify

from .const import (
    ATTR_ACCOUNT,
    ATTR_ENTRY_NAME,
    ATTR_ISSUER,
    ATTR_PERIOD,
    ATTR_TIME_REMAINING,
    CONF_DATABASE_PATH,
    CONF_KEYFILE,
    CONF_PASSWORD,
    DOMAIN,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class KeePassXCOTPCoordinator(DataUpdateCoordinator):
    """Class to manage fetching KeePassXC OTP data."""

    def __init__(
        self,
        hass: HomeAssistant,
        database_path: str,
        password: str,
        keyfile: str | None,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.database_path = database_path
        self.password = password
        self.keyfile = keyfile

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from KeePassXC database."""
        try:
            return await self.hass.async_add_executor_job(self._load_otp_entries)
        except CredentialsError as err:
            raise UpdateFailed(f"Invalid credentials: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with KeePassXC: {err}") from err

    def _load_otp_entries(self) -> dict[str, dict[str, Any]]:
        """Load OTP entries from KeePassXC database."""
        try:
            kp = PyKeePass(self.database_path, password=self.password, keyfile=self.keyfile)
        except Exception as err:
            _LOGGER.error("Failed to open KeePassXC database: %s", err)
            raise

        otp_entries = {}
        
        # Iterate through all entries in the database
        for entry in kp.entries:
            otp_data = self._extract_otp_from_entry(entry)
            if otp_data:
                entry_id = slugify(entry.title)
                otp_entries[entry_id] = otp_data
                _LOGGER.debug("Found OTP entry: %s", entry.title)

        _LOGGER.info("Found %d OTP entries in KeePassXC database", len(otp_entries))
        return otp_entries

    def _extract_otp_from_entry(self, entry) -> dict[str, Any] | None:
        """Extract OTP data from a KeePassXC entry."""
        otp_uri = None
        
        # Try to find OTP in custom attributes
        if hasattr(entry, "custom_properties"):
            for prop_name, prop_value in entry.custom_properties.items():
                if prop_name.lower() in ["otp", "totp", "otpauth"]:
                    otp_uri = prop_value
                    break
        
        # Also check standard attributes
        if not otp_uri and hasattr(entry, "otp"):
            otp_uri = entry.otp
        
        if not otp_uri:
            return None
        
        # Parse otpauth:// URI
        if not otp_uri.startswith("otpauth://"):
            # Try to construct URI if it's just a secret
            _LOGGER.debug("Entry %s has OTP data but not in URI format", entry.title)
            return None
        
        return self._parse_otpauth_uri(otp_uri, entry.title)

    def _parse_otpauth_uri(self, uri: str, entry_name: str) -> dict[str, Any] | None:
        """Parse otpauth:// URI and extract OTP parameters."""
        try:
            parsed = urlparse(uri)
            if parsed.scheme != "otpauth":
                return None
            
            # Extract type (totp or hotp)
            otp_type = parsed.netloc
            if otp_type not in ["totp", "hotp"]:
                _LOGGER.warning("Unsupported OTP type: %s", otp_type)
                return None
            
            # Parse label (issuer:account or just account)
            label = parsed.path.lstrip("/")
            issuer = None
            account = label
            
            if ":" in label:
                issuer, account = label.split(":", 1)
            
            # Parse query parameters
            params = parse_qs(parsed.query)
            secret = params.get("secret", [None])[0]
            
            if not secret:
                _LOGGER.warning("No secret found in OTP URI for %s", entry_name)
                return None
            
            # Get optional parameters
            period = int(params.get("period", ["30"])[0])
            digits = int(params.get("digits", ["6"])[0])
            algorithm = params.get("algorithm", ["SHA1"])[0]
            
            # Override issuer from query param if present
            if "issuer" in params:
                issuer = params["issuer"][0]
            
            return {
                "entry_name": entry_name,
                "secret": secret,
                "issuer": issuer,
                "account": account,
                "period": period,
                "digits": digits,
                "algorithm": algorithm,
                "type": otp_type,
            }
        except Exception as err:
            _LOGGER.error("Error parsing OTP URI for %s: %s", entry_name, err)
            return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KeePassXC OTP sensors from a config entry."""
    database_path = config_entry.data[CONF_DATABASE_PATH]
    password = config_entry.data[CONF_PASSWORD]
    keyfile = config_entry.data.get(CONF_KEYFILE)

    coordinator = KeePassXCOTPCoordinator(hass, database_path, password, keyfile)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Create sensors for each OTP entry
    sensors = []
    for entry_id, otp_data in coordinator.data.items():
        sensors.append(KeePassXCOTPSensor(coordinator, entry_id, otp_data))

    async_add_entities(sensors)


class KeePassXCOTPSensor(CoordinatorEntity, SensorEntity):
    """Representation of a KeePassXC OTP sensor."""

    def __init__(
        self,
        coordinator: KeePassXCOTPCoordinator,
        entry_id: str,
        otp_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._otp_data = otp_data
        self._attr_unique_id = f"{DOMAIN}_{entry_id}"
        self._attr_name = otp_data["entry_name"]
        self._attr_icon = "mdi:key-chain"
        # Set suggested entity_id for predictable entity naming
        self.entity_id = f"sensor.{DOMAIN}_{self._entry_id}"

    @property
    def native_value(self) -> str:
        """Return the current TOTP code."""
        try:
            otp_data = self.coordinator.data.get(self._entry_id)
            if not otp_data:
                return None
            
            secret = otp_data["secret"]
            digits = otp_data.get("digits", 6)
            period = otp_data.get("period", 30)
            
            totp = pyotp.TOTP(secret, digits=digits, interval=period)
            code = totp.now()
            
            # Zero-pad the code to the correct number of digits
            return code.zfill(digits)
        except Exception as err:
            _LOGGER.error("Error generating TOTP code for %s: %s", self._attr_name, err)
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        otp_data = self.coordinator.data.get(self._entry_id)
        if not otp_data:
            return {}
        
        period = otp_data.get("period", 30)
        time_remaining = period - (int(time.time()) % period)
        
        attributes = {
            ATTR_ENTRY_NAME: otp_data.get("entry_name"),
            ATTR_TIME_REMAINING: time_remaining,
            ATTR_PERIOD: period,
        }
        
        if otp_data.get("issuer"):
            attributes[ATTR_ISSUER] = otp_data["issuer"]
        
        if otp_data.get("account"):
            attributes[ATTR_ACCOUNT] = otp_data["account"]
        
        return attributes
