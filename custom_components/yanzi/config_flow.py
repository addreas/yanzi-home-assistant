import logging

import voluptuous as vol

from homeassistant import config_entries

from custom_components.yanzi.errors import InvalidAuth, InvalidLocation

from .const import DOMAIN  # pylint:disable=unused-import
from websockets.exceptions import WebSocketException
from .cirrus import connect
from .tls import get_certificate, get_ssl_context

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    'host': str,
    'location_id': str,
    'username': str,
    'password': str,
})


async def get_location_name(host, ssl_context, location_id):
    async with connect(f'wss://{host}/cirrusAPI', ssl=ssl_context) as ws:
        async for response in ws.send({'messageType': 'GetLocationsRequest'}):
            for location in response['list']:
                if location['locationAddress']['locationId'] == location_id:
                    return location['name']

        raise InvalidLocation


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    '''Handle a config flow for yanzi.'''

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    async def async_step_user(self, user_input=None):
        '''Handle the initial step.'''
        errors = {}
        if user_input is not None:
            try:
                host = user_input['host']
                username = user_input['username']
                password = user_input['password']
                location_id = user_input['location_id']

                await self.async_set_unique_id(f'yanzi://{username}@{host}/{location_id}')
                self._abort_if_unique_id_configured()

                private_key, certificates = await get_certificate(username, password)
                ssl_context = get_ssl_context(private_key, certificates)
                location_name = await get_location_name(host, ssl_context, location_id)

                return self.async_create_entry(
                    title=f'{location_name} ({location_id})',
                    data={
                        'host': host,
                        'location_id': location_id,
                        'private_key': private_key,
                        "certificates": certificates,
                    })
            except WebSocketException as e:
                _LOGGER.exception(e)
                errors['base'] = 'cannot_connect'
            except InvalidAuth as e:
                _LOGGER.exception(e)
                errors['base'] = 'invalid_auth'
            except InvalidLocation as e:
                _LOGGER.exception(e)
                errors['base'] = 'invalid_location'
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.exception(e)
                errors['base'] = 'unknown'

        return self.async_show_form(
            step_id='user', data_schema=DATA_SCHEMA, errors=errors
        )
