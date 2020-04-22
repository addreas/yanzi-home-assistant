import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .location import YanziLocation

__LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

# For your initial PR, limit it to 1 platform.
PLATFORMS = ['sensor', 'binary_sensor']

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the yanzi component."""
    hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up yanzi from a config entry."""
    location = YanziLocation(entry.data['host'], entry.data[
                             'access_token'], entry.data['location_id'])
    hass.data[DOMAIN][entry.entry_id] = location

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component))

    def notify(key, sample):
        hass.bus.async_fire('yanzi_data', {'key': key, 'sample': sample})

    location._hass_watcher_task = asyncio.create_task(location.watch(notify))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
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
        location = hass.data[DOMAIN].pop(entry.entry_id)
        location._hass_watcher_task.cancel()

    return unload_ok
