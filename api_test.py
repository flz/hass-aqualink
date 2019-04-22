import asyncio
import asynctest
from .api import AqualinkLightToggle


class TestAqualinkLightToggle(asynctest.TestCase):
    def setUp(self) -> None:
        system = asynctest.MagicMock()
        system.set_aux = asynctest.CoroutineMock(return_value=None)
        data = {'name': 'Test Pool Light', 'state': '0', 'aux': '1'}
        self.obj = AqualinkLightToggle(system, data)

    @asynctest.strict
    async def test_switch(self) -> None:
        await self.obj.turn_off()
        self.obj.system.set_aux.assert_not_called()
        await self.obj.turn_on()
        self.obj.system.set_aux.assert_called_once()
