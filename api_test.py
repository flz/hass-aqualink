import asyncio
import unittest
from unittest.mock import MagicMock

from api import AqualinkLightToggle


def async_run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

class TestAqualinkLightToggle(unittest.TestCase):
    def setUp(self) -> None:
        system = MagicMock()
        data = {'name': 'Test Pool Light', 'state': '0', 'aux': '1'}
        self.obj = AqualinkLightToggle(system, data)

    def test_switch(self) -> None:
        async_run(self.obj.turn_off())
        self.obj.system.mock.set_aux.assert_not_called()
        async_run(self.obj.turn_on())
        self.obj.system.set_aux.assert_called_once()
