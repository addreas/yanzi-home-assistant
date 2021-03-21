import asyncio
import time

from .const import DOMAIN
from .yanzi_entity import YanziEntity
from homeassistant.components.binary_sensor import BinarySensorEntity

BINARY_VARIABLE_NAMES = [
    'uplog',
    'motion'
]

async def async_setup_entry(hass, entry, async_add_entities):
    location = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        BinaryYanziSensor(location, device, source)
        for device, source in location.device_sources
        if source['variableName'] in BINARY_VARIABLE_NAMES
    ])

class BinaryYanziSensor(BinarySensorEntity, YanziEntity):
    async def on_sample(self, sample):
        # We need to refresh ourselves after 60 seconds, since we use
        # time.time() in self.state
        await asyncio.sleep(60)
        await self.async_update_ha_state()

    @property
    def device_class(self):
        vn = self.source['variableName']

        if vn == 'motion':
            return 'motion'
        elif vn == 'uplog':
            return 'connectivity'

    @property
    def is_on(self):
        vn = self.source['variableName']
        l = self.source['latest']

        if l is None:
            return None

        if vn == 'motion':
            return l['timeLastMotion'] / 1000 > time.time() - 60
        elif vn  == 'uplog':
            return l['deviceUpState']['name'] in ['up', 'goingUp']

    @property
    def state_attributes(self):
        return self.source['latest']
