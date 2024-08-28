from motion_lights import MotionLights
import datetime
from lights import DEFAULT_DELAY

#
# App contol lights
# v.14

class TimeoutLights(MotionLights):

    def initialize(self):
        super().initialize()
        #self.depends_on_module("motion_lights")

    def watch_dog_check(self, profile):
        if "time_control" in self.args:
            if self.args["time_control"]:
                current_profile = self.get_current_profile()
                if not current_profile:
                    self.log('WatchDog: lighting time out (time).')
                    return False

        is_active = super(TimeoutLights, self).watch_dog_check(profile)
        if is_active:
            return True

        return self.watch_dog_check_manual(profile)

    def watch_dog_check_manual(self, profile):

        # if not light - exit
        is_light, last_light_changed = self.is_light(True)
        if not is_light:
            return False

        delay = self.get_option(
            profile, "delay", DEFAULT_DELAY)

        # lets check lighting
        time_off = datetime.datetime.now().timestamp(
        ) - self.convert_utc(last_light_changed).timestamp()
        if time_off > float(delay):
            self.log('WatchDog: lighting time out.')
            return True

        return False

    def motion_callback(self, entity, attribute, old, new, kwargs):
        if "manual" in self.args:
            if self.args["manual"]:
                return

        super(TimeoutLights, self).motion_callback(entity, attribute, old, new, kwargs)

    def door_callback(self, entity, attribute, old, new, kwargs):
        if "manual" in self.args:
            if self.args["manual"]:
                return

        super(TimeoutLights, self).door_callback(
            entity, attribute, old, new, kwargs)
