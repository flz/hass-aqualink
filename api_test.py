import unittest
from unittest.mock import MagicMock

from api import AqualinkLight

class TestAqualinkLight(unittest.TestCase):
    def setUp(self) -> None:
        self.obj = AqualinkLight('Test', 'test', False, 'action', MagicMock())

    def test_switch(self) -> None:
        self.obj.state = False
        self.obj.turn_off()
        self.obj.aqualink.refresh.assert_not_called()
        self.obj.turn_on()
        self.obj.aqualink.refresh.assert_called_once()