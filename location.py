import asyncio
import logging
import time
import json


from .cirrus import connect

log = logging.getLogger(__name__)

class YanziLocation:
    def __init__(self, host, access_token, location_id):
        self.host = host
        self.access_token = access_token
        self.location_id = location_id

    async def get_device_sources(self):
        log.debug('Called get_device_sources')
        location_address = { 'resourceType': 'LocationAddress', 'locationId': self.location_id }

        async with connect(f"wss://{self.host}/cirrusAPI?one") as ws:
            await ws.authenticate({ 'accessToken': self.access_token })
            gql_response = await ws.request({
                'messageType':'GraphQLRequest',
                'locationAddress': {
                    'resourceType': 'LocationAddress',
                    'locationId': self.location_id,
                },
                'query': qq_query,
                'vars': {},
                'isLS': False
            })

            location = json.loads(gql_response['result'])['data']['location']

            if location['units']['cursor'] != location['units']['endCursor']:
                raise RuntimeError('Im unable to handle multiple pages of sensors.')

            key_to_version = { item['key']: item['version'] for item in location['inventory']['list'] }

            for device in location['units']['list']:
                device['version'] = key_to_version[device['key']]

                for source in device['dataSources']:
                    if source['variableName'] in ['log', 'unitState', 'statistics']:
                        continue

                    source['name'] = device['name']
                    source['unitTypeFixed'] = 'physicalOrChassis'

                    yield device, source

                for child in device['chassisChildren']:
                    for source in child['dataSources']:
                        if source['variableName'] in ['temperatureK']:
                            continue

                        source['name'] = device['name']
                        source['unitTypeFixed'] = child['unitTypeFixed']

                        yield device, source

    async def watch(self, notify_update=lambda key, sample: None):
        log.debug('Starting watch')
        while True:
            try:
                async with connect(f'wss://{self.host}/cirrusAPI?two') as ws:
                    await ws.authenticate({'accessToken': self.access_token})
                    log.debug('Authenticated!!')
                    async for message in ws.subscribe({'messageType': 'SubscribeRequest'}):
                        key = dsa_to_key(message['list'][0]['dataSourceAddress'])
                        await notify_update(key, message['list'][0]['list'][0])

            except Exception as e:
                log.warning('Restarting ws watch in 10 seconds because of: %s', e)
                await asyncio.sleep(10)

            log.warning('I dont know why im here')

    async def get_latest(self, did):
        async with connect(f'wss://{self.host}/cirrusAPI') as ws:
            await ws.authenticate({'accessToken': self.access_token})
            response = await ws.request({
                'messageType': 'GetSamplesRequest',
                'dataSourceAddress': {
                    'resourceType': 'DataSourceAddress',
                    'locationId': self.location_id,
                    'did': did
                },
                'timeSerieSelection': {
                    'resourceType': 'TimeSerieSelection',
                    'timeStart': int(time.time() * 1000),
                    'numberOfSamplesBeforeStart': 1,
                }
            })
            # log.debug(response)
            return response['sampleListDto'].get('list', [None])[0]

def dsa_to_key(dsa):
    gwdid = dsa['serverDid']
    location_id = dsa['locationId']
    did = dsa['did']
    variable_name = dsa['variableName']
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

        dataSources {
          key
          variableName
          siUnit
          latest {
            time
            resourceType
            ... on SampleUpState { state }
            ... on SamplePosition { longitude, latitude }
          }
        }

        chassisChildren {
          unitTypeFixed
          dataSources {
            key
            variableName
            siUnit
            latest {
              time
              ... on SampleTemp { temperature }
              ... on SampleHumidity { humidity }
              ... on SampleCO2 { cO2 }
              ... on SampleVOC { vOC }
              ... on SamplePressure { pressure }
              ... on SampleIlluminance { illuminance }
              ... on SampleSoundPressureLevel { sound: max }

              ... on SampleMotion { timeLastMotion, counter }
            }
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
