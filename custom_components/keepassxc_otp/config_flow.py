"""Config flow for KeePassXC OTP integration."""
from __future__ import annotations

import hashlib
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


def _has_references(entry) -> bool:
    """Check if entry contains KeePass field references.
    
    KeePass/KeePassXC use {REF:...} syntax for field references.
    Examples: {REF:P@I:46C9B1FFBD4ABC4BBB260C6190BAD20C}
    """
    # Check title
    if entry.title and "{REF:" in str(entry.title).upper():
        return True
    
    # Check username
    if hasattr(entry, 'username') and entry.username:
        if "{REF:" in str(entry.username).upper():
            return True
    
    # Check password (might contain references)
    if hasattr(entry, 'password') and entry.password:
        if "{REF:" in str(entry.password).upper():
            return True
    
    # Check URL
    if hasattr(entry, 'url') and entry.url:
        if "{REF:" in str(entry.url).upper():
            return True
    
    # Check notes
    if hasattr(entry, 'notes') and entry.notes:
        if "{REF:" in str(entry.notes).upper():
            return True
    
    # Check custom properties
    if hasattr(entry, "custom_properties"):
        for prop_value in entry.custom_properties.values():
            if prop_value and "{REF:" in str(prop_value).upper():
                return True
    
    return False


def _extract_otp_from_entry(entry) -> dict[str, Any] | None:
    """Extract OTP data from a KeePassXC entry."""
    
    # Skip entries with references - they don't contain actual OTP data
    if _has_references(entry):
        _LOGGER.debug(
            "Skipping entry '%s' - contains field references (not an actual OTP entry)",
            entry.title
        )
        return None
    
    otp_uri = None

    # Try to find OTP in custom attributes
    if hasattr(entry, "custom_properties"):
        for prop_name, prop_value in entry.custom_properties.items():
            if prop_name.lower() in ["otp", "totp", "otpauth"]:
                # Skip if this is a reference
                if prop_value and "{REF:" in str(prop_value).upper():
                    _LOGGER.debug(
                        "Skipping OTP property in '%s' - contains reference",
                        entry.title
                    )
                    continue
                otp_uri = prop_value
                break

    # Also check standard attributes
    if not otp_uri and hasattr(entry, "otp"):
        if entry.otp and "{REF:" not in str(entry.otp).upper():
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
        vol.Optional(CONF_KEYFILE_FILE, default=""): cv.string,
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

    # Validate filenames to prevent directory traversal
    db_filename = os.path.basename(db_filename)
    if keyfile_filename and keyfile_filename.strip():
        keyfile_filename = os.path.basename(keyfile_filename)
    else:
        keyfile_filename = None

    # Construct full paths
    db_path = os.path.join(storage_dir, db_filename)
    keyfile_path = None
    if keyfile_filename:
        keyfile_path = os.path.join(storage_dir, keyfile_filename)

    # Verify paths are within storage directory (additional security check)
    db_path = os.path.abspath(db_path)
    if not db_path.startswith(os.path.abspath(storage_dir)):
        raise ValueError("database_not_found")

    if keyfile_path:
        keyfile_path = os.path.abspath(keyfile_path)
        if not keyfile_path.startswith(os.path.abspath(storage_dir)):
            raise ValueError("keyfile_not_found")

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
        seen_secret_hashes = set()  # Track secret hashes to avoid duplicates
        
        for entry in kp.entries:
            otp_data = _extract_otp_from_entry(entry)
            if otp_data:
                secret = otp_data["secret"]
                
                # Hash the secret for deduplication to minimize exposure of actual secret
                secret_hash = hashlib.sha256(secret.encode()).hexdigest()
                
                # Skip if we've already seen this exact secret
                if secret_hash in seen_secret_hashes:
                    _LOGGER.debug(
                        "Skipping duplicate OTP secret in entry '%s' - already extracted",
                        entry.title
                    )
                    continue
                
                seen_secret_hashes.add(secret_hash)
                entry_uuid = str(entry.uuid)
                
                otp_secrets[entry_uuid] = {
                    "secret": secret,
                    "name": entry.title,
                    "issuer": otp_data.get("issuer"),
                    "account": otp_data.get("account"),
                    "period": otp_data.get("period", 30),
                    "digits": otp_data.get("digits", 6),
                    "algorithm": otp_data.get("algorithm", "SHA1"),
                }
                _LOGGER.debug(
                    "Extracted OTP for entry: %s (UUID: %s)",
                    entry.title,
                    entry_uuid
                )

        _LOGGER.info(
            "Successfully extracted %d unique OTP secrets. "
            "Skipped entries with references and duplicates.",
            len(otp_secrets)
        )

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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of the integration.
        
        This allows users to:
        - Upload a new database file
        - Re-extract OTP secrets
        - Automatically remove old entities
        - Create new entities from the updated database
        """
        errors: dict[str, str] = {}
        
        # Ensure directory exists
        storage_dir = self.hass.config.path("keepassxc_otp")
        await self.hass.async_add_executor_job(_ensure_directory, storage_dir)
        
        # Get the existing config entry being reconfigured
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        
        if user_input is not None:
            try:
                # Validate new input and extract OTP secrets
                info = await validate_input(self.hass, user_input)
                
                # Update the existing config entry with new OTP secrets
                # This will replace all old secrets with new ones
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_OTP_SECRETS: info[CONF_OTP_SECRETS],
                    }
                )
                
                _LOGGER.info(
                    "Reconfigured KeePassXC OTP integration with %d secrets",
                    len(info[CONF_OTP_SECRETS])
                )
                
                # Reload the integration to remove old entities and create new ones
                await self.hass.config_entries.async_reload(entry.entry_id)
                
                return self.async_abort(reason="reconfigure_successful")
                
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
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfiguration")
                errors["base"] = "unknown"
        
        # Show the same form as initial setup
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "storage_path": storage_dir,
            },
        )

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
