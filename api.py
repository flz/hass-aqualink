import aiohttp
import asyncio
from enum import Enum, auto, unique
import logging
import re
import sys
import time
from typing import Dict, List, Optional
import threading
import traceback


AQUALINK_API_KEY = 'EOOEMOW4YR6QNB07'

AQUALINK_LOGIN_URL = 'https://support.iaqualink.com/users/sign_in.json'
AQUALINK_DEVICES_URL = 'https://support.iaqualink.com/devices.json'
AQUALINK_SESSION_URL = 'https://iaqualink-api.realtime.io/v1/mobile/session.json'

AQUALINK_COMMAND_GET_DEVICES = 'get_devices'
AQUALINK_COMMAND_GET_HOME = 'get_home'
AQUALINK_COMMAND_GET_ONETOUCH = 'get_onetouch'
AQUALINK_COMMAND_SET_AUX = 'set_aux'
AQUALINK_COMMAND_SET_LIGHT = 'set_light'
AQUALINK_COMMAND_SET_POOL_HEATER = 'set_pool_heater'
AQUALINK_COMMAND_SET_POOL_PUMP = 'set_pool_pump'
AQUALINK_COMMAND_SET_SOLAR_HEATER = 'set_solar_heater'
AQUALINK_COMMAND_SET_SPA_HEATER = 'set_spa_heater'
AQUALINK_COMMAND_SET_SPA_PUMP = 'set_spa_pump'
AQUALINK_COMMAND_SET_TEMPS = 'set_temps'

AQUALINK_HTTP_HEADERS = {
    'User-Agent': 'iAquaLink/70 CFNetwork/901.1 Darwin/17.6.0', 
    'Content-Type': 'application/json',
    'Accept': '*/*'
}

@unique
class AqualinkState(Enum):
    OFF = '0'
    ON = '1'
    ENABLED = '3'

# XXX - I don't know the exact values per type. The enum is pretty much a
# placeholder. If you know what type of lights you have and have debugging
# on, please submit an issue to GitHub with the details so I can update the
# code.
@unique
class AqualinkLightType(Enum):
    JANDY_LED_WATERCOLORS = auto()
    JANDY_COLORS = auto()
    HAYWARD_COLOR_LOGIC = auto()
    PENTAIR_INTELLIBRITE = auto()
    PENTAIR_SAM_SAL = auto()

# XXX - These values are probably LightType-specific but they're all I have
# at the moment. I can see this changing into a color profile system later.
class AqualinkLightEffect(Enum):
    NONE = '0'
    ALPINE_WHITE = '1'
    SKY_BLUE = '2'
    COBALT_BLUE = '3'
    CARIBBEAN_BLUE = '4'
    SPRING_GREEN = '5'
    EMERALD_GREEN = '6'
    EMERALD_ROSE = '7'
    MAGENTA = '8'
    VIOLENT = '9'
    SLOW_COLOR_SPLASH = '10'
    FAST_COLOR_SPLASH = '11'
    USA = '12'
    FAT_TUESDAY = '13'
    DISCO_TECH = '14'
 
Payload = Dict[str, str]
                
MIN_SECS_TO_REFRESH = 10

logger = logging.getLogger('aqualink')


