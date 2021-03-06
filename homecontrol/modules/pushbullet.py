"""Pushbullet module"""
import json
import logging

import aiohttp

import voluptuous as vol
from homecontrol.dependencies.action_decorator import action
from homecontrol.dependencies.entity_types import Item

SPEC = {
    "name": "Pushbullet"
}

LOGGER = logging.getLogger(__name__)

BASE_URL = "https://api.pushbullet.com/v2"
PUSH_URL = BASE_URL + "/pushes"
ME_URL = BASE_URL + "/users/me"

MESSAGE_SCHEMA = vol.Schema({
    vol.Required("type", default="note"): str,
    vol.Optional("title"): str,
    vol.Optional("body"): str,
    vol.Optional("url"): str
})


class Pushbullet(Item):
    """The Pushbullet item"""
    config_schema = vol.Schema({
        vol.Required("access_token"): str
    }, extra=vol.ALLOW_EXTRA)

    @action("send_message")
    async def send_message(self, **data):
        """Sends a message"""
        data = json.dumps(MESSAGE_SCHEMA(data))
        async with aiohttp.ClientSession(loop=self.core.loop) as session:
            await session.post(PUSH_URL, data=data, headers={
                "Access-Token": self.cfg["access_token"],
                "Content-Type": "application/json"
            })
