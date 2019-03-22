import logging
import re
import sys
import time
from typing import Dict, List
import threading
import traceback

from requests import Response
from requests_html import HTMLSession, Element


BASE_URL = 'https://mobile.iaqualink.net/'
ACTION_BASE_URL = BASE_URL + '?actionID=%s'

MIN_SECS_TO_REFRESH = 20

logger = logging.getLogger('aqualink')

DEVICE_STATE_MAP = {
    # Those are regular lights...
    "/files/images/aux_0_0.png": False,
    "/files/images/aux_0_1.png": True,
    "/files/images/aux_0_3.png": True,
    # ... and those are dimmable lights.
    "/files/images/aux_1_0.png": False,
    "/files/images/aux_1_1.png": True,
}      


class AqualinkDevice(object):
    def update(self) -> None:
        self.aqualink.refresh()

class AqualinkSensor(AqualinkDevice):
    def __init__(self,
                 aqualink: 'Aqualink',
                 name: str,
                 entity: str,
                 state: int):
        self.name = name
        self.entity = entity
        self.state = state
        self.aqualink = aqualink

    def __repr__(self) -> str:
        attrs = ["name", "entity", "state"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return "AqualinkSensor(%s)" % ", ".join(attrs)


class AqualinkSwitch(AqualinkDevice):
    def __init__(self,
                 aqualink: 'Aqualink',
                 name: str,
                 entity: str,
                 state: str,
                 action: str):
        self.name = name
        self.entity = entity
        self.state = state
        self.action = action
        self.aqualink = aqualink

    @property
    def is_on(self) -> bool:
        return self.state

    def turn_on(self) -> None:
        if not self.is_on:
            self.toggle()

    def turn_off(self) -> None:
        if self.is_on:
            self.toggle()

    def toggle(self) -> None:
        self.aqualink.request(ACTION_BASE_URL % self.action)
        self.aqualink.refresh(force_refresh=True)

    def __repr__(self) -> str:
        attrs = ["name", "entity", "state", "action"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return "AqualinkSwitch(%s)" % ", ".join(attrs)


class AqualinkLight(AqualinkSwitch):
    def __init__(self,
                 aqualink: 'Aqualink',
                 name: str,
                 entity: str,
                 state: str,
                 action: str,
                 brightness: int = None):
        self.name = name
        self.entity = entity
        self.state = state
        self.action = action
        self.brightness = brightness
        self.aqualink = aqualink

    @property
    def is_dimmable(self) -> bool:
        return self.brightness != None

    def set_brightness(self, level: int) -> None:
        if not self.is_dimmable:
            msg = f"{self.name} isn't a dimmable light. Can't set brightness."
            logger.warning(msg)
            return

        # Brightness only works in 25% increments.
        if level not in [0, 25, 50, 75, 100]:
            msg = f"{level}% isn't a valid percentage. Only use 25% increments."
            logger.warning(msg)
            return

        url = ACTION_BASE_URL % self.action + "&level=%d" % level
        self.aqualink.request(url)
        self.aqualink.refresh(force_refresh=True)

    def turn_on(self, level: int = 100) -> None:
        if self.is_dimmable:
            self.set_brightness(level)
        else:
            AqualinkSwitch.turn_on(self)

    def turn_off(self) -> None:
        if self.is_dimmable:
            self.set_brightness(0)
        else:
            AqualinkSwitch.turn_off(self)

    def __repr__(self) -> str:
        attrs = ["name", "entity", "state", "brightness", "action"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return "AqualinkLight(%s)" % ", ".join(attrs)


class AqualinkThermostat(AqualinkDevice):
    def __init__(self,
                 aqualink: 'Aqualink',
                 name: str,
                 entity: str,
                 state: str,
                 action: str):
        self.aqualink = aqualink
        self.name = name
        self.entity = entity
        self.state = state
        self.action = action

    def set_target(self, target: int) -> None:
        if target not in range(34, 105):
            msg = f"{target}F isn't a valid temperature (34-104F)."
            logger.warning(msg)
            return

        url = ACTION_BASE_URL % self.action + '&%s=%s' % (self.entity, target)
        self.aqualink.request(url)
        self.aqualink.refresh()

    def __repr__(self) -> None:
        attrs = ["name", "entity", "state", "action"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return "AqualinkThermostat(%s)" % ", ".join(attrs)


class Aqualink(object):
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = HTMLSession()
        self.login_link = None
        self.home_link = None
        self.home_cache = None
        self.devices_link = None
        self.devices_cache = None
        self._devices = {}
        self.lock = threading.Lock() 
        self.last_refresh = 0

        self.login()

    def request(self, url: str, method: str = 'get', **kwargs) -> Response:
        r = self.session.request(method, url, **kwargs)
        if r.status_code == 200:
            logger.debug(f"<- {r.status_code} {r.reason} - {url}")
        else:
            logger.warning(f"<- {r.status_code} {r.reason} - {url}")
        return r

    def login(self) -> None:
            logger.debug("Getting Aqualink start page...")
            start = self.request(ACTION_BASE_URL)
            form = start.html.find('form', first=True)
            action = form.xpath('//input[@id = "actionID"]', first=True).attrs['value']
            self.login_link = ACTION_BASE_URL % action
            logger.debug("Login Link: %s" % self.login_link)

            # Make sure our credentials work.
            self.home_cache = self.request(self.login_link)
            if len(self.home_cache.html.find("div.temps")) == 0:
                payload = {'userID': self.username, 'userPassword': self.password}
                logger.info("Logging in to Aqualink...")
                self.home_cache = self.request(self.login_link, 'post', data=payload)
                if len(self.home_cache.html.find("div.temps")) == 0:
                    self.home_link = None
                    self.home_cache = None
                    raise Exception("Check your username and password.")
                else:
                    self.home_link = self.home_cache.html.find('li#tabHeader_1', first=True).absolute_links.pop()
                    logger.debug("Home Link: %s" % self.home_link)


    def refresh(self, force_refresh=False) -> None:
        self.lock.acquire()

        # Be nice to Aqualink servers since we rely on polling.
        now = int(time.time())
        delta = now - self.last_refresh
        if delta < MIN_SECS_TO_REFRESH and not force_refresh:
            self.lock.release()
            return

        try:
            self._refresh()
        except Exception as e:
            logger.error(f"Unhandled exception: {e}")
            for line in traceback.format_exc().split('\n'):
                logger.error(line)
        else:
            self.last_refresh = int(time.time())

        self.lock.release()


    def _refresh(self, force_refresh=False) -> None:
        logger.debug("Refreshing device list...")

        if self.home_link is None:
            self.login()
        else:
            self.home_cache = self.request(self.home_link)

        self.devices_link = self.home_cache.html.find('li#tabHeader_3', first=True).absolute_links.pop()
        logger.debug("Devices Link: %s" % self.devices_link)

        self.devices_cache = self.request(self.devices_link)

        # Keep track of devices in case they change. This might be overkill and likely to work great.
        # Probably would be safer to restart the process altogether.
        previous = set(self._devices.keys())
        seen = set()

        home = self.home_cache.html.find("div#home", first=True)

        elements = home.find("div.top,div.inbetween,script")

        # Remove the last element that's a script we're not interested in.
        elements.pop()

        def _parse_temperatures(
            e: Element,
            devices: Dict[str, AqualinkDevice]
        ) -> List[str]:
            temps = self.home_cache.html.find("div.temps")

            sensors = []
            for i in temps:
                name = re.sub(r"(Temp).*$", r"\1", i.text)
                entity = name.lower().replace(' ', '_')
                temp = re.sub(r"^.*Temp", "", i.text)
                if temp == "--":
                    temp = None
                else:
                    temp = int(temp.rstrip("°F"))
                if entity in devices:
                    devices[entity].state = temp
                else:
                    ss = AqualinkSensor(self, name, entity, temp)
                    devices[entity] = ss
                sensors += [entity]
            return sensors

        def _parse_set_temperatures(
            e: Element,
            devices: Dict[str, AqualinkDevice]
        ) -> List[str]:
            # First, open the sub-page.
            sub = self.request(BASE_URL + (e.links.pop()))

            # Then get the action link to set thermostats. Same for all of them.
            script = sub.html.find('script')[-2]
            action = re.match(r".*actionID=(\w+)&temp.*", script.text).groups()[0]

            control = sub.html.find('div.set_temp_label')

            thermostats = []

            for c in control:
                (name, temp) = c.text.split("\n")
                temp = int(temp.rstrip("°F"))
                entity = c.find('span')[1].attrs['id']
                if entity in devices:
                    devices[entity].state = temp
                    devices[entity].action = action
                else:
                    ts = AqualinkThermostat(self, name, entity, temp, action)
                    devices[entity] = ts
                thermostats += [entity]

            return thermostats
            
        # Go through all the elements on the page.
        for e in elements:
            if e.tag == 'script':
                continue

            if 'top' in e.attrs['class']:
                # Current Temperatures.
                seen |= set(_parse_temperatures(e, self._devices))
                continue

            if 'inbetween' in e.attrs['class']:
                # Set Temperatures for Pool/Spa heaters.
                # This "Set Temperatures" string seems to be safe to use.
                if e.text == 'Set Temperatures':
                    seen |= set(_parse_set_temperatures(e, self._devices))
                    continue

                # At this point, we're pretty sure it's a toggle.
                # The 'inbetween' element gives us the name/state. The
                # following 'script' element gives the link to flip it.
                pass


        # XXX - This code needs to be made more robust, like the devices page.
        # Now find the switches for pool/spa.
        # This is a bit convoluted but labels, states and scripts don't live
        # in the same element so we need to find all of them individually and
        # put them together.
        labels = home.find("div.inbetween")
        states = home.find("div#home", first=True).find("img")
        scripts = home.find("script")

        labels.pop(0)
        states.pop(0)
        scripts.pop()

        for label, state, script in zip(labels, states, scripts):
            name = label.find('span', first=True).text
            entity = state.attrs['id'].replace('_state', '')
            state = DEVICE_STATE_MAP[state.attrs['src']]
            action = re.match(r".*actionID=(\w+)", script.text).groups()[0]

            if entity in self._devices:
                self._devices[entity].state = state
                self._devices[entity].action = action
            else:
                sw = AqualinkSwitch(self, name, entity, state, action)
                self._devices[entity] = sw
            seen.add(entity)

        # Now go through auxiliary devices. These typically include water
        # features, pool cleaner, lights, ...
        # Here again, we look for labels, states and scripts separately and
        # put them all together.
        devices = self.devices_cache.html.find('div#devices', first=True)

        objs = []
        for e in devices.find('div.inbetween,script'):
            if e.tag == 'div':
                label = e.find('span.row_label', first=True)
                name = " ".join([x.capitalize() for x in label.text.split()])
                entity = label.text.lower().replace(' ', '_')
                state = e.find('img', first=True)
                state = DEVICE_STATE_MAP[state.attrs['src']]
                # Create a Light
                if len(e.links) > 0:
                    # Device is a dimmable light.
                    sub = re.match(r".*actionID=(\w+)", e.links.pop()).groups()[0]
                    # Browse sub-menu. Find the dimming action url.
                    sub_cache = self.request(ACTION_BASE_URL % sub)
                    script = sub_cache.html.find('script')[-1]
                    cur = sub_cache.html.find('span.button-dimmer-selected', first=True)
                    cur = int(cur.attrs['id'].split('_')[-1])
                    action = re.match(r".*actionID=(\w+)&level=0.*", script.text).groups()[0]
                    sw = AqualinkLight(self, name, entity, state, action, brightness=cur)
                    objs += [sw]
            else:
                action = re.match(r".*actionID=(\w+)", e.text).groups()[0]
                # This is script with an action for the previous element.
                # Going to assume that people used sensible names for lights.
                # At least my installer did.
                if 'Light' in name:
                    sw = AqualinkLight(self, name, entity, state, action)
                else:
                    sw = AqualinkSwitch(self, name, entity, state, action)
                objs += [sw]

        for obj in objs:
            entity = obj.entity
            if entity in self._devices:
                self._devices[entity].state = obj.state
                self._devices[entity].action = obj.action
                if type(obj) == AqualinkLight and obj.is_dimmable:
                    self._devices[entity].brightness = obj.brightness
            else:
                self._devices[entity] = obj
            seen.add(entity)

        # Get rid of devices that went away.
        missing = previous - seen
        for i in list(missing):
            del(self._devices[i])

    @property
    def devices(self) -> List[AqualinkDevice]:
        return self._devices.values()


def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <username> <password>")
        sys.exit(1)

    aqualink = Aqualink(username=sys.argv[1], password=sys.argv[2])
    aqualink.refresh()
    print(aqualink._devices)
    return 0

if __name__ == "__main__":
    sys.exit(main())
