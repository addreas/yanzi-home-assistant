import asyncio
import struct

from .const import DOMAIN
from .binary_sensor import BINARY_VARIABLE_NAMES
__LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    location = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        YanziSensor(location, device, source)
        async for device, source in location.get_device_sources()
        if source['variableName'] not in BINARY_VARIABLE_NAMES
    ])


class YanziSensor(YanziEntity):

    @property
    def device_class(self):
        vn = self.source['variableName']
        return DEVICE_CLASSES.get(vn)

    @property
    def unit_of_measurement(self):
        u = self.source['siUnit']

        return u if u != 'NA' else None

    @property
    def state(self):
        vn = self.source['variableName']
        l = self.source['latest']

        if vn == 'uplog':
            return l['deviceUpState']['name']
        elif vn == 'positionLog':
            return l['longitude'], l['latitude']
        elif vn == 'battery':
            return l['percentFull']
        else:
            return l['value'] if l and 'value' in l else None

    @property
    def state_attributes(self):
        if self.source['variableName'] == 'statistics':
            # Grabbed from pan, not sure if still correct...
            # uint8_t version;
            # uint8_t parent_rssi; /* version > 0: Parent RSSI */
            # uint16_t parent_switches; /* Number of parent switches */
            # uint32_t parent_time; /* Time since last parent switch (seconds) */
            # uint8_t parent[8]; /* 8 right most bytes of parent IP address*/
            # uint16_t parent_rank; /* Rank of the parent */
            # uint16_t parent_metric; /* Link metric to the parent */
            # uint8_t free_routes;    /* version > 0: Number of free routes */
            # uint8_t free_neighbors; /* version > 0: Number of free neighbors */
            # uint8_t reserved_future[10];

            res = struct.unpack('BBHIBBBBBBBBHHBBBBBBBBBBBB',
                                bytes.fromhex(self.source['latest']['value']))
            return {
                'version': res[0],
                'parent_rssi': res[1],
                'parent_switches': res[2],
                'parent_time': res[3],
                'parent': res[4:12],
                'parent_rank': res[12],
                'parent_metric': res[13],
                'free_routes': res[14],
                'free_neighbors': res[15],
                'reserved_future': res[16:]
            }

        return self.source['latest']

DEVICE_CLASSES = {
    'temperatureC': 'temperature',
    'temperatureK': 'temperature',
    'relativeHumidity': 'humidity',
    'carbonDioxide': 'carbon_dioxide',
    'volatileOrganicCompound': 'volatile_organic_compounds',
    'pressure': 'pressure',
    'illuminance': 'illuminance',
    'battery': 'battery',
}
