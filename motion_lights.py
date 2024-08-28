from lights import Lights

#
# App contol lights
# v.15


class MotionLights(Lights):
    def initialize(self):
        super().initialize()
        self.depends_on_module("lights")

        # Subscribe to motion sensors
        if "sensors" in self.args:
            self.log("Use multi-sensor mode")
            for entity_id in self.args["sensors"]:
                self.listen_state(self.motion_callback, entity_id)
        elif "sensor" in self.args:
            self.listen_state(self.motion_callback, self.args["sensor"])
        else:
            self.log("No motion sensor specified, doing nothing")

        # Subscribe to door sensors
        if "doors" in self.args:
            self.log("Use multi-sensor mode")
            for entity_id in self.args["doors"]:
                self.listen_state(self.door_callback, entity_id)
        elif "door" in self.args:
            self.listen_state(self.door_callback, self.args['door'])
        else:
            self.log("No door sensor specified, doing nothing")

    def watch_dog_check(self, profile):
        if self.watch_dog_motion(profile):
            return True
        if self.watch_dog_door(profile):
            return True
        return False

    def watch_dog_motion(self, profile):
        if "sensors" in self.args:
            results = []
            for entity_id in self.args["sensors"]:
                result = self.is_sensor_active(entity_id, profile)
                results.append(result)
            return any(results)
        elif "sensor" in self.args:
            entity_id = self.args["sensor"]
            return self.is_sensor_active(entity_id, profile)
        else:
            return False

    def watch_dog_door(self, profile):
        if "doors" in self.args:
            results = []
            for entity_id in self.args["doors"]:
                result = self.is_sensor_active(entity_id, profile)
                results.append(result)
            return any(results)
        if "door" in self.args:
            entity_id = self.args["door"]
            return self.is_sensor_active(entity_id, profile)
        else:
            return False

    def motion_callback(self, entity, attribute, old, new, kwargs):
        if new == "on":
            self.on_action()

        if new == "off":
            self.off_action()

    def door_callback(self, entity, attribute, old, new, kwargs):
        if new == "on":
            self.on_action()

        if new == "off":
            self.off_action()

    def on_lux_allow(self, action):
        # get current profile
        profile = self.get_current_profile()

        # if no prifiles at all the initialize
        if profile is None:
            profile = {}

        if not action:
            self.light_off()
        else:
            results = []
            for entity_id in self.args["sensors"]:
                result = self.is_sensor_active(entity_id, profile)
                results.append(result)
            # is motion is active?
            if any(results):
                self.light_on()
