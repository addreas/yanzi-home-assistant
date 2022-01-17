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
        self._socket = asyncio.Future()

    async def get_device_sources(self):
        self.device_sources = [x async for x in self._get_device_sources()]

    async def _get_device_sources(self):
        ws = await self._socket
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
            raise RuntimeError(
                f'Failed to get list of devices: {gql_response}')

        location = json.loads(gql_response['result'])['data']['location']

        if location['units']['cursor'] != location['units']['endCursor']:
            raise RuntimeError(
                'I\'m unable to handle multiple pages of sensors.')

        key_to_version = {item['key']: item['version']
                          for item in location['inventory']['list']}

        device = location['gateway']
        device['version'] = key_to_version[device['key']]
        for source in device['dataSources']:
            source['did'] = device['unitAddress']['did']
            source['name'] = device['name']
            source['latest'] = None

            yield device, source

        for device in location['units']['list']:
            device['version'] = key_to_version[device['key']]

            for source in device['dataSources']:
                if source['variableName'] in ['log', 'unitState']:
                    # These two are always null for physical devices?
                    continue

                source['did'] = device['unitAddress']['did']
                source['name'] = device['name']
                source['latest'] = None

                yield device, source

            for child in device['chassisChildren']:
                for source in child['dataSources']:
                    source['did'] = child['unitAddress']['did']
                    source['name'] = device['name']
                    source['latest'] = None

                    yield device, source

                    if source['variableName'] == 'totalPowerInst':
                        yield device, {
                            'key': source['key'],
                            'did': source['did'],
                            'name': device['name'],
                            'latest': None,
                            'variableName': 'totalEnergy',
                            'siUnit': 'mWs'
                        }

    async def watch(self):
        log.debug('Starting watch')
        while True:
            try:
                async with connect(f'wss://{self.host}/cirrusAPI') as ws:
                    await ws.authenticate({'accessToken': self.access_token})
                    self._socket.set_result(ws)

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
                self._socket = asyncio.Future()
                await asyncio.sleep(1)
                break
            except Exception as e:
                self._socket = asyncio.Future()
                log.warning(
                    'Restarting ws watch in 10 seconds because of: %s', e, exc_info=e)
                await asyncio.sleep(10)

    async def get_latest(self, did, variable_name):
        ws = await self._socket
        response = await ws.request({
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
        if response['responseCode']['name'] != 'success':
            log.warning('Error when getting latest sample %s/%s %s', did, variable_name, response)
            return None
        if 'sampleListDto' not in response or 'list' not in response['sampleListDto'] or len(response['sampleListDto']['list']) < 1:
            log.warning('Malformed sample response for %s/%s %s', did, variable_name, response)
            return None
        return response['sampleListDto']['list'][0]

    async def control_request_binary(self, did, value):
        ws = await self._socket
        response = await ws.request({
            'messageType': 'control_request',
            'unitAddress': {
                'resourceType': 'UnitAddress',
                'locationId': self.location_id,
                'did': did
            },
            'controlValue': {
                'resourceType': 'ControlValueBinary',
                'value': value
            }
        })

def dsa_to_key(dsa):
    gwdid = dsa['serverDid']
    location_id = dsa['locationId']
    did = dsa['did']
    variable_name = dsa['variableName']['name']
    instance_number = dsa['instanceNumber']

    return f'{gwdid}/{location_id}/{did}/{variable_name}/{instance_number}'


qq_query = '''query {
  location {
    gateway {
      key
      productType
      name
      lifeCycleState
      unitAddress {
        did
        serverDid
      }
      dataSources {
        key
        variableName
        siUnit
      }
    }
    units(filter:[{ name:unitTypeFixed, type: equals, value:"physicalOrChassis"}]) {
      cursor
      endCursor
      list {
        key
        productType
        name
        lifeCycleState

        assetParent {
          name
        }

        unitAddress {
          did
          serverDid
        }

        dataSources {
          key
          variableName
          siUnit
        }

        chassisChildren {
          key
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
