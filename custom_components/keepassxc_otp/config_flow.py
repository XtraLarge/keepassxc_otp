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
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DATABASE_FILE,
    CONF_IMPORT_STATS,
    CONF_KEYFILE_FILE,
    CONF_OTP_SECRETS,
    CONF_PASSWORD,
    DOMAIN,
    sanitize_entity_name,
    sanitize_path_component,
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
    """Extract OTP data from a KeePassXC entry.
    
    Returns:
        dict with OTP data, or None if entry should be skipped
        On error, returns dict with "error" key containing the skip reason
    """
    
    # Skip entries with references - they don't contain actual OTP data
    if _has_references(entry):
        _LOGGER.debug(
            "Skipping entry '%s' - contains field references (not an actual OTP entry)",
            entry.title
        )
        return {"error": "contains_field_references"}
    
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

    # Parse otpauth:// URI or try to construct one from simple key format
    if not otp_uri.startswith("otpauth://"):
        # Try to construct URI if it's a simple key format
        _LOGGER.debug("Entry %s has OTP data but not in URI format, attempting to parse", entry.title)
        
        import re
        # Try to extract key from various formats:
        # - "key=JBSWY3DPEHPK3PXP"
        # - "JBSWY3DPEHPK3PXP" (plain base32)
        key_match = re.search(r'key\s*=\s*([A-Z2-7]+)', otp_uri, re.IGNORECASE)
        
        if key_match:
            secret = key_match.group(1).upper()
        elif re.match(r'^[A-Z2-7]+=*$', otp_uri.strip()):
            # Looks like a plain base32 secret
            secret = otp_uri.strip().upper()
        else:
            _LOGGER.debug("Entry %s: OTP data is not in a recognized format", entry.title)
            return {"error": "simple_key_not_supported"}
        
        # Validate it's a valid base32 string (length should be multiple of 8 when padded)
        # Base32 uses A-Z and 2-7
        if not secret or len(secret) < 16:  # Minimum reasonable length for OTP secret
            _LOGGER.debug("Entry %s: Secret too short or empty", entry.title)
            return {"error": "no_secret_found"}
        
        # Construct a full otpauth URI with defaults
        # Use entry title as the account name, sanitized
        account_name = entry.title.replace(":", "_").replace("/", "_")
        otp_uri = f"otpauth://totp/{account_name}?secret={secret}&period=30&digits=6&algorithm=SHA1"
        _LOGGER.info("Constructed OTP URI from simple key format for entry: %s", entry.title)

    otp_data = _parse_otpauth_uri(otp_uri, entry.title)
    if not otp_data:
        return {"error": "invalid_uri_format"}
    
    # Extract URL from entry (if available)
    entry_url = None
    if hasattr(entry, 'url') and entry.url:
        # Only include if not a reference
        if "{REF:" not in str(entry.url).upper():
            entry_url = entry.url
    
    # Extract username from entry (if available)
    entry_username = None
    if hasattr(entry, 'username') and entry.username:
        # Only include if not a reference
        if "{REF:" not in str(entry.username).upper():
            entry_username = entry.username
    
    # Add URL and username to OTP data
    otp_data["url"] = entry_url
    otp_data["username"] = entry_username
    
    return otp_data


