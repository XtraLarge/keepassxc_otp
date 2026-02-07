"""Constants for the KeePassXC OTP integration."""
from datetime import timedelta

DOMAIN = "keepassxc_otp"

# Configuration keys
CONF_DATABASE_FILE = "database_file"
CONF_PASSWORD = "password"
CONF_KEYFILE_FILE = "keyfile_file"
CONF_OTP_SECRETS = "otp_secrets"

# Update interval
UPDATE_INTERVAL = timedelta(seconds=10)

# Default values
DEFAULT_NAME = "KeePassXC OTP"

# Attributes
ATTR_ENTRY_NAME = "entry_name"
ATTR_ISSUER = "issuer"
ATTR_ACCOUNT = "account"
ATTR_TIME_REMAINING = "time_remaining"
ATTR_PERIOD = "period"
