"""Constants for the KeePassXC OTP integration."""
import os
from datetime import timedelta

DOMAIN = "keepassxc_otp"

# Configuration keys
CONF_DATABASE_FILE = "database_file"
CONF_PASSWORD = "password"
CONF_KEYFILE_FILE = "keyfile_file"
CONF_OTP_SECRETS = "otp_secrets"
CONF_IMPORT_STATS = "import_stats"

# Update interval - only update when new code is due (every ~30 seconds)
UPDATE_INTERVAL = timedelta(seconds=30)

# Default values
DEFAULT_NAME = "KeePassXC OTP"

# Attributes
ATTR_ENTRY_NAME = "entry_name"
ATTR_ISSUER = "issuer"
ATTR_ACCOUNT = "account"
ATTR_TIME_REMAINING = "time_remaining"
ATTR_PERIOD = "period"


def sanitize_entity_name(name: str) -> str:
    """Sanitize a name for use in entity ID.
    
    Args:
        name: The name to sanitize
        
    Returns:
        Sanitized name suitable for entity IDs
    """
    # Convert to lowercase and replace spaces/hyphens with underscores
    entity_name = name.lower().replace(" ", "_").replace("-", "_")
    # Remove special characters, keep only alphanumeric and underscores
    entity_name = "".join(c for c in entity_name if c.isalnum() or c == "_")
    return entity_name


def sanitize_path_component(name: str) -> str:
    """Sanitize a name for use in file paths.
    
    This removes any path traversal attempts and ensures the name is safe
    to use as a directory or file name component.
    
    Args:
        name: The name to sanitize
        
    Returns:
        Sanitized name suitable for file paths
    """
    # Remove any path separators and parent directory references
    name = name.replace("/", "_").replace("\\", "_").replace("..", "_")
    # Use os.path.basename to ensure we only get the file name component
    name = os.path.basename(name)
    # Replace any remaining problematic characters
    name = name.replace(":", "_").replace("*", "_").replace("?", "_")
    name = name.replace('"', "_").replace("<", "_").replace(">", "_")
    name = name.replace("|", "_")
    # Ensure the name is not empty after sanitization
    if not name or name == "." or name == "..":
        name = "unknown"
    return name
