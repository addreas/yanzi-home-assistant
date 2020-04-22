import asyncio
import logging
import time

from .const import DOMAIN
from .yanzi_entity import YanziEntity
__LOGGER = logging.getLogger(__name__)

BINARY_VARIABLE_NAMES = [
    'motion'
]

async def async_setup_entry(hass, entry, async_add_entities):
    location = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        YanziSensor(location, device, source)
        async for device, source in location.get_device_sources()
        if source['variableName'] in BINARY_VARIABLE_NAMES
    ])

log = logging.getLogger(__name__ + '.YanziSensor')


class BinaryYanziSensor(YanziEntity):
    async def on_sample(self):
        # We need to refresh ourselves after 60 seconds, since we use
        # time.time() in self.state
        await asyncio.sleep(60)
        await self.async_update_ha_state()

    @property
    def device_class(self):
        vn = self.source['variableName']

        if vn == 'motion':
            return 'motion'

    @property
    def state(self):
        vn = self.source['variableName']
        l = self.source['latest']

        if vn == 'motion':
            return l['timeLastMotion'] / 1000 > time.time() - 60
        else:
            return l['value'] if l and 'value' in l else None

    @property
    def state_attributes(self):
        return self.source['latest']
