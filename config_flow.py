import logging
import base64

import voluptuous as vol

from homeassistant import config_entries, core, exceptions

from .const import DOMAIN  # pylint:disable=unused-import
from websockets.exceptions import WebSocketException
from .cirrus import connect

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    "host": str,
    "username": str,
    "password": str,
    "location_id": str
})


async def validate_input(host, username, password):
    credentials = {
        "username": username,
        "password": password
    }

    async with connect(f"wss://{host}/cirrusAPI") as ws:
        return await ws.authenticate(credentials)

async def get_access_token(host, session_id, location_id):
    async with connect(f"wss://{host}/cirrusAPI") as ws:
        await ws.authenticate({"sessionId": session_id})
        response = await ws.request({
            "messageType": "CirrusLocalRequest",
            "localMessageType": "configAPI",
            "list": [{
                "resourceType": "BlobDTO",
                "blobType": "getAccessToken",
                "blobData": base64.b64encode(location_id.encode()).decode()
            }]
        })

        return base64.b64decode(response['list'][0]['blobData']).decode()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for yanzi."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                host = user_input['host']
                username = user_input['username']
                password = user_input['password']
                location_id = user_input['location_id']

                await self.async_set_unique_id(f"yanzi://{username}@{host}/{location_id}")
                self._abort_if_unique_id_configured()

                session_id = await validate_input(host, username, password)
                access_token = await get_access_token(host, session_id, location_id)

                return self.async_create_entry(
                    title=str(location_id),
                    data={
                        "host": host,
                        "location_id": location_id,
                        "access_token": access_token
                    })
            except WebSocketException as e:
                _LOGGER.exception(e)
                errors["base"] = "cannot_connect"
            except AssertionError as e:
                _LOGGER.exception(e)
                errors["base"] = "invalid_auth"
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.exception(e)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
