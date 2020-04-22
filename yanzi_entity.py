import asyncio
import logging
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

log = logging.getLogger(__name__)


class YanziEntity(Entity):

    def __init__(self, location, device, source):
        self.location = location
        self.device = device
        self.source = source

    async def async_added_to_hass(self):
        log.debug('async_added_to_hass %s', self.source['key'])
        async def filter_data(event):
            if event.data['key'] == self.source['key']:
                self.source['latest'] = event.data['sample']

                if self.source['variableName'] == 'uplog':
                    self.device['lifeCycleState'] = self.source['latest']['deviceUpState']['name']

                await self.async_update_ha_state()

                await self.on_sample(self.source['latest'])

        self.hass.bus.async_listen('yanzi_data', filter_data)

    async def on_sample(self, sample):
        pass

    @property
    def should_poll(self):
        return False

    @property
    def unique_id(self):
        return self.source['key']

    @property
    def name(self):
        return self.source['name'] + ' ' + self.source['variableName']

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.device['key'])},
            "name": self.device['name'],
            "manufacturer": "Yanzi Networks",
            "model": get_device_model(self.device['productType']),
            "sw_version": self.device['version'],
            # "via_device": (DOMAIN, self.device['unitAddress']['serverDid']),
        }

    @property
    def available(self):
        return self.device['lifeCycleState'] == 'present'


def get_device_model(product_type):
    return {
        '0090DA03010104A3': 'Yanzi LED',
        '0090DA03010104A1': 'Yanzi LED',
        '0090DA03010104B0': 'Yanzi Motion',
        '0090DA03010104A0': 'Yanzi Climate',
        '0090DA03010104D0': 'Yanzi Distance',
        '0090DA03010104D3': 'Yanzi Distance',
        '0090DA03010104D4': 'Yanzi Distance',
        '0090DA0301010491': 'Yanzi Plug',
        '0090DA0301010492': 'Yanzi Plug',
        '0090DA03010104C1': 'Yanzi Air',
        '0090DA03010104A5': 'Yanzi Light',
        '0090DA0301010510': 'Yanzi Decibel',
        '0090DA0301020422': 'Yanzi Gateway',
        '0090DA0301020421': 'Yanzi Gateway',
        '0090DA0301020423': 'Yanzi Gateway',
        '0090DA0301020424': 'Yanzi Gateway',
        '0090DA0301010521': 'Yanzi Motion+',
        '0090DA0301010522': 'Yanzi Comfort',
        '0090DA0301010523': 'Yanzi Climate+',
        '0090DA0301010524': 'Yanzi Presence',
        '0090DA0301028030': 'Axis Camera 1',
        '0090DA0301028002': 'Axis Camera 2',
        '0090DA0301028021': 'Sercom Camera',
        '0090DA0301020010': 'IoT Access Point',
        '0090DA0301020011': 'IoT Access Point',
        '0090DA0301020012': 'IoT Access Point',
        '0090DA0302010014': 'Border Router',
        '0090DA0301088010': 'Footfall Camera',
        '0090DA03010104D5': 'Katrin Towel Dispenser',
        '0090DA03010104D6': 'Katrin Hand Towel M Dispenser',
        '0090DA03010104D7': 'Katrin Toilet Dispenser',
        '0090DA03010104D9': 'Katrin Soap 1000 Dispenser',
        '0090DA03010104D8': 'Katrin Soap 1000 Dispenser',
        '0090DA03010104DB': 'Katrin Towel Dispenser',
        '0090DA03010104DC': 'Katrin Smart Hand Towel M',
        '0090DA0301038031': 'Carlo Gavassi EM24',
        '0090DA0301048052': 'CG Modbus Ethernet SIU',
        '0090DA0301038041': 'Humidity MODBUS',
        '0090DA0301010532': 'Yanzi Presence Mini',
        '0090DA0301010502': 'Yanzi IoT Mesh',
    }.get(product_type, f'Unknown product {product_type}')
