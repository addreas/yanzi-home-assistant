import asyncio
import logging

from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .cirrus import Cirrus

__LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    __LOGGER.debug('async_setup_entry %s', entry.data)

    location = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([YanziSensor(location, device, source) async for device, source in location.get_device_sources()])

log = logging.getLogger(__name__ + '.YanziSensor')
class YanziSensor(Entity):
    def __init__(self, location, device, source):
        self.location = location
        self.device = device
        self.source = source

    async def async_added_to_hass(self):
        log.debug('async_added_to_hass %s', self.source['key'])
        async def filter_data(event):
            if event.data['key'] == self.source['key']:
                self.source['latest'] = event.data['sample']

                await self.async_update_ha_state()
                # self.async_write_ha_state()

        self.hass.bus.async_listen('yanzi_data', filter_data)

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
    def device_class(self):
        vn = self.source['variableName']

        if vn == 'temperatureC': return 'temperature'
        elif vn == 'temperatureK': return 'temperature'
        elif vn == 'relativeHumidity': return 'humidity'
        elif vn == 'carbonDioxide': return 'carbon_dioxide'
        elif vn == 'volatileOrganicCompound': return 'volatile_organic_compounds'
        elif vn == 'pressure': return 'pressure'
        elif vn == 'illuminance': return 'illuminance'
        elif vn == 'battery': return 'battery'
        # elif vn == 'soundPressureLevel': return l['sound']
        # elif vn == 'motion': return l['timeLastMotion']
        # elif vn == 'uplog': return l['state']
        # elif vn == 'positionLog': return { 'longitude': l['longitude'], 'latitude': l['latitude'] }


    @property
    def unit_of_measurement(self):
        u = self.source['siUnit']
        if u != 'NA':
            return u

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

    @property
    def state(self):
        vn = self.source['variableName']
        l = self.source['latest']

        if vn == 'battery': return l['percentFull']

        return l['value'] if l and 'value' in l else None

        # if vn == 'temperatureC': return l['temperature']
        # elif vn == 'temperatureK': return l['value']
        # elif vn == 'relativeHumidity': return l['humidity']
        # elif vn == 'carbonDioxide': return l['cO2']
        # elif vn == 'volatileOrganicCompound': return l['vOC']
        # elif vn == 'pressure': return l['pressure']
        # elif vn == 'illuminance': return l['illuminance']
        # elif vn == 'soundPressureLevel': return l['sound']
        # elif vn == 'motion': return l['timeLastMotion']
        # elif vn == 'uplog': return l['state']


    @property
    def state_attributes(self):
        return self.source['latest']

def get_device_class(variable_name):
    return {
        'battery': ('battery', 'mV'),
        'relativeHumidity': ('humidity', '%'),
        'illuminance': ('illuminance', 'mLx'),
        'signal_strength': ('signal_strength', 'dBm'),
        'temperatureK': ('temperature', 'K'),
        'timestamp': ('timestamp', 'ISO8601'),
        'instantPower': ('power', 'kW'),
        'pressure': ('pressure', 'mbar'),
    }[variable_name]

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