def _get_person_info(person_state) -> tuple[str, str]:
    """Extract person name and ID from person state.
    
    Args:
        person_state: The person entity state object
        
    Returns:
        Tuple of (person_name, person_id)
        
    Raises:
        ValueError: If the person entity ID format is invalid
    """
    # Get person name and sanitize for safe path usage
    raw_person_name = person_state.attributes.get("friendly_name") or person_state.name
    person_name = sanitize_path_component(raw_person_name)
    
    # Extract person ID from entity ID (e.g., person.alice -> alice)
    entity_id = person_state.entity_id
    if "." not in entity_id:
        raise ValueError(f"Invalid person entity ID format: {entity_id}")
    
    person_id = entity_id.split(".", 1)[1]
    
    return person_name, person_id


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
        vol.Required("person_entity_id"): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="person")
        ),
        vol.Required(CONF_DATABASE_FILE, default="database.kdbx"): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_KEYFILE_FILE, default=""): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any], person_name: str) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    
    Args:
        hass: Home Assistant instance
        data: User input data
        person_name: Name of the person (for logging only)
    """
    # Use SHARED directory for all imports (not person-specific)
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
        _LOGGER.error("Database not found for person %s at %s", person_name, db_path)
        raise ValueError("database_not_found")

    # Check if keyfile exists (if provided)
    if keyfile_path and not await hass.async_add_executor_job(os.path.exists, keyfile_path):
        _LOGGER.error("Keyfile not found for person %s at %s", person_name, keyfile_path)
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
        
        # Track import statistics
        import_stats = {
            "imported": [],  # List of successfully imported entry names
            "skipped": [],   # List of dicts with {"name": str, "reason": str}
            "total_entries": len(kp.entries),
        }
        
        for entry in kp.entries:
            otp_data = _extract_otp_from_entry(entry)
            
            # Check if entry was skipped with a reason
            if otp_data and "error" in otp_data:
                reason_map = {
                    "contains_field_references": "Contains field references",
                    "simple_key_not_supported": "Simple key format not supported",
                    "no_secret_found": "No secret found",
                    "invalid_uri_format": "Invalid URI format",
                }
                reason = reason_map.get(otp_data["error"], "Unknown error")
                import_stats["skipped"].append({
                    "name": entry.title,
                    "reason": reason
                })
                continue
            
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
                    import_stats["skipped"].append({
                        "name": entry.title,
                        "reason": "Duplicate"
                    })
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
                    "url": otp_data.get("url"),
                    "username": otp_data.get("username"),
                }
                
                # Track successful import
                import_stats["imported"].append(entry.title)
                
                _LOGGER.debug(
                    "Extracted OTP for entry: %s (UUID: %s)",
                    entry.title,
                    entry_uuid
                )

        _LOGGER.info(
            "Successfully extracted %d unique OTP secrets. "
            "Skipped %d entries.",
            len(otp_secrets),
            len(import_stats["skipped"])
        )
        
        _LOGGER.info("Successfully validated database for person %s with %d OTP entries", person_name, len(otp_secrets))

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
        "import_stats": import_stats,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KeePassXC OTP."""

    VERSION = 2

    def __init__(self):
        """Initialize the config flow."""
        super().__init__()
        self._import_stats = None
        self._pending_data = None

    def _format_import_stats(self, import_stats: dict[str, Any]) -> str:
        """Format import statistics into a readable string."""
        lines = []
        
        # Imported entries
        imported_count = len(import_stats.get("imported", []))
        if imported_count > 0:
            lines.append(f"✅ **Imported: {imported_count} entries**")
            for name in import_stats["imported"][:10]:  # Limit to first 10
                lines.append(f"  - {name}")
            if imported_count > 10:
                lines.append(f"  - ... and {imported_count - 10} more")
        
        # Skipped entries
        skipped_count = len(import_stats.get("skipped", []))
        if skipped_count > 0:
            lines.append(f"\n⏭️ **Skipped: {skipped_count} entries**")
            for item in import_stats["skipped"][:10]:  # Limit to first 10
                lines.append(f"  - \"{item['name']}\" ({item['reason']})")
            if skipped_count > 10:
                lines.append(f"  - ... and {skipped_count - 10} more")
        
        # Total
        total_count = import_stats.get("total_entries", 0)
        lines.append(f"\n📊 **Total entries in database: {total_count}**")
        
        return "\n".join(lines)

    async def async_step_import_report(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show import report after successful import."""
        if user_input is not None:
            # User clicked OK
            # For reconfigure: abort with success message
            if self.context.get("reconfigure"):
                return self.async_abort(reason="reconfigure_successful")
            # For initial setup: create the entry
            else:
                return self.async_create_entry(
                    title=self._pending_data["title"],
                    data=self._pending_data["data"],
                )
        
        # Get import stats
        import_stats = self._import_stats or {}
        formatted_stats = self._format_import_stats(import_stats)
        
        return self.async_show_form(
            step_id="import_report",
            description_placeholders={
                "import_stats": formatted_stats,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        
        # Get the existing config entry
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        person_entity_id = entry.data.get("person_entity_id")
        person_name = entry.data.get("person_name")
        person_id = entry.data.get("person_id")
        
        # Get saved filenames (or use defaults)
        saved_database_file = entry.data.get("database_file", "database.kdbx")
        saved_keyfile_file = entry.data.get("keyfile_file", "")
        
        # Create reconfigure schema with pre-filled filenames
        RECONFIGURE_SCHEMA = vol.Schema(
            {
                vol.Required(CONF_DATABASE_FILE, default=saved_database_file): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_KEYFILE_FILE, default=saved_keyfile_file): cv.string,
            }
        )
        
        # Use SHARED directory (not person-specific)
        storage_dir = self.hass.config.path("keepassxc_otp")
        await self.hass.async_add_executor_job(_ensure_directory, storage_dir)
        
        if user_input is not None:
            try:
                # Add person_entity_id back for validation
                user_input["person_entity_id"] = person_entity_id
                
                info = await validate_input(self.hass, user_input, person_name)
                
                # Store import stats for the import report
                self._import_stats = info.get("import_stats", {})
                self.context["reconfigure"] = True
                
                # Update config entry with new secrets AND save filenames
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        "person_entity_id": person_entity_id,
                        "person_name": person_name,
                        "person_id": person_id,
                        "database_file": user_input[CONF_DATABASE_FILE],
                        "keyfile_file": user_input.get(CONF_KEYFILE_FILE, ""),
                        CONF_OTP_SECRETS: info[CONF_OTP_SECRETS],
                    }
                )
                
                _LOGGER.info(
                    "Reconfigured KeePassXC OTP for person %s with %d secrets",
                    person_name,
                    len(info[CONF_OTP_SECRETS])
                )
                
                await self.hass.config_entries.async_reload(entry.entry_id)
                
                # Show import report instead of immediately aborting
                return await self.async_step_import_report()
                
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
        
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=RECONFIGURE_SCHEMA,
            errors=errors,
            description_placeholders={
                "storage_path": storage_dir,
                "person_name": person_name,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Get person entity
            person_entity_id = user_input.get("person_entity_id")
            person_state = self.hass.states.get(person_entity_id)
            
            if not person_state:
                errors["person_entity_id"] = "person_not_found"
            else:
                try:
                    # Get person name and ID using helper function
                    person_name, person_id = _get_person_info(person_state)
                except ValueError as err:
                    _LOGGER.error("Invalid person entity: %s", err)
                    errors["person_entity_id"] = "person_not_found"
                except (IndexError, AttributeError) as err:
                    _LOGGER.error("Error extracting person info: %s", err)
                    errors["person_entity_id"] = "person_not_found"
                else:
                    # Check if this person already has an integration instance
                    existing_entries = self._async_current_entries()
                    for entry in existing_entries:
                        if entry.data.get("person_entity_id") == person_entity_id:
                            errors["base"] = "person_already_configured"
                            break
                    
                    if not errors:
                        # Create SHARED directory (not person-specific)
                        storage_dir = self.hass.config.path("keepassxc_otp")
                        await self.hass.async_add_executor_job(_ensure_directory, storage_dir)
                        
                        try:
                            # Pass person info to validation (for logging only)
                            info = await validate_input(self.hass, user_input, person_name)
                            
                            # Store import stats and pending data for the import report
                            self._import_stats = info.get("import_stats", {})
                            self._pending_data = {
                                "title": f"KeePassXC OTP ({person_name})",
                                "data": {
                                    "person_entity_id": person_entity_id,
                                    "person_name": person_name,
                                    "person_id": person_id,
                                    "database_file": user_input[CONF_DATABASE_FILE],
                                    "keyfile_file": user_input.get(CONF_KEYFILE_FILE, ""),
                                    CONF_OTP_SECRETS: info[CONF_OTP_SECRETS],
                                },
                            }
                            
                            # Show import report before creating the entry
                            return await self.async_step_import_report()
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
                            _LOGGER.exception("Unexpected exception")
                            errors["base"] = "unknown"

        # Static storage path (no dynamic variable needed)
        storage_dir = self.hass.config.path("keepassxc_otp")
        
        # Show form with person selector
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, user_input
            ) if user_input else DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "storage_path": storage_dir,
            },
        )
