"""Config flow for KeePassXC OTP integration."""
from __future__ import annotations

import logging
import os
from typing import Any

from pykeepass import PyKeePass
from pykeepass.exceptions import CredentialsError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_DATABASE_PATH, CONF_KEYFILE, CONF_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DATABASE_PATH): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_KEYFILE): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    database_path = data[CONF_DATABASE_PATH]
    password = data[CONF_PASSWORD]
    keyfile = data.get(CONF_KEYFILE)

    # Check if database file exists
    if not await hass.async_add_executor_job(os.path.exists, database_path):
        raise ValueError("database_not_found")

    # Check if keyfile exists (if provided)
    if keyfile and not await hass.async_add_executor_job(os.path.exists, keyfile):
        raise ValueError("keyfile_not_found")

    # Try to open the database
    try:
        await hass.async_add_executor_job(
            PyKeePass,
            database_path,
            password,
            keyfile,
        )
    except CredentialsError as err:
        _LOGGER.error("Invalid credentials for KeePassXC database: %s", err)
        raise ValueError("invalid_auth") from err
    except Exception as err:
        _LOGGER.error("Error opening KeePassXC database: %s", err)
        raise ValueError("cannot_connect") from err

    # Return info that you want to store in the config entry.
    return {"title": "KeePassXC OTP"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KeePassXC OTP."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ValueError as err:
                if str(err) == "database_not_found":
                    errors["base"] = "database_not_found"
                elif str(err) == "keyfile_not_found":
                    errors["base"] = "keyfile_not_found"
                elif str(err) == "invalid_auth":
                    errors["base"] = "invalid_auth"
                elif str(err) == "cannot_connect":
                    errors["base"] = "cannot_connect"
                else:
                    errors["base"] = "unknown"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
