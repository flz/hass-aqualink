from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import logging
import re
import time
import threading

from requests_html import HTMLSession

BASE_URL = 'https://mobile.iaqualink.net/'
ACTION_BASE_URL = BASE_URL + '?actionID=%s'

MIN_SECS_TO_REFRESH = 20

logger = logging.getLogger('aqualink')

class AqualinkDevice(object):
    def update(self):
        self.aqualink_obj.refresh()

class AqualinkSensor(AqualinkDevice):
    def __init__(self, name, entity, value, aqualink_obj):
        self.name = name
        self.entity = entity
        self.value = value
        self.aqualink_obj = aqualink_obj

    def __repr__(self):
        attrs = ["name", "entity", "value"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return "AqualinkSensor(%s)" % ", ".join(attrs)


class AqualinkSwitch(AqualinkDevice):
    def __init__(self, name, entity, state, action, aqualink_obj):
        self.name = name
        self.entity = entity
        self.state = state
        self.action = action
        self.aqualink_obj = aqualink_obj

    @property
    def is_on(self):
        return self.state

    def turn_on(self):
        if not self.is_on:
            self.switch()

    def turn_off(self):
        if self.is_on:
            self.switch()

    def switch(self):
        self.aqualink_obj.session.get(ACTION_BASE_URL % self.action)
        self.aqualink_obj.refresh(force_refresh=True)

    def __repr__(self):
        attrs = ["name", "entity", "state", "action"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return "AqualinkSwitch(%s)" % ", ".join(attrs)


class AqualinkLight(AqualinkSwitch):
    def __repr__(self):
        attrs = ["name", "entity", "state", "action"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return "AqualinkLight(%s)" % ", ".join(attrs)

class Aqualink(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = HTMLSession()
        self.login_link = None
        self.home_link = None
        self.home_cache = None
        self.devices_link = None
        self.devices_cache = None
        self.dev_objs = {}
        self.lock = threading.Lock() 
        self.last_refresh = 0

        self.login()

    def login(self):
            logger.debug("Getting Aqualink start page...")
            start = self.session.get(ACTION_BASE_URL)
            form = start.html.find('form', first=True)
            action = form.xpath('//input[@id = "actionID"]', first=True).attrs['value']
            self.login_link = ACTION_BASE_URL % action
            logger.debug("Login Link: %s" % self.login_link)

            # Make sure our credentials work.
            self.home_cache = self.session.get(self.login_link)
            if len(self.home_cache.html.find("div.temps")) == 0:
                payload = {'userID': self.username, 'userPassword': self.password}
                logger.info("Logging in to Aqualink...")
                self.home_cache = self.session.post(self.login_link, data=payload)
                if len(self.home_cache.html.find("div.temps")) == 0:
                    self.home_link = None
                    self.home_cache = None
                    raise Exception("Check your username and password.")
                else:
                    self.home_link = self.home_cache.html.find('li#tabHeader_1', first=True).absolute_links.pop()
                    logger.debug("Home Link: %s" % self.home_link)

    def refresh(self, force_refresh=False):
        self.lock.acquire()

        # Be nice to Aqualink servers since we rely on polling.
        now = int(time.time())
        delta = now - self.last_refresh
        if delta < MIN_SECS_TO_REFRESH and not force_refresh:
            logger.debug("Only %ds since last refresh. Skipping." % delta)
            self.lock.release()
            return

        logger.debug("Refreshing device list...")

        try:
            if self.home_link is None:
                self.login()
            else:
                self.home_cache = self.session.get(self.home_link)

            self.devices_link = self.home_cache.html.find('li#tabHeader_3', first=True).absolute_links.pop()
            logger.debug("Devices Link: %s" % self.devices_link)

            self.devices_cache = self.session.get(self.devices_link)
        except Exception as e:
            print(e)
            self.lock.release()
            return

        # Keep track of devices in case they change. This might be overkill and likely to work great.
        # Probably would be safer to restart the process altogether.
        previous = set(self.dev_objs.keys())
        seen = set()

        # Find the sensors first.
        temps = self.home_cache.html.find("div.temps")

        for i in temps:
            name = re.sub(r"(Temp).*$", r"\1", i.text)
            entity = name.lower().replace(' ', '_')
            temp = re.sub(r"^.*Temp", "", i.text)
            if temp == "--":
                temp = None
            else:
                temp = temp.rstrip("°F")
            if entity in self.dev_objs:
                self.dev_objs[entity].value = temp
            else:
                ss = AqualinkSensor(name, entity, temp, self)
                self.dev_objs[entity] = ss
            seen.add(entity)

        # Now find the switches for pool/spa.
        # This is a bit convoluted but labels, states and scripts don't live
        # in the same element so we need to find all of them individually and
        # put them together.
        home = self.home_cache.html.find("div#home", first=True)
        labels = home.find("div.inbetween")
        states = home.find("div#home", first=True).find("img")
        scripts = home.find("script")

        labels.pop(0)
        states.pop(0)
        scripts.pop()

        state_map = {
                "/files/images/aux_0_0.png": False,
                "/files/images/aux_0_1.png": True,
                "/files/images/aux_0_3.png": True,
        }

        for label, state, script in zip(labels, states, scripts):
            name = label.find('span', first=True).text
            entity = state.attrs['id']
            state = state_map[state.attrs['src']]
            action = re.match(r".*actionID=(\w+)", script.text).groups()[0]

            if entity in self.dev_objs:
                self.dev_objs[entity].state = state
                self.dev_objs[entity].action = action
            else:
                sw = AqualinkSwitch(name, entity, state, action, self)
                self.dev_objs[entity] = sw
            seen.add(entity)

        # Now go through auxiliary devices. These typically include water
        # features, pool cleaner, lights, ...
        # Here again, we look for labels, states and scripts separately and
        # put them all together.
        devices = self.devices_cache.html.find('div#devices', first=True)
        labels = devices.find('span.row_label')
        states = devices.find('img')
        scripts = devices.find('script')

        for label, state, script in zip(labels, states, scripts):
            name = " ".join([x.capitalize() for x in label.text.split()])
            entity = label.text.lower().replace(' ', '_') + '_state'
            state = state_map[state.attrs['src']]
            action = re.match(r".*actionID=(\w+)", script.text).groups()[0]

            if entity in self.dev_objs:
                self.dev_objs[entity].state = state
                self.dev_objs[entity].action = action
            else:
                # Going to assume that people used sensible names for lights.
                # At least my installer did.
                if "Light" in name:
                    sw = AqualinkLight(name, entity, state, action, self)
                else:
                    sw = AqualinkSwitch(name, entity, state, action, self)
                self.dev_objs[entity] = sw
            seen.add(entity)

        # Get rid of devices that went away.
        missing = previous - seen
        for i in list(missing):
            del(self.dev_objs[i])

        self.last_refresh = int(time.time())
        self.lock.release()
      

    def get_devices(self):
        return self.dev_objs.values()
