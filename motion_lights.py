"""AD: Motion lights."""

# pylint: disable=import-error
# pylint: disable=W0201
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
from enum import Enum
from typing import Any
import datetime
import global_module
import hassapi as hass  # type: ignore


class Profile:
    """Current profile"""

    _name = "default"
    _start_time = "00:00:00"
    _end_time = "00:00:00"
    _delay = 60
    _active = False
    _lux = 5
    _transition_delay = 0
    _turn_off_mode = True
    _light_data = {"brightness": 254}
    _transition_data = {"brightness": 2}

    def __init__(self, obj):
        """Init"""

        if obj is not None:
            self._name = obj.get("name") or "default"
            self._start_time = obj.get("start_time") or "00:00:00"
            self._end_time = obj.get("end_time") or "00:00:00"
            self._turn_off_mode = (
                True if obj.get("turn_off_mode") is None else obj.get(
                    "turn_off_mode")
            )

            self._lux = obj.get("lux", 5)
            self._delay = obj.get("delay", 60)
            self._light_data = obj.get("light_data") or {"brightness": 254}

            if obj.get("transition"):
                self._transition_delay = obj["transition"].get("delay") or 0
                self._transition_data = obj["transition"].get("light_data") or {
                    "brightness": 2
                }

    @property
    def active(self) -> str:
        """Profile name"""
        return self._active

    @active.setter
    def active(self, value: bool):
        """Set active / inactive."""
        self._active = value

    @property
    def name(self) -> str:
        """Profile name"""
        return self._name

    @property
    def lux(self) -> int:
        """Min lux"""
        return self._lux

    @property
    def start_time(self) -> str:
        """Start time"""
        return self._start_time

    @property
    def end_time(self) -> str:
        """End time"""
        return self._end_time

    @property
    def delay(self) -> int:
        """Light delay"""
        return self._delay

    @property
    def transition_delay(self) -> int:
        """Light transition delay"""
        return self._transition_delay

    @property
    def turn_off_mode(self) -> bool:
        """Light turn off mode"""
        return self._turn_off_mode

    @property
    def light_data(self) -> object:
        """Light data"""
        return self._light_data

    @property
    def transition_data(self) -> object:
        """Transition data"""
        return self._transition_data


class Action(Enum):
    """Action"""

    INIT = 0
    MOTION = 1
    ILLUMINANCE = 2
    OVERRIDE = 3
    LIGHTING = 4
    TIMEOUT = 255


class State(Enum):
    """State"""

    IDLE = 0
    DETECTED = 1
    COUNTDOWN = 2

    def __str__(self):
        return str(self.value)

    @staticmethod
    def from_str(text):
        """Convert str to enum"""
        statuses = [status for status in dir(
            State) if not status.startswith("_")]
        if text in statuses:
            return getattr(State, text)
        return None


DEFAULT_WATCHDOG_TIMEOUT = 60 * 5


