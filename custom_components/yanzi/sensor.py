import struct

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .binary_sensor import BINARY_VARIABLE_NAMES
from .switch import SWITCH_VARIABLE_NAMES
from .yanzi_entity import YanziEntity

IGNORED_VARIABLE_NAMES = ['onOffTransition']


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    location = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        YanziSensor(location, device, source)
        for device, source in location.device_sources
        if source['variableName'] not in BINARY_VARIABLE_NAMES and
        source['variableName'] not in SWITCH_VARIABLE_NAMES and
        source['variableName'] not in IGNORED_VARIABLE_NAMES
    ])


class YanziSensor(YanziEntity):

    @property
    def should_poll(self):
        if self.source['variableName'] == 'battery':
            return True

        return False

    @property
    def unit_of_measurement(self):
        u = self.source['siUnit']
        vn = self.source['variableName']

        return UNIT_BY_VARIABLE_NAME.get(vn, SI_UNITS.get(u, u))

    @property
    def state(self):
        vn = self.source['variableName']
        l = self.source['latest']

        if l is None:
            return None

        if vn == 'up':
            return l['deviceUpState']['name']
        elif vn == 'positionLog':
            return l['longitude'], l['latitude']
        elif vn == 'battery':
            return int(l['percentFull'])
        elif vn == 'soundPressureLevel':
            return l['max']
        elif vn == 'totalpowerInst':
            return l['instantPower']
        elif vn == 'totalEnergy':
            # seconds -> hours, millis -> kilo
            return l['totalEnergy'] / (3600 * 1000)
        elif 'value' in l:
            return l['value']
        elif vn in l:
            return l[vn]
        else:
            return None

    @property
    def state_class(self):
        if self.source['variableName'] == 'totalEnergy':
            return "total_increasing"

        return "measurement"

    @property
    def state_attributes(self):
        if self.source['variableName'] == 'statistics' and self.source['latest'] is not None:
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


SI_UNITS = {
    'NA': None,
    'celsius': '°C',
    'kelvin': 'K',
    'percent': '%',
    'mlux': 'mlx',
    'watt': 'W',
    'mWs': 'Wh'
}

UNIT_BY_VARIABLE_NAME = {
    'battery': '%'
}
