import logging
import base64

import voluptuous as vol

from homeassistant import config_entries, core, exceptions

from .const import DOMAIN  # pylint:disable=unused-import
from websockets.exceptions import WebSocketException
from .cirrus import connect

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    'host': str,
    'location_id': str,
    'username': str,
    'password': str,
})


async def validate_input(host, username, password):
    credentials = {
        'username': username,
        'password': password
    }

    async with connect(f'wss://{host}/cirrusAPI') as ws:
        session_id = await ws.authenticate(credentials)
        if not session_id:
            raise InvalidAuth
        else:
            return session_id

async def get_access_token(host, session_id, location_id):
    async with connect(f'wss://{host}/cirrusAPI') as ws:
        await ws.authenticate({'sessionId': session_id})
        response = await ws.request({
            'messageType': 'CirrusLocalRequest',
            'localMessageType': 'configAPI',
            'list': [{
                'resourceType': 'BlobDTO',
                'blobType': 'getAccessToken',
                'blobData': base64.b64encode(location_id.encode()).decode()
            }]
        })

        return base64.b64decode(response['list'][0]['blobData']).decode()

async def get_location_name(host, session_id, location_id):
    async with connect(f'wss://{host}/cirrusAPI') as ws:
        await ws.authenticate({'sessionId': session_id})
        async for response in ws.send({ 'messageType': 'GetLocationsRequest' }):
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

                session_id = await validate_input(host, username, password)
                access_token = await get_access_token(host, session_id, location_id)
                location_name = await get_location_name(host, session_id, location_id)

                return self.async_create_entry(
                    title=f'{location_name} ({location_id})',
                    data={
                        'host': host,
                        'location_id': location_id,
                        'access_token': access_token
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


class InvalidAuth(exceptions.HomeAssistantError):
    '''Error to indicate there is invalid auth.'''

class InvalidLocation(exceptions.HomeAssistantError):
    '''Error to indicate that the location was not found.'''