class MotionLights(hass.Hass):
    """Motion lights class."""

    def initialize(self):
        """AD initialize."""

        self.depends_on_module([global_module])

        # { "app_class": "MotionLights" }
        self.listen_event(
            self._handle_log_debug, event='APPDAEMON_SET_DEBUG'
        )

        # internal sensor for states
        self.state_name = f"sensor.{self.name.lower().replace(' ', '_')}"

        self.handle = None
        self.profile = Profile(None)
        self.default_lux = self.args.get("lux", 65535)

        self.time_control = self.args.get("time_control", False)

        self.sensors = self.init_list_values(
            "sensors", self.update_all, action=Action.MOTION
        )
        self.ambient_light_sensors = self.init_list_values(
            "ambient_light_sensors", self.update_all, action=Action.ILLUMINANCE
        )
        self.override_list = self.init_list_values(
            "overrides", self.update_all, action=Action.OVERRIDE
        )
        self.on_entities = self.init_list_values(
            "lights", self.update_all, action=Action.LIGHTING
        )

        self.conditions = self.args.get("conditions", ["True"])

        self.current_state = State.IDLE
        self.update_all(None, None, None, None, {"action": Action.INIT})

        self.run_every(self.on_idle, "now", 1 * 60)

        self.log("Application started...", level="INFO")

    def _handle_log_debug(self, event_name, data, _):
        """Handle debug log."""

        if data.get('app_class', 'unknown') == self.__class__.__name__:
            self.set_log_level("DEBUG")
            self.log("Debug log enabled", level="INFO")

    # properties
    @property
    def current_state(self):
        """current state"""
        return State.from_str(self.get_state(self.state_name))

    @current_state.setter
    def current_state(self, value):
        self.set_state(self.state_name, state=value.name)

    @property
    def restriction(self):
        """restriction propery"""
        return self.get_state(self.state_name, attribute="restriction", default=False)

    @restriction.setter
    def restriction(self, value):
        self.set_state(self.state_name, attributes={"restriction": value})

    @property
    def motion(self):
        """motion propery"""
        return self.get_state(self.state_name, attribute="motion", default=False)

    @motion.setter
    def motion(self, value):
        self.set_state(self.state_name, attributes={"motion": value})

    @property
    def lighting(self):
        """motion propery"""
        return self.get_state(self.state_name, attribute="lighting", default=False)

    @lighting.setter
    def lighting(self, value):
        self.set_state(self.state_name, attributes={"lighting": value})

    @property
    def override(self):
        """override propery"""
        return self.get_state(self.state_name, attribute="override", default=False)

    @override.setter
    def override(self, value):
        self.set_state(self.state_name, attributes={"override": value})

    @property
    def illuminance(self):
        """illuminance property"""
        return self.get_state(self.state_name, attribute="illuminance", default=0)

    @illuminance.setter
    def illuminance(self, value):
        self.set_state(self.state_name, attributes={"illuminance": value})

    def update_illuminance(self):
        """update lluminance"""
        collected = []

        for entity in self.ambient_light_sensors:
            state = self.get_state(entity)
            if state is not None:
                if isinstance(state, (int, float)):
                    collected.append(float(state))

        self.illuminance = min(collected, default=0)

    def update_motion(self):
        """update motion"""
        motion = False
        for entity in self.sensors:
            if self.get_state(entity) == "on":
                motion = True

        self.motion = motion

    def update_lighting(self):
        """update update_lighting"""
        lighting = False
        for entity in self.on_entities:
            if self.get_state(entity) == "on":
                lighting = True

        self.lighting = lighting

    def update_overrides(self):
        """update overrides"""
        on = False
        for entity in self.override_list:
            if self.get_state(entity) == "on":
                on = True

        self.override = on

    def update_all(self, entity, attribute, old, new, kwargs):
        """update all states"""

        # if old in ['unknown', 'unavailable']:
        #    return

        self.update_illuminance()
        self.update_motion()
        self.update_overrides()
        self.update_lighting()

        data = {"handle_user": False}
        if kwargs["action"] == Action.LIGHTING:
            data["handle_user"] = self.is_light_handle_by_user(
                entity, attribute, old, new, kwargs
            )

        self.update(kwargs["action"], new, data)

    def update(self, action: str, value=None, kwargs: dict[str, Any] = None):
        """on update action"""
        new_state = self.current_state

        if action == Action.INIT:
            self.log("INIT", level="INFO")
        elif action == Action.MOTION:
            self.log(f"MOTION({self.motion})", level="INFO")
        elif action == Action.LIGHTING:
            self.log(f"LIGHTING({self.lighting})", level="INFO")
        elif action == Action.ILLUMINANCE:
            self.log(f"ILLUMINANCE({self.illuminance})", level="DEBUG")
        elif action == Action.OVERRIDE:
            self.log(f"OVERRIDE({self.override})", level="INFO")
        elif action == Action.TIMEOUT:
            self.log("TIMEOUT", level="INFO")
        else:
            self.log(f"UNKNOWN({value})", level="INFO")

        self.restriction = self.check_restriction()

        if action == Action.INIT:
            new_state = State.IDLE

        elif action == Action.OVERRIDE:
            self.on_override()

        elif action == Action.LIGHTING:
            handle_user = kwargs.get("handle_user") if kwargs else False
            if self.lighting and handle_user:
                self.log(f"MANUALLY {action} -> {self.lighting}")

            if not self.lighting:
                new_state = State.IDLE

        elif action == Action.ILLUMINANCE:
            if not self.restriction:
                if self.motion:
                    if not self.lighting:
                        self.motion_action(True)

        elif action == Action.TIMEOUT:
            new_state = State.IDLE

        elif action == Action.MOTION:
            if self.motion:
                if self.restriction:
                    self.log("LIGHT RESTRICTION", level="INFO")
                    new_state = State.IDLE
                else:
                    new_state = State.DETECTED
                    self.motion_action(True)
            else:
                new_state = State.COUNTDOWN
                self.motion_action(False)

        if self.current_state != new_state:
            self.log(f"{self.current_state.name} -> {new_state.name}")
            self.current_state = new_state

    def set_profile(self, profiles):
        """Set active profile"""
        profile_changed = False
        if profiles is None:
            self.profile = Profile(None)
            self.profile.activate = True
        else:
            found = False
            for idx, profile in enumerate(profiles):
                profile_name = profile.get("name", f"default_{idx}")
                if self.check_time(
                    str(profile.get("start_time", "00:00:00")),
                    str(profile.get("end_time", "00:00:00")),
                ):
                    found = True
                    if self.profile.name != profile_name:
                        if profile.get("lux") is None:
                            profile["lux"] = self.default_lux
                        self.profile = Profile(profile)
                        self.profile.active = True
                        self.log(
                            f"Set active profile: {profile_name}", level="INFO")
                        profile_changed = True
                        break

            if not found:
                if self.profile.active:
                    self.profile.active = False
                    self.log(
                        f"Profile {self.profile.name} deactivated.", level="INFO")
                    profile_changed = True

        return profile_changed

    def on_override(self):
        """On override"""
        if not self.profile.active:
            return

        if self.override:
            if self.lighting:
                self.log("WatchDog: Lights overridden.")
                self.light_off(dict(mandatory=True))
        else:
            if not self.restriction:
                if self.motion:
                    if not self.lighting:
                        self.motion_action(True)

    def motion_action(self, motion_detected):
        """Do on motion action is ON/OFF"""
        if motion_detected:
            # do lighting....
            if not self.time_control:
                self.cancel()
                self.run_in(self.light_on, 0)
        else:
            # start downcount timer for lighting off
            if self.lighting:
                delay = self.profile.delay
                method = self.light_off
                if self.profile.transition_delay > 0:
                    delay = delay - self.profile.transition_delay
                    method = self.light_dim
                self.cancel()
                self.handle = self.run_in(method, delay)
            else:
                self.update(Action.TIMEOUT)

    def check_restriction(self):
        """check restrictions"""

        # is profile active?
        if not self.profile.active:
            return "PROFILE_INACTIVE"

        # check constraint
        check = self.constraint_check(self.conditions)
        if not check:
            self.log("Constraints is active", level="DEBUG")
            return "CONSTRAINT"

        # is it time to light?
        if not self.check_time(self.profile.start_time, self.profile.end_time):
            self.log(
                f"Time not meet - [{self.profile.start_time}..{self.profile.end_time}]",
                level="DEBUG")
            return "TIME"

        # light override?
        if self.override:
            self.log("Lights overridden.", level="DEBUG")
            return "OVERRIDE"

        # lux control
        if self.illuminance > self.profile.lux:
            self.log(
                f"lux: {self.illuminance}/{self.profile.lux}", level="DEBUG")
            return "LUX"

        return False

    def light_on(self, kwargs):
        """Do light on"""
        for on_entity in self.on_entities:
            self.log(
                f"Turned {on_entity} on by profile {self.profile.name}", level="INFO")
            device, _ = self.split_entity(on_entity)
            if device == "switch":
                self.turn_on(on_entity)
            else:
                self.turn_on(on_entity)
                self.sleep(1)
                data = self.profile.light_data
                self.turn_on(on_entity, **data)

    def light_dim(self, kwargs):
        """Do Light dim"""
        for dim_entity in self.on_entities:
            self.log(
                f"Dim {dim_entity} by profile {self.profile.name}", level="INFO")
            device, _ = self.split_entity(dim_entity)
            if device == "switch":
                pass
            else:
                state = self.get_state(dim_entity)
                if state == "on":
                    data = self.profile.transition_data
                    self.turn_on(dim_entity, **data)

        self.handle = self.run_in(
            self.light_off, self.profile.transition_delay)

    def light_off(self, kwargs):
        """Do light off"""

        self.update(Action.TIMEOUT)

        mandatory = kwargs is not None and kwargs.get("mandatory", False)
        if not mandatory:
            if not self.profile.turn_off_mode:
                return

        for off_entity in self.on_entities:
            state = self.get_state(off_entity)
            if state == "on":
                self.log(f"Turned {off_entity} off", level="INFO")
                self.turn_off(off_entity)

    def on_idle(self, kwargs: dict[str, Any]):
        """On idle"""
        profile_changed = self.set_profile(
            self.args["profiles"] if "profiles" in self.args else None
        )
        if profile_changed:
            self.on_profile_changed()

        # update restriction property
        self.restriction = self.check_restriction()

        # if constraint => turn off
        check = self.constraint_check(self.conditions)
        if not check:
            if self.lighting:
                self.log("WatchDog: Constraints is active", level="INFO")
                self.light_off(dict(mandatory=True))

        # check lost devices...
        if self.is_idle():
            motion, time_out = self.is_motion_timeout(DEFAULT_WATCHDOG_TIMEOUT)
            if not motion and time_out:
                if self.lighting:
                    if self.profile.turn_off_mode:
                        if self.is_lights_timeout(
                            0 if self.time_control else DEFAULT_WATCHDOG_TIMEOUT
                        ):
                            self.log(
                                "WatchDog: Light off by timeout", level="INFO")
                            self.light_off(None)

    def on_profile_changed(self):
        """On profile changed"""
        if not self.profile.active:
            self.log("Profile deactivated: Turn off lights.", level="INFO")
            self.light_off(dict(mandatory=True))

        if self.motion:
            return

        if self.lighting:
            if self.profile.turn_off_mode:
                self.log("New profile: Turn off lights.", level="INFO")
                self.light_off(dict(mandatory=True))
            else:
                self.log("New profile: Fix dim lights.", level="INFO")
                self.light_dim(None)

    def check_time(self, on_time, off_time):
        """Check is time for action."""
        return (
            False
            if (on_time is None and off_time is None)
            else (on_time == off_time == "00:00:00")
            or self.now_is_between(on_time, off_time)
        )

    def constraint_check(self, conditionlist: list) -> bool:
        """Check conditions and constraints."""

        for conditions in conditionlist:
            if not eval(conditions):  # pylint: disable=eval-used
                return False
        return True

    def is_motion_timeout(self, watch_dog_timeout=0):
        """Get motion timeout state."""
        motion_on = False
        time_out = False
        last_changed = 0
        for motion in self.sensors:
            states = self.get_state(motion, attribute="all")
            if states is None:
                states["state"] = False
            state = states["state"]
            if state == "on":
                motion_on = True
            else:
                last_changed_value = self.convert_utc(
                    states["last_changed"]
                ).timestamp()

                if last_changed_value > last_changed:
                    last_changed = last_changed_value

        if not motion_on:
            time_off = datetime.datetime.now().timestamp() - last_changed
            if time_off > float(self.profile.delay + watch_dog_timeout):
                time_out = True

        return motion_on, time_out

    def is_lights_timeout(self, watch_dog_timeout=0):
        """Check timed out light devices."""
        action = False
        for on_entity in self.on_entities:
            states = self.get_state(on_entity, attribute="all")
            if states is None:
                states["state"] = "off"

            state = states["state"]
            if state == "on":
                last_changed = states["last_changed"]
                # lets check lighting
                time_off = (
                    datetime.datetime.now().timestamp()
                    - self.convert_utc(last_changed).timestamp()
                )
                if time_off > float(self.profile.delay + watch_dog_timeout):
                    action = True

        return action

    def cancel(self):
        """Cancel timer with checks."""
        if self.handle:
            if self.timer_running(self.handle):
                self.cancel_timer(self.handle)
            self.handle = None

    def is_idle(self):
        """Device in idle."""
        return not self.handle or not self.timer_running(self.handle)

    def init_list_values(self, name, method, action=None):
        """ "Fill list values"""
        entities = self.args.get(name)
        if entities is None:
            self.log(
                f"No sensor(s) {name} specified, doing nothing", level="INFO")
            return []

        if isinstance(entities, str):
            entities = entities.split(",")

        for entity in entities:
            self.listen_state(method, entity, action=action)

        return entities

    def is_light_handle_by_user(self, entity, attribute, old, new, kwargs):  # pylint: disable=unused-argument
        """Handle light context."""

        # Action	    id	        parent_id	user_id
        # Physical	    Not Null	Null	        Null
        # Automation	    Not Null	Not Null	Null
        # UI	            Not Null	Null	        Not Null

        context = self.get_state(entity, attribute="context")
        if context is not None:
            user_id = context.get("user_id")
            context_id = context.get("id")
            parent_id = context.get("parent_id")
            self.log(
                f"Light action: to '{new}' from '{old}' "
                f"user_id: '{user_id}' "
                f"context_id '{context_id}' "
                f"parent_id '{parent_id}'",
                level="DEBUG"
            )

            if context_id is not None and parent_id is None and user_id is not None:
                if user_id != global_module.SUPERVISOR:
                    self.log(
                        f"User: '{user_id}' change device from UI "
                        f"to '{new}' from '{old}'",
                        level="INFO",
                    )
                    return True
            elif context_id is not None and parent_id is None and user_id is None:
                self.log(
                    f"User: manually physical change device to '{new}' from '{old}'",
                    level="INFO",
                )
                return True

        return False