class AqualinkDevice(object):
    def __init__(self, system, data):
        self.system = system
        self.data = data

    def __repr__(self) -> str:
        attrs = ["name", "data"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return f'{self.__class__.__name__}({" ".join(attrs)})'

    @property
    def label(self) -> str:
        if 'label' in self.data:
            label = self.data['label']
            return " ".join([x.capitalize() for x in label.split()])
        else:
            label = self.data['name']
            return " ".join([x.capitalize() for x in label.split('_')])

    @property
    def state(self) -> str:
        return self.data['state']

    @property
    def name(self) -> str:
        return self.data['name']

    @classmethod
    def from_data(self, system, data: Dict[str, Dict[str, str]]) -> 'AqualinkDevice':
        if data['name'].endswith('_heater'):
            cls = AqualinkHeater
        elif data['name'].endswith('_set_point'):
            cls = AqualinkThermostat
        elif data['name'].endswith('_pump'):
            cls = AqualinkPump
        elif data['name'].startswith('aux_'):
            if data['type'] == '2':
                cls = AqualinkColorLight
            elif data['type'] == '1':
                # XXX - This is a wild guess.
                cls = AqualinkDimmableLight
            elif 'LIGHT' in data['label']:
                cls = AqualinkLightToggle
            else:
                cls = AqualinkAuxToggle
        else:
            cls = AqualinkSensor

        return cls(system, data)

class AqualinkSensor(AqualinkDevice):
    pass


class AqualinkToggle(AqualinkDevice):
    @property
    def is_on(self) -> bool:
        return AqualinkState(self.state) in \
            [AqualinkState.ON, AqualinkState.ENABLED] if self.state else False

    async def turn_on(self) -> None:
        if not self.is_on:
            await self.toggle()

    async def turn_off(self) -> None:
        if self.is_on:
            await self.toggle()

    async def toggle(self) -> None:
        raise NotImplementedError()


class AqualinkPump(AqualinkToggle):
    async def toggle(self) -> None:
        await self.system.set_pump(f'set_{self.name}')
        

class AqualinkHeater(AqualinkToggle):
    async def toggle(self) -> None:
        await self.system.set_heater(f'set_{self.name}')


class AqualinkAuxToggle(AqualinkToggle):
    async def toggle(self) -> None:
        await self.system.set_aux(self.data['aux'])


# Using AqualinkLight as a Mixin so we can use isinstance(dev, AqualinkLight).
class AqualinkLight(object):
    @property
    def brightness(self) -> Optional[int]:
        raise NotImplementedError()

    @property
    def effect(self) -> Optional[str]:
        raise NotImplementedError()

    @property
    def is_dimmer(self) -> bool:
        return self.brightness != None

    @property
    def is_color(self) -> bool:
        return self.effect != None


class AqualinkLightToggle(AqualinkLight, AqualinkAuxToggle):
    @property
    def brightness(self) -> Optional[bool]:
        return None

    @property
    def effect(self) -> Optional[int]:
        return None


# XXX - This is largely untested since I don't have any of those.
class AqualinkDimmableLight(AqualinkLight, AqualinkDevice):
    @property
    def effect(self) -> Optional[int]:
        return None

    async def set_brightness(self, brightness: int) -> None:
        # Brightness only works in 25% increments.
        if brightness not in [0, 25, 50, 75, 100]:
            msg = f"{brightness}% isn't a valid percentage. Only use 25% increments."
            logger.warning(msg)
            return

        # XXX - Unclear what parameters to send here.
        # data = {}
        # await self.system.set_light(data)

    async def turn_on(self, level: int = 100) -> None:
        await self.set_brightness(level)

    async def turn_off(self) -> None:
        await self.set_brightness(0)


# XXX - Not implemented as I don't have any of those.
class AqualinkColorLight(AqualinkLight, AqualinkDevice):
    pass


class AqualinkThermostat(AqualinkDevice):
    @property
    def temp(self) -> str:
        # Spa takes precedence for temp1 if present.
        if self.name.startswith('pool') and self.system.has_spa:
            return 'temp2'
        return 'temp1'

    async def set_temperature(self, temperature: int) -> None:
        if temperature not in range(34, 105):
            msg = f"{temperature}F isn't a valid temperature (34-104F)."
            logger.warning(msg)
            return
        
        data = {self.temp: temperature}
        await self.system.set_temps(data)


class AqualinkSystem(object):
    def __init__(self,
                 aqualink: 'Aqualink',
                 serial: str):
        self.aqualink = aqualink
        self.serial = serial
        self.devices = {}
        self.has_spa = None
        self.lock = threading.Lock()
        self.last_refresh = 0
        
    @property
    async def info(self) -> Payload:
        systems = await self.aqualink.get_systems()
        for x in systems:
            if x['serial_number'] == self.serial:
                return x
        else:
            raise Exception(f"System not found for serial {self.serial}.")

    async def get_devices(self):
        if not self.devices:
            await self.update()
        return self.devices

    async def update(self) -> None:
        self.lock.acquire()

        # Be nice to Aqualink servers since we rely on polling.
        now = int(time.time())
        delta = now - self.last_refresh
        if delta < MIN_SECS_TO_REFRESH:
            logger.debug(f"Only {delta}s since last refresh.")
            self.lock.release()
            return

        try:
            r1 = await self.aqualink._send_home_screen_request(self.serial)
            r2 = await self.aqualink._send_devices_screen_request(self.serial)
            await self._parse_home_response(r1)
            await self._parse_devices_response(r2)
        except Exception as e:
            logger.error(f"Unhandled exception: {e}")
            for line in traceback.format_exc().split('\n'):
                logger.error(line)
        else:
            self.last_refresh = int(time.time())

        # Keep track of the presence of the spa so we know whether temp1 is
        # for the spa or the pool. This is pretty ugly.
        if 'spa_set_point' in self.devices:
            self.has_spa = True
        else:
            self.has_spa = False

        self.lock.release()

    async def _parse_home_response(self, response: aiohttp.ClientResponse) -> None:
        data = await response.json()

        if data['home_screen'][0]['status'] == 'Offline':
            logger.warning(f"Status for system {self.serial} is Offline.")
            return

        # Make the data a bit flatter.
        devices = {}
        for x in data['home_screen'][4:]:
            name = list(x.keys())[0]
            state = list(x.values())[0] 
            attrs = {'name': name, 'state': state}
            devices.update({name: attrs})

        for k, v in devices.items():
            if k in self.devices:
                self.devices[k].data['state'] = v['state']
            else:
                self.devices[k] = AqualinkDevice.from_data(self, v)

    async def _parse_devices_response(self, response: aiohttp.ClientResponse) -> None:
        data = await response.json()

        if data['devices_screen'][0]['status'] == 'Offline':
            logger.warning(f"Status for system {self.serial} is Offline.")
            return

        # Make the data a bit flatter.
        devices = {}
        for i, x in enumerate(data['devices_screen'][3:], 1):
            attrs = {'aux': f'{i}', 'name': list(x.keys())[0]}
            for y in list(x.values())[0]:
                attrs.update(y)
            devices.update({f'aux_{i}': attrs})

        for k, v in devices.items():
            if k in self.devices:
                self.devices[k].data['state'] = v['state']
            else:
                self.devices[k] = AqualinkDevice.from_data(self, v)

    async def set_pump(self, command: str) -> None:
        r = await self.aqualink.set_pump(self.serial, command)
        await self._parse_home_response(r)

    async def set_heater(self, command: str) -> None:
        r = await self.aqualink.set_heater(self.serial, command)
        await self._parse_home_response(r)

    async def set_temps(self, temps: Payload) -> None:
        r = await self.aqualink.set_temps(self.serial, temps)
        await self._parse_home_response(r)

    async def set_aux(self, aux: str) -> None:
        r = await self.aqualink.set_aux(self.serial, aux)
        await self._parse_devices_response(r)

    async def set_light(self, data: Payload) -> None:
        r = await self.aqualink.set_light(self.serial, data)
        await self._parse_devices_response(r)
        

class Aqualink(object):
    def __init__(self,
                 username: str,
                 password: str,
                 session: aiohttp.ClientSession):
        self.username = username
        self.password = password
        self.session = session

        self.session_id = None
        self.token = None
        self.user_id = None

        self.lock = threading.Lock() 
        self.last_refresh = 0

    async def _send_request(self,
                      url: str,
                      method: str = 'get',
                      **kwargs) -> aiohttp.ClientResponse:
        logger.debug(f'-> {method.upper()} {url} {kwargs}')
        r = await self.session.request(method,
                                       url,
                                       headers=AQUALINK_HTTP_HEADERS,
                                       **kwargs)
        if r.status == 200:
            logger.debug(f"<- {r.status} {r.reason} - {url}")
        else:
            logger.warning(f"<- {r.status} {r.reason} - {url}")
        return r

    async def _send_login_request(self) -> aiohttp.ClientResponse:
        data = {
            "api_key": AQUALINK_API_KEY,
            "email": self.username,
            "password": self.password
        }
        return await self._send_request(AQUALINK_LOGIN_URL,
                                        method='post',
                                        json=data)

    async def login(self) -> None:
        r = await self._send_login_request()

        if r.status == 200:
            data = await r.json()
            self.session_id = data['session_id']
            self.token = data['authentication_token']
            self.user_id = data['id']
        else:
            raise Exception("Login failed: {r.status} {r.reason}")

    async def _send_systems_request(self) -> aiohttp.ClientResponse:
        params = {
            "api_key": AQUALINK_API_KEY,
            "authentication_token": self.token,
            "user_id": self.user_id,
        }
        params = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{AQUALINK_DEVICES_URL}?{params}"
        return await self._send_request(url)

    async def get_systems(self) -> list:
        r = await self._send_systems_request()

        if r.status == 200:
            data = await r.json()
            return data
        else:
            raise Exception(f"Unable to retrieve systems list: {r.status} {r.reason}")

    async def _send_session_request(self,
                                    serial: str,
                                    command: str,
                                    params: Optional[Payload] = None) -> aiohttp.ClientResponse:
        if not params:
            params = {}
            
        params.update({
            "actionID": "command",
            "command": command,
            "serial": serial,
            "sessionID": self.session_id,
        })
        params = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{AQUALINK_SESSION_URL}?{params}"
        return await self._send_request(url)

    async def _send_home_screen_request(self, serial) -> aiohttp.ClientResponse:
        r = await self._send_session_request(serial, AQUALINK_COMMAND_GET_HOME)
        return r

    async def _send_devices_screen_request(self, serial) -> aiohttp.ClientResponse:
        r = await self._send_session_request(serial, AQUALINK_COMMAND_GET_DEVICES)
        return r

    async def set_pump(self,
                       serial: str,
                       command: str) -> aiohttp.ClientResponse:
        r = await self._send_session_request(serial, command)
        return r

    async def set_heater(self,
                         serial: str,
                         command: str) -> aiohttp.ClientResponse:
        r = await self._send_session_request(serial, command)
        return r

    async def set_temps(self,
                        serial: str,
                        temps: Payload) -> aiohttp.ClientResponse:
        r = await self._send_session_request(serial, AQUALINK_COMMAND_SET_TEMPS, temps)
        return r

    async def set_aux(self,
                      serial: str,
                      aux: str) -> aiohttp.ClientResponse:
        command = AQUALINK_COMMAND_SET_AUX + '_' + aux.replace('aux_', '')
        r = await self._send_session_request(serial, command)
        return r

    async def set_light(self,
                        serial: str,
                        command: str,
                        data: Payload) -> aiohttp.ClientResponse:
        r = await self._send_session_request(serial, AQUALINK_COMMAND_SET_LIGHT, data)
        return r


async def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <username> <password>")
        sys.exit(1)

    session = aiohttp.ClientSession()
    aqualink = Aqualink(username=sys.argv[1], password=sys.argv[2], session=session)
    await aqualink.login()
    data = await aqualink.get_systems()
    pool = AqualinkSystem(aqualink, data[0]['serial_number'])
    await pool.update()
    data = await pool.get_devices()
    print(data)
    await session.close()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
