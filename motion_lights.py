"""AD: Motion lights."""

from typing import Any
import datetime
from datetime import timedelta
import global_module

# pylint: disable=import-error
# pylint: disable=W0201
# pylint: disable=too-many-arguments
import hassapi as hass  # type: ignore

# SUPERVISOR = "a855815cb80b4592beb9bdb1a28597c6"

DEFAULT_NAME = "profile"


class MotionLights(hass.Hass):
    """Motion lights class."""

    def initialize(self):
        """AD initialize."""

        self.depends_on_module([global_module])

        self.sensors = self.args.get("sensors", [])
        self.lights = self.args.get("lights", None)
        self.ambient_sensor = self.args.get("ambient_light_sensor", None)
        self.light_overrides = self.args.get("light_override", [])
        self.light_override_force_off = self.args.get(
            "light_override_force_off", False)
        self.time_control = self.args.get("time_control", False)
        self.conditions = self.args.get("conditions", ["True"])

        self.default_ambient_lux = int(self.args.get("lux", 5))
        self.default_ambient_lux_off = int(
            self.args.get("lux_control_off", self.default_ambient_lux))
        self.default_ambient_lux_control = self.args.get(
            "lux_control", False)
        #
        self.handle = None
        self._profile = {"profile_name": None}

        # init sensors and lights
        self.handle_user = False
        if self.lights is not None:
            for light in self.lights:
                self.listen_state(
                    self.light_off_cancel_timer_handler,
                    entity_id=light)  # attribute="context"
                self.listen_state(
                    self.light_off_cancel_timer_handler, attribute="brightness")
        else:
            self.log("No lights specified, doing nothing")
            return

        if isinstance(self.sensors, str):
            self.sensors = self.sensors.split(",")

        for sensor in self.sensors:
            self.listen_state(self.motion_handler, sensor)

        if self.ambient_sensor is not None:
            self.listen_state(self.ambient_handler, self.ambient_sensor)

        for sensor in self.light_overrides:
            if len(sensor.split(",")) > 1:
                sensor = sensor.split(",")[0].strip()
            self.listen_state(self.light_override_handler, sensor)

        self.watch_dog_handler(dict(initial=True))
        in_one_minute = datetime.datetime.now() + timedelta(minutes=1)
        self.run_every(self.watch_dog_handler, in_one_minute, 1 * 60)

        self.log("Motion lights started...")

    def __getattr__(self, name):
        return self._profile.get(name)

    def motion_handler(self, entity, attribute, old, new, kwargs):  # pylint: disable=unused-argument
        """Motion calback handler."""

        if new not in ["on", "off"]:
            return

        self.do_action(new == "on")

    def do_action(self, on: bool):
        """ do action"""

        check = self.constraint_check(self.conditions)
        if on and not check:
            self.log(f"Constraints is active. Action: {on}")
            return

        overrides = self.check_light_overrides(self.light_overrides)
        if overrides:
            self.log(f"Lights overridden. Action: {on}")
            return

        if not self.check_time(self.on_time, self.off_time):
            self.log(
                f"Time not meet. Motion: {on}",
            )
            return

        if on:
            is_light = self.is_light(self.lights)
            if not self.is_dark(is_light):
                self.log(f"Too much lux. Action: {on}")
                return

            self.log("Action detected ON.")
            self.cancel()
            self.do_light_on(self.service_data)
        elif not on:
            self.log("Action detected OFF.")
            self.cancel()
            sensor_on = False
            for sensor in self.sensors:
                if self.get_state(sensor) == "on":
                    sensor_on = True
            if not sensor_on:
                self.log("Countdown for lighting OFF")
                self.handle = self.run_in(self.do_light_off, self.delay)

    def light_off_cancel_timer_handler(self, entity, attribute, old, new, kwargs):  # pylint: disable=unused-argument
        """Handle light to turn off."""

        user_id = self.get_state(entity, attribute="context")["user_id"]
        if user_id != global_module.SUPERVISOR:
            self.log(
                f"User: '{user_id}' change device from UI"
                f"to '{new}' from '{old}'",
                level="INFO"
            )
            if new == "on":
                self.handle_user = True

        if attribute != "state":
            return

        if new == "off":
            self.handle_user = False
            light_on = False
            for light in self.lights:
                if self.get_state(light) == "on":
                    light_on = True
            if not light_on:
                self.cancel()

    def light_override_handler(self, entity, attribute, old, new, kwargs):  # pylint: disable=unused-argument
        """Light override handler."""

        self.log(f"Turned {entity} {new}")
        if new == "on" and self.light_override_force_off:
            self.light_off(None)

    def ambient_handler(self, entity, attribute, old, new, kwargs):  # pylint: disable=unused-argument
        """Check lux chagnes."""

        if not self.ambient_lux_control:
            return

        # self.log(f"ambient_handler {new} => {self.ambient_lux} {self.ambient_lux_off}")

        if self.check_time(self.on_time, self.off_time):
            if self.is_motion(self.sensors):
                is_light = self.is_light(self.lights)
                is_dark = self.is_dark(is_light)
                if is_dark and not is_light:
                    # if dark and not lighting
                    self.log("Ambient sensor: To dark")
                    self.do_action(True)
                elif not is_dark and is_light:
                    # if not dark and lighting
                    self.log("Ambient sensor: Too much lux")
                    self.do_action(False)

    # mode = True if lighting is on now otherwise False
    def is_dark(self, mode=None):
        """Check lux."""

        if self.ambient_sensor is not None:
            value = int(self.get_state(self.ambient_sensor))
            if value > self.ambient_lux:
                # Too much LUX
                if mode:
                    # Is lighting now
                    if value > self.ambient_lux_off:
                        return False

                    return True

                # if not is lighting now
                return False

        return True

    def do_light_on(self, data):
        """Ask to light on."""

        overrides = self.check_light_overrides(self.light_overrides)
        if overrides:
            return

        check = self.constraint_check(self.conditions)
        if check:
            self.light_on(data)

    def do_light_off(self, kwargs):
        """Ask to light off."""

        overrides = self.check_light_overrides(self.light_overrides)
        if overrides:
            return

        check = self.constraint_check(self.conditions)
        if check:
            if self.is_light(self.lights):
                if self.transition_delay > 0:
                    self.log("Lighting DIM")
                    self.light_dim(self.transition_dim)
                    if self.turn_off_mode:
                        dim_in_sec = int(self.delay) - \
                            int(self.transition_delay)
                        self.log("Countdown for final lighting OFF")
                        self.handle = self.run_in(self.light_off, dim_in_sec)
                else:
                    if self.turn_off_mode:
                        self.light_off(kwargs)

    def light_dim(self, dim):
        """Action light dim."""

        for on_entity in self.lights:
            device, _ = self.split_entity(on_entity)
            if device == "light":
                if self.get_state(on_entity) == "on":
                    self.turn_on(on_entity, brightness=dim)

    def light_on(self, data):
        """Action light on."""

        for on_entity in self.lights:
            device, _ = self.split_entity(on_entity)
            if device == "scene":
                self.log(f"I activated {on_entity}")
                self.turn_on(on_entity)
            else:
                self.log(f"Turned {on_entity} on")
                if device == "switch":
                    self.turn_on(on_entity)
                else:
                    self.turn_on(on_entity, **data)

    def light_off(self, kwargs):  # pylint: disable=unused-argument
        """Action light off."""

        for on_entity in self.lights:
            device, _ = self.split_entity(on_entity)
            if device != "scene":
                if self.get_state(on_entity) == "on":
                    self.log(f"Turned {on_entity} off")
                    self.turn_off(on_entity)

    def check_light_overrides(self, override_list: list):
        """Check light for overriding."""

        value = False
        if len(override_list) > 0:
            condition_states = ["on", "Home", "home", "True", "true"]
            for entity in override_list:
                if len(entity.split(",")) > 1:
                    if entity.split(",")[1].strip() != self.get_state(
                        entity.split(",")[0].strip()
                    ):
                        value = True
                elif self.get_state(entity) not in condition_states:
                    value = True
        else:
            value = True
        return not value

    def constraint_check(self, conditionlist: list) -> bool:
        """Check conditions and constraints."""

        for conditions in conditionlist:
            if not eval(conditions):  # pylint: disable=eval-used
                return False
        return True

    def is_light(self, lights: list):
        """Get light state."""
        light_on = False
        for light in lights:
            device, _ = self.split_entity(light)
            if device != "scene":
                if self.get_state(light) == "on":
                    light_on = True
        return light_on

    def is_motion(self, motions: list, time_out_mode=False):
        """Get motion state."""
        motion_on = False
        for motion in motions:
            states = self.get_state(motion, attribute="all")
            state = states["state"]
            if state == "on":
                motion_on = True
            if time_out_mode:
                if state == "off":
                    last_changed = states["last_changed"]
                    time_off = (
                        datetime.datetime.now().timestamp()
                        - self.convert_utc(last_changed).timestamp()
                    )
                    if time_off < float(self.delay + 10):
                        motion_on = True
        return motion_on

    def check_time(self, on_time, off_time):
        """Check is time for action."""
        return (
            False
            if (on_time is None and off_time is None)
            else (on_time == off_time == "00:00:00")
            or self.now_is_between(on_time, off_time)
        )

    def check_timeout_lights(self):
        """Check lost lights."""

        for on_entity in self.lights:
            device, _ = self.split_entity(on_entity)
            if device == "light":
                states = self.get_state(on_entity, attribute="all")
                state = states["state"]
                last_changed = states["last_changed"]
                if state == "on":
                    # lets check lighting
                    time_off = (
                        datetime.datetime.now().timestamp()
                        - self.convert_utc(last_changed).timestamp()
                    )
                    if time_off > float(self.delay + 10):
                        self.log("WatchDog: lighting time out.")
                        self.light_off(None)

    def is_idle(self):
        """Device in idle."""
        if not self.handle or not self.timer_running(self.handle):
            if not self.is_motion(self.sensors, True):
                return True
        return False

    def watch_dog_handler(self, kwargs: dict[str, Any]):  # pylint: disable=unused-argument
        """Watch dog handler."""

        profiles = self.args.get("profiles", [])

        found = False
        for idx, profile in enumerate(profiles):
            profile_name = profile.get("name", f"{DEFAULT_NAME}_{idx}")
            if self.check_time(
                str(profile.get("start_time", "00:00:00")),
                str(profile.get("end_time", "00:00:00")),
            ):
                found = True
                if self.profile_name != profile_name:
                    self.log(f"Set active profile: {profile_name}")
                    # run init profile
                    self.start_profile(profile)
                    break

        if not found:
            # No active profile - cleanup
            if self.profile_name is not None:
                self.clear_profile()

                # turn all off
                self.cancel()
                self.light_off(None)

        if self.profile_name is not None:
            # check device without motions
            if self.time_control:
                self.check_timeout_lights()

            # constraint is active
            if not self.constraint_check(self.conditions):
                if self.is_idle():
                    if self.is_light(self.lights):
                        self.log("WatchDog: Constraints is active.")
                        self.light_off(None)

            if self.check_light_overrides(self.light_overrides):
                return

            # lost lights
            if self.turn_off_mode:
                if self.is_idle():
                    if self.is_light(self.lights):
                        if 1 == 1:  # self.handle_user
                            self.log("WatchDog: Lost light.")
                            self.light_off(None)

            # inactive time
            if not self.check_time(self.on_time, self.off_time):
                if self.is_idle():
                    if self.is_light(self.lights):
                        self.log("WatchDog: Not time for light.")
                        self.light_off(None)

    def on_profile_changed(self):
        """Event on change profile."""
        if self.turn_off_mode:
            if self.is_idle():
                if self.is_light(self.lights):
                    self.light_off(None)
        else:
            if self.is_idle():
                if self.is_light(self.lights):
                    self.light_on(self.service_data)

    def start_profile(self, profile):
        """Action change profile."""

        profile_name = profile["name"]
        profile_delay = int(profile.get("delay", 60))
        profile_ambient_lux = int(profile.get(
            "lux", self.default_ambient_lux))
        profile_ambient_lux_off = int(profile.get(
            "lux_control_off", self.default_ambient_lux_off))
        profile_ambient_lux_control = profile.get("lux_control",
                                                  self.default_ambient_lux_control)
        profile_turn_off_mode = profile.get("turn_off_mode", True)
        profile_service_data = profile.get("light_data", {})
        transition = profile.get("transition", {})
        profile_transition_delay = int(transition.get("delay", 0))
        profile_transition_dim = int(transition.get("dim", 10))

        current_profile = dict(
            profile_name=profile_name,
            on_time=str(profile.get("start_time", "00:00:00")),
            off_time=str(profile.get("end_time", "00:00:00")),
            turn_off_mode=profile_turn_off_mode,
            delay=profile_delay,
            service_data=profile_service_data,
            ambient_lux=profile_ambient_lux,
            ambient_lux_off=profile_ambient_lux_off,
            ambient_lux_control=profile_ambient_lux_control,
            transition_delay=profile_transition_delay,
            transition_dim=profile_transition_dim,
        )
        self._profile = current_profile
        self.log(f"start_profile {self.profile_name}: {current_profile}")
        self.on_profile_changed()

    def clear_profile(self):
        """Clear the currnt profile."""

        self._profile["profile_name"] = None
        self._profile["on_time"] = None
        self._profile["off_time"] = None

    def cancel(self):
        """Cancel timer with checks."""

        if self.handle:
            if self.timer_running(self.handle):
                self.cancel_timer(self.handle)
            self.handle = None
