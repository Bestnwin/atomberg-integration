"""The Atomberg integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .api import AtombergCloudAPI
from .const import CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import AtombergDataUpdateCoordinator
from .udp_listener import UDPListener

PLATFORMS: list[Platform] = [
    Platform.FAN,
    Platform.SWITCH,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Atomberg from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    api = AtombergCloudAPI(
        hass, entry.data[CONF_API_KEY], entry.data[CONF_REFRESH_TOKEN]
    )

    # Test API connection
    status = await api.test_connection()
    if not status:
        raise ConfigEntryNotReady("Failed to initialize Atomberg integration.")

    udp_listener = UDPListener(hass)
    coordinator = AtombergDataUpdateCoordinator(
        hass=hass, api=api, udp_listener=udp_listener
    )
    hass.data[DOMAIN][entry.entry_id] = coordinator


    async def handle_increase_speed(call):
        """Handle the increase speed service."""
        entity_id = call.data["entity_id"]
        entity = hass.data[DOMAIN][entry.entry_id].get_entity(entity_id)
        if entity and isinstance(entity, AtombergFanEntity):
            await entity.async_increase_speed()

    async def handle_decrease_speed(call):
        """Handle the decrease speed service."""
        entity_id = call.data["entity_id"]
        entity = hass.data[DOMAIN][entry.entry_id].get_entity(entity_id)
        if entity and isinstance(entity, AtombergFanEntity):
            await entity.async_decrease_speed()

    hass.services.async_register(
        DOMAIN,
        "increase_speed",
        handle_increase_speed,
        schema=vol.Schema({vol.Required("entity_id"): cv.entity_id}),
    )

    hass.services.async_register(
        DOMAIN,
        "decrease_speed",
        handle_decrease_speed,
        schema=vol.Schema({vol.Required("entity_id"): cv.entity_id}),
    )

    try:
        await udp_listener.start()
    except Exception:
        raise ConfigEntryError("Failed to start udp listener.")  # noqa: B904

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)



    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: AtombergDataUpdateCoordinator = hass.data[DOMAIN].pop(
            entry.entry_id
        )
        coordinator.udp_listener.close()

    return unload_ok
