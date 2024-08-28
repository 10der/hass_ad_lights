import hassapi as hass
import datetime
from datetime import timedelta

#
# App contol lights
# v.15

DEFAULT_DELAY = 60
DEFAULT_TIMEOUT = 60

DEFAULT_DIM_DELAY = 10
DEFAULT_BRIGHTNESS = 255
DEFAULT_DIM_BRIGHTNESS = 1


class Lights(hass.Hass):
    def initialize(self):
        self.handle = None
        self.profile = None

        if "entity_on" not in self.args:
            self.log("No lights specified, doing nothing")
            return

        self.listen_state(self.light_update, self.args["entity_on"])

        self.light_entity = self.args["entity_on"]

        if "ambient_light_sensor" in self.args:
            self.lux_entity = self.args["ambient_light_sensor"]
            self.listen_state(
                self.lux_update, self.lux_entity)

        else:
            self.lux_entity = None

        if "light_override" in self.args:
            self.light_override = self.args["light_override"]
            if "light_override_force_off" in self.args:
                self.light_override_force_off = self.args["light_override_force_off"]
                if self.light_override_force_off:
                    self.listen_state(
                        self.light_override_update, self.light_override)
            else:
                self.light_override_force_off = False
        else:
            self.light_override = None

        inOneMinute = datetime.datetime.now() + timedelta(minutes=1)
        self.run_every(self.watch_dog, inOneMinute, 1 * 60)

    def get_option(self, profile, name, default_value=None):
        return profile.get(name, default_value)

    def get_current_profile(self):
        # timeDate = self.ADapi.parse_datetime(automation['time'], today = True)

        if "profiles" in self.args:
            for profile_name in self.args["profiles"]:
                profile = self.args["profiles"][profile_name]

                start_time = str(profile.get('start_time', '00:00:00'))
                end_time = str(profile.get('end_time', '00:00:00'))
                if start_time == end_time and start_time == '00:00:00':
                    self.log('Profile (default): {} '.format(profile_name))
                    return profile

                if self.now_is_between(start_time, end_time):
                    # self.log('Profile: {} '.format(profile_name))
                    return profile

            return None
        else:
            start_time = str(self.args.get('start_time', '00:00:00'))
            end_time = str(self.args.get('end_time', '00:00:00'))
            if start_time == end_time and start_time == '00:00:00':
                return self.args

            if self.now_is_between(start_time, end_time):
                return self.args

            return None

    def is_light(self, timestamp=None):
        entity_id = self.args["entity_on"]
        state = self.get_state(entity_id, attribute='all')
        if timestamp:
            return state['state'] == 'on', state['last_changed']
        else:
            return state['state'] == 'on'

    def watch_dog(self, kwargs=None):
        # get current profile
        profile = self.get_current_profile()

        # if no active profile - trying to find in last action
        #if profile is None:
        #    profile = self.profile

        # if no prifiles at all the initialize
        if profile is None:
            profile = {}

        turn_off_mode = self.get_option(profile, "turn_off_mode", True)
        if turn_off_mode:
            if self.is_light():
                if not self.watch_dog_check(profile):
                    self.log('WatchDog: Starting turn off by timeout.')
                    self.light_off()

    def is_sensor_active(self, entity_id, profile):
        state = self.get_state(entity_id, attribute='all')
        last_changed = state['last_changed']
        if state['state'] == 'on':
            return True
        elif state['state'] == 'off':
            time_off = datetime.datetime.now().timestamp(
            ) - self.convert_utc(last_changed).timestamp()
            delay = self.get_option(
                profile, "delay", DEFAULT_DELAY) + DEFAULT_TIMEOUT  # time + 1 minutes
            if time_off > float(delay):
                # self.log('WatchDog: sensor {} is time out'.format(entity_id))
                return False
            else:
                return True
        else:
            # sensor is dead!
            self.log('WatchDog: sensor {} is DEAD!'.format(entity_id))
            return False

    def watch_dog_check(self, profile):
        return True

    def light_update(self, entity, attribute, old, new, kwargs):
        pass

    def lux_update(self, entity, attribute, old, new, kwargs):
        # get current profile
        profile = self.get_current_profile()

        # if no prifiles at all the initialize
        if profile is None:
            profile = {}

        ambient_lux = None
        if "ambient_lux" in self.args:
            ambient_lux = self.args["ambient_lux"]
        ambient_lux_profile = self.get_option(profile, "ambient_lux")
        ambient_lux = ambient_lux_profile or ambient_lux

        if ambient_lux is not None:
            if float(lux_state) <= ambient_lux:
               self.on_lux_allow(True)
            else:
               self.on_lux_allow(False)

    def on_lux_allow(self, action):
        pass

    def light_override_update(self, entity, attribute, old, new, kwargs):
        if new == "on":
            entity_id = self.args["entity_on"]
            self.turn_off(entity_id)

    # Check conditions and constraints
    def checkOnConditions(self, conditionlist: list) -> bool:
        for conditions in conditionlist:
            if not eval(conditions):
                return False
        return True

    def on_action(self):
        # get current profile
        profile = self.get_current_profile()

        if profile is None:
            self.log('The time is not meet...')
            return

        if self.lux_entity:
            lux_state = self.get_state(self.lux_entity)

            ambient_lux = None
            if "ambient_lux" in self.args:
                ambient_lux = self.args["ambient_lux"]
            ambient_lux_profile = self.get_option(profile, "ambient_lux")
            ambient_lux = ambient_lux_profile or ambient_lux

            if ambient_lux is not None:
                if float(lux_state) <= ambient_lux:
                   self.log(f'Lux: {lux_state}')
                else:
                   self.log("Lux constrain on")
                   return

        if self.light_override:
            light_override_state = self.get_state(self.light_override)
            if light_override_state == "on":
                self.log("Override constrain on")
                if self.light_override_force_off:
                    self.light_off()
                return

        if not self.checkOnConditions(self.get_option(profile, "conditions", ['True'])):
            self.log("Profile override constrain on")
            return

        self.profile = profile

        self.cancel()

        self.log("Action ON")

        self.light_on({"profile": profile})

    def off_action(self):

        # if no light the done
        if not self.is_light():
            return

        # cancel the current flow
        self.cancel()

        # get current profile
        profile = self.get_current_profile()

        # if no active profile - trying to find in last action
        if profile is None:
            self.log("No active profile")
            profile = self.profile

        # if no prifiles at all the initialize
        if profile is None:
            self.log("Using default profile")
            profile = {}

        self.log("Action OFF")

        delay = self.get_option(profile, "delay", DEFAULT_DELAY)
        args = {"profile": profile}
        if 'transition' in profile:
            transition = profile['transition']
            delay_dim = self.get_option(transition, "delay", DEFAULT_DIM_DELAY)
            if delay - delay_dim > 0:
                delay = delay - delay_dim
                self.log("Run transition delay")
                self.handle = self.run_in(self.light_dim, delay, **args)
            else:
                self.log("Run turn_off delay (transition error)")
                self.handle = self.run_in(self.light_off, delay, **args)
        else:
            self.log("Run turn_off delay")
            self.handle = self.run_in(self.light_off, delay, **args)

    def light_on(self, kwargs={}):
        entity_id = self.args["entity_on"]
        if 'profile' in kwargs:
            profile = kwargs['profile']
        else:
            profile = {}
        #self.log("In turn_on: {} {} ".format(entity_id, profile))

        if "switch" in entity_id:
            self.turn_on(entity_id)
        else:
            brightness = self.get_option(
                profile, "brightness", DEFAULT_BRIGHTNESS)
            data = self.get_option(profile, "light_data", {
                                   "brightness": brightness})
            self.turn_on(entity_id, **data)

    def light_off(self, kwargs={}):
        entity_id = self.args["entity_on"]

        if 'profile' in kwargs:
            profile = kwargs['profile']
        else:
            profile = {}
        #self.log("In turn_off: {} {} ".format(entity_id, profile))

        # TODO: check is light?

        if "switch" in entity_id:
            self.turn_off(entity_id)
        else:
            turn_off_mode = self.get_option(profile, "turn_off_mode", True)
            if turn_off_mode:
                self.log("Turned {} off".format(entity_id))
                self.turn_off(entity_id)

    def light_dim(self, kwargs={}):
        entity_id = self.args["entity_on"]
        if 'profile' in kwargs:
            profile = kwargs['profile']
        else:
            profile = {}
        #self.log("In transition: {} {} ".format(entity_id, profile))

        if 'transition' in profile:
            transition = profile['transition']
            dim = self.get_option(transition, "dim", DEFAULT_DIM_BRIGHTNESS)
            delay = self.get_option(transition, "delay", DEFAULT_DIM_DELAY)
            self.turn_on(entity_id, brightness=dim)
            args = {"profile": profile}
            self.log("Run turn_off delay: {} ".format(entity_id))
            self.handle = self.run_in(self.light_off, delay, **args)
        else:
            self.log("No transition: {}".format(entity_id))

    def cancel(self):
        if self.handle:
            if self.timer_running(self.handle):
                self.cancel_timer(self.handle)
            self.handle = None
