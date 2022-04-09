import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.yanzi.tls import get_certificate, get_ssl_context

from .const import DOMAIN
from .location import YanziLocation

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

# For your initial PR, limit it to 1 platform.
PLATFORMS = ['sensor', 'binary_sensor', 'switch']


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the yanzi component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up yanzi from a config entry."""

    ssl_context = get_ssl_context(
        entry.data['private_key'], entry.data['certificates'])

    location = YanziLocation(
        entry.data['host'],
        ssl_context,
        entry.data['location_id'])

    hass.data[DOMAIN][entry.entry_id] = location

    async def watch():
        counter_key = 'sensor.yanzi_sample_counter_' + \
            entry.data['location_id']
        count = 0
        async for key, sample in location.watch():
            hass.bus.async_fire('yanzi_data', {'key': key, 'sample': sample})
            count = count + 1
            hass.states.async_set(counter_key, count, {
                                  'unit_of_measurement': 'samples'})

    async def sources():
        while location.is_loaded:
            try:
                await location.get_device_sources()
                for component in PLATFORMS:
                    hass.async_create_task(
                        hass.config_entries.async_forward_entry_setup(entry, component))
            finally:
                await asyncio.sleep(60*10)

    location._hass_watcher_task = asyncio.create_task(watch())
    location._hass_sources_task = asyncio.create_task(sources())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    location = hass.data[DOMAIN].pop(entry.entry_id)

    location.unload()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(
                    entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        location._hass_watcher_task.cancel()
        location._hass_sources_task.cancel()

    return unload_ok
