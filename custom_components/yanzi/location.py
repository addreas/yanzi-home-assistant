import asyncio
import logging
import time
import json

from concurrent.futures import CancelledError

from .cirrus import connect

log = logging.getLogger(__name__)


class YanziLocation:
    def __init__(self, host, access_token, location_id):
        self.host = host
        self.access_token = access_token
        self.location_id = location_id

        self.device_sources = {}

    async def get_device_sources(self, get_latest):
        self.device_sources = list(await self._get_device_sources(get_latest))

    async def _get_device_sources(self, get_latest):
        location_address = {
            'resourceType': 'LocationAddress', 'locationId': self.location_id}

        async with connect(f"wss://{self.host}/cirrusAPI?get_device_sources") as ws:
            await ws.authenticate({'accessToken': self.access_token})

            gql_response = await ws.request({
                'messageType': 'GraphQLRequest',
                'locationAddress': {
                    'resourceType': 'LocationAddress',
                    'locationId': self.location_id,
                },
                'query': qq_query,
                'vars': {},
                'isLS': False
            })

            if 'result' not in gql_response:
                raise RuntimeError(f'Failed to get list of devices: {gql_response}')

            location = json.loads(gql_response['result'])['data']['location']

            if location['units']['cursor'] != location['units']['endCursor']:
                raise RuntimeError(
                    'Im unable to handle multiple pages of sensors.')

            key_to_version = {item['key']: item['version']
                              for item in location['inventory']['list']}

            for device in location['units']['list']:
                device['version'] = key_to_version[device['key']]

                for source in device['dataSources']:
                    if source['variableName'] in ['log', 'unitState']:
                        # These two are always null for physical devices?
                        continue

                    source['name'] = device['name']
                    source['unitTypeFixed'] = 'physicalOrChassis'
                    source['latest'] = None

                    yield device, source

                for child in device['chassisChildren']:
                    for source in child['dataSources']:
                        source['name'] = device['name']
                        source['unitTypeFixed'] = child['unitTypeFixed']
                        source['latest'] = None

                        yield device, source

    async def watch(self):
        log.debug('Starting watch')
        while True:
            try:
                async with connect(f'wss://{self.host}/cirrusAPI?watch') as ws:
                    await ws.authenticate({'accessToken': self.access_token})
                    self._ws = ws

                    subscribe_request = {
                        'messageType': 'SubscribeRequest',
                        'unitAddress': {
                            'resourceType': 'UnitAddress',
                            'locationId': self.location_id
                        },
                        'subscriptionType': {
                            'resourceType': 'SubscriptionType',
                            'name': 'data'
                        },
                    }

                    async for message in ws.subscribe(subscribe_request):

                        dsa = message['list'][0]['dataSourceAddress']
                        sample = message['list'][0]['list'][0]

                        yield dsa_to_key(dsa), sample

                        if dsa['variableName']['name'] == 'temperatureK':
                            emulated_dsa = {
                                **dsa,
                                'variableName': {
                                    **dsa['variableName'],
                                    'name': 'temperatureC'
                                }
                            }
                            emulated_sample = {
                                **sample,
                                'value': round(sample['value'] - 273.15, 2)
                            }

                            yield dsa_to_key(emulated_dsa), emulated_sample

            except CancelledError:
                self._ws = None
                await asyncio.sleep(1)
                break
            except Exception as e:
                self._ws = None
                log.warning(
                    'Restarting ws watch in 10 seconds because of: %s', e, exc_info=e)
                await asyncio.sleep(10)

    async def get_latest(self, did, variable_name):
        response = await self._ws.request({
            'messageType': 'GetSamplesRequest',
            'dataSourceAddress': {
                'resourceType': 'DataSourceAddress',
                'locationId': self.location_id,
                'did': did,
                'variableName': {
                    'resourceType': 'VariableName',
                    'name': variable_name
                }
            },
            'timeSerieSelection': {
                'resourceType': 'TimeSerieSelection',
                'timeStart': int(time.time() * 1000),
                'numberOfSamplesBeforeStart': 1,
            }
        })
        res = response['sampleListDto'].get('list', [None])[0]
        if res is None:
            log.warning('Got None sample %s', response)
        return res


def dsa_to_key(dsa):
    gwdid = dsa['serverDid']
    location_id = dsa['locationId']
    did = dsa['did']
    variable_name = dsa['variableName']['name']
    instance_number = dsa['instanceNumber']

    return f'{gwdid}/{location_id}/{did}/{variable_name}/{instance_number}'

qq_query = '''query {
  location {
    units(filter:[{ name:unitTypeFixed, type: equals, value:"physicalOrChassis"}]) {
      cursor
      endCursor
      list {
        key
        productType
        name
        lifeCycleState

        unitAddress {
          did
        }
        dataSources {
          key
          variableName
          siUnit
        }

        chassisChildren {
          unitTypeFixed
          unitAddress {
            did
          }
          dataSources {
            key
            variableName
            siUnit
          }
        }
      }
    }
    inventory {
      list {
        key
        version
      }
    }
  }
}'''
