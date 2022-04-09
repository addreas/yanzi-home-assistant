
from homeassistant import exceptions


class InvalidAuth(exceptions.HomeAssistantError):
    '''Error to indicate there is invalid auth.'''


class InvalidLocation(exceptions.HomeAssistantError):
    '''Error to indicate that the location was not found.'''
