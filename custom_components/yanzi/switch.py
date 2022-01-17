import asyncio
import time

from .const import DOMAIN
from .yanzi_entity import YanziEntity
from homeassistant.components.switch import SwitchEntity

SWITCH_VARIABLE_NAMES = ['onOffOutput']


async def async_setup_entry(hass, entry, async_add_entities):
    location = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        YanziSwitch(location, device, source)
        for device, source in location.device_sources
        if source['variableName'] in SWITCH_VARIABLE_NAMES
    ])


class YanziSwitch(SwitchEntity, YanziEntity):
    @property
    def is_on(self):
        vn = self.source['variableName']
        l = self.source['latest']

        if l is None:
            return None

        if vn == 'onOffOutput':
            return l['value']['name'] == 'on'

    @property
    def state_attributes(self):
        return self.source['latest']

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self.location.control_request_binary(self.source['did'], self.source['variableName'], 'onn')

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self.location.control_request_binary(self.source['did'], self.source['variableName'], 'off')

