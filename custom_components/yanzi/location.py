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

    async def get_device_sources(self):
        location_address = {
            'resourceType': 'LocationAddress', 'locationId': self.location_id}

        async with connect(f"wss://{self.host}/cirrusAPI?one") as ws:
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
                    source['latest'] = await self.get_latest(ws, device['unitAddress']['did'], source['variableName'])

                    yield device, source

                for child in device['chassisChildren']:
                    for source in child['dataSources']:
                        source['name'] = device['name']
                        source['unitTypeFixed'] = child['unitTypeFixed']
                        source['latest'] = await self.get_latest(ws, child['unitAddress']['did'], source['variableName'])

                        yield device, source

    async def watch(self, notify_update=lambda key, sample: None):
        log.debug('Starting watch')
        while True:
            try:
                async with connect(f'wss://{self.host}/cirrusAPI?two') as ws:
                    await ws.authenticate({'accessToken': self.access_token})
                    async for message in ws.subscribe({
                        'messageType': 'SubscribeRequest',
                        'unitAddress': {
                            'resourceType': 'UnitAddress',
                            'locationId': self.location_id
                        },
                        'subscriptionType': {
                            'resourceType': 'SubscriptionType',
                            'name': 'data'
                        },
                    }):
                        key = dsa_to_key(message['list'][0][
                                         'dataSourceAddress'])
                        notify_update(key, message['list'][0]['list'][0])

            except CancelledError:
                await asyncio.sleep(1)
                break
            except Exception as e:
                log.warning(
                    'Restarting ws watch in 10 seconds because of: %s', e, exc_info=e)
                await asyncio.sleep(10)

    async def get_latest(self, ws, did, variable_name):
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
