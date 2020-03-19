"""Module for an MQTT adapter"""

import asyncio
# pylint: disable=redefined-builtin
from concurrent.futures import TimeoutError
import paho.mqtt.client as mqtt
import voluptuous as vol
from homecontrol.dependencies.entity_types import Item


class MQTTAdapter(Item):
    """The MQTT adapter"""
    config_schema = vol.Schema({
        vol.Required("host", default="localhost"): str,
        vol.Required("port", default=1883): vol.Coerce(int)
    }, extra=vol.ALLOW_EXTRA)

    async def init(self):
        """Initialise the adapter"""
        self.connected = asyncio.Event()
        self.client = mqtt.Client()
        self.client.connect_async(self.cfg["host"], self.cfg["port"])
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.loop_start()
        try:
            await asyncio.wait_for(self.connected.wait(), 3)
        except TimeoutError:
            return False

    async def stop(self):
        """Stop the mqtt session"""
        if self.connected:
            self.client.disconnect()
        self.core.loop.call_soon(
            self.core.loop.run_in_executor(None, self.client.loop_stop))

    def on_connect(self, _, userdata, flags, result):
        """Handle a connection"""
        self.connected.set()
        self.core.event_engine.broadcast_threaded(
            "mqtt_connected", mqtt_adapter=self)

    def on_disconnect(self, _, userdata, mid) -> None:
        """Handle on_disconnect"""
        self.connected.clear()

    def on_message(self, _, userdata, msg):
        """Handle a message"""
        self.core.event_engine.broadcast_threaded(
            "mqtt_message_received",
            mqtt_adapter=self,
            message=msg)
