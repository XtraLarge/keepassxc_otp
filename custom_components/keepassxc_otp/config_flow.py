"""Config flow for KeePassXC OTP integration."""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any
from urllib.parse import parse_qs, urlparse

from pykeepass import PyKeePass
from pykeepass.exceptions import CredentialsError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DATABASE_FILE,
    CONF_KEYFILE_FILE,
    CONF_OTP_SECRETS,
    CONF_PASSWORD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _read_file(file_path: str) -> bytes:
    """Read file content."""
    with open(file_path, "rb") as file:
        return file.read()


def _ensure_directory(path: str) -> None:
    """Ensure directory exists with proper permissions."""
    os.makedirs(path, mode=0o755, exist_ok=True)


def _secure_delete_file(file_path: str) -> None:
    """Securely delete a file by overwriting it before deletion."""
    try:
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Overwrite with random data
        with open(file_path, "wb") as f:
            f.write(os.urandom(file_size))
            f.flush()
            os.fsync(f.fileno())
        
        # Delete the file
        os.unlink(file_path)
    except Exception as err:
        _LOGGER.error("Error during secure file deletion: %s", err)
        # Try regular deletion as fallback
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception:
            pass


def _extract_otp_from_entry(entry) -> dict[str, Any] | None:
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

    return _parse_otpauth_uri(otp_uri, entry.title)


def _parse_otpauth_uri(uri: str, entry_name: str) -> dict[str, Any] | None:
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

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DATABASE_FILE, default="database.kdbx"): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_KEYFILE_FILE, default="keyfile.key"): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    storage_dir = hass.config.path("keepassxc_otp")
    
    db_filename = data[CONF_DATABASE_FILE]
    password = data[CONF_PASSWORD]
    keyfile_filename = data.get(CONF_KEYFILE_FILE)

    # Construct full paths
    db_path = os.path.join(storage_dir, db_filename)
    keyfile_path = None
    if keyfile_filename:
        keyfile_path = os.path.join(storage_dir, keyfile_filename)

    # Check if database file exists
    if not await hass.async_add_executor_job(os.path.exists, db_path):
        raise ValueError("database_not_found")

    # Check if keyfile exists (if provided)
    if keyfile_path and not await hass.async_add_executor_job(os.path.exists, keyfile_path):
        raise ValueError("keyfile_not_found")

    # Read files
    db_content = await hass.async_add_executor_job(_read_file, db_path)
    keyfile_content = None
    if keyfile_path:
        keyfile_content = await hass.async_add_executor_job(_read_file, keyfile_path)

    # Create temporary files
    db_temp_path = None
    kf_temp_path = None

    try:
        # Save database to temporary file with restricted permissions
        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, suffix=".kdbx"
        ) as db_temp:
            db_temp.write(db_content)
            db_temp_path = db_temp.name
        # Set file permissions to owner read/write only (0o600)
        os.chmod(db_temp_path, 0o600)

        # Save keyfile to temporary file if provided with restricted permissions
        if keyfile_content:
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False
            ) as kf_temp:
                kf_temp.write(keyfile_content)
                kf_temp_path = kf_temp.name
            # Set file permissions to owner read/write only (0o600)
            os.chmod(kf_temp_path, 0o600)

        # Try to open the database and extract OTP secrets
        try:
            kp = await hass.async_add_executor_job(
                PyKeePass,
                db_temp_path,
                password,
                kf_temp_path,
            )
        except CredentialsError as err:
            _LOGGER.error("Invalid credentials for KeePassXC database: %s", err)
            raise ValueError("invalid_auth") from err
        except Exception as err:
            _LOGGER.error("Error opening KeePassXC database: %s", err)
            raise ValueError("cannot_connect") from err

        # Extract all OTP secrets from all entries
        otp_secrets = {}
        for entry in kp.entries:
            otp_data = _extract_otp_from_entry(entry)
            if otp_data:
                entry_uuid = str(entry.uuid)
                otp_secrets[entry_uuid] = {
                    "secret": otp_data["secret"],
                    "name": entry.title,
                    "issuer": otp_data.get("issuer"),
                    "account": otp_data.get("account"),
                    "period": otp_data.get("period", 30),
                    "digits": otp_data.get("digits", 6),
                    "algorithm": otp_data.get("algorithm", "SHA1"),
                }
                _LOGGER.debug("Extracted OTP for entry: %s (UUID: %s)", entry.title, entry_uuid)

        _LOGGER.info("Extracted %d OTP secrets from database", len(otp_secrets))

        if not otp_secrets:
            _LOGGER.warning("No OTP entries found in the database")
            raise ValueError("no_otp_entries")

    finally:
        # CRITICAL: Securely delete temporary files
        if db_temp_path and os.path.exists(db_temp_path):
            _secure_delete_file(db_temp_path)
            _LOGGER.debug("Securely deleted temporary database file")
        if kf_temp_path and os.path.exists(kf_temp_path):
            _secure_delete_file(kf_temp_path)
            _LOGGER.debug("Securely deleted temporary keyfile")
        
        # CRITICAL: Delete original files from keepassxc_otp directory
        if os.path.exists(db_path):
            _secure_delete_file(db_path)
            _LOGGER.info("Securely deleted original database file from %s", db_path)
        if keyfile_path and os.path.exists(keyfile_path):
            _secure_delete_file(keyfile_path)
            _LOGGER.info("Securely deleted original keyfile from %s", keyfile_path)

    # Return info that you want to store in the config entry
    # Note: Password is NOT stored for security reasons
    return {
        "title": "KeePassXC OTP",
        CONF_OTP_SECRETS: otp_secrets,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KeePassXC OTP."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        # Ensure directory exists
        storage_dir = self.hass.config.path("keepassxc_otp")
        await self.hass.async_add_executor_job(_ensure_directory, storage_dir)

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ValueError as err:
                error_str = str(err)
                if "database_not_found" in error_str:
                    errors["base"] = "database_not_found"
                elif "keyfile_not_found" in error_str:
                    errors["base"] = "keyfile_not_found"
                elif "invalid_auth" in error_str:
                    errors["base"] = "invalid_auth"
                elif "cannot_connect" in error_str:
                    errors["base"] = "cannot_connect"
                elif "no_otp_entries" in error_str:
                    errors["base"] = "no_otp_entries"
                else:
                    errors["base"] = "unknown"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Store only OTP secrets in config entry (no password)
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_OTP_SECRETS: info[CONF_OTP_SECRETS],
                    },
                )

        # Show form with description
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "storage_path": storage_dir,
            },
        )
