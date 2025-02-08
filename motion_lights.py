"""AD: Motion lights."""

# pylint: disable=import-error
# pylint: disable=W0201
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
from enum import Enum
from typing import Any
import datetime
from datetime import timedelta
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
                True if obj.get("turn_off_mode") is None else obj.get("turn_off_mode")
            )

            self._lux = obj.get("lux") or 5
            self._delay = obj.get("delay") or 60
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
    COWNTDOWN = 2
    RESTRICTED = 255

    def __str__(self):
        return str(self.value)

    @staticmethod
    def from_str(text):
        """Convert str to enum"""
        statuses = [status for status in dir(State) if not status.startswith("_")]
        if text in statuses:
            return getattr(State, text)
        return None


DEFAULT_WATCHDOG_TIMEOUT = 60 * 5


class MotionLights(hass.Hass):
    """Motion lights class."""

    def initialize(self):
        """AD initialize."""

        self.depends_on_module([global_module])

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

        self.on_idle(None)
        self.run_every(
            self.on_idle, datetime.datetime.now() + timedelta(minutes=1), 1 * 60
        )
        self.log("Application started...")

    # properties
    @property
    def current_state(self):
        """current state"""
        return State.from_str(self.get_state(self.state_name))

    @current_state.setter
    def current_state(self, value):
        self.set_state(self.state_name, state=value.name)

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
        self.update_illuminance()
        self.update_motion()
        self.update_overrides()
        self.update_lighting()

        handle_user = False
        if kwargs["action"] == Action.LIGHTING:
            handle_user = self.is_light_handle_by_user(
                entity, attribute, old, new, kwargs
            )

        self.update(kwargs["action"], handle_user)

    def update(self, action: str, handle_user: bool = False):
        """on update action"""
        new_state = self.current_state

        if action == Action.INIT:
            self.log(f"{action}")

        elif action == Action.OVERRIDE:
            self.log(f"{action}")
            self.on_override()

        elif action == Action.LIGHTING:
            if self.lighting and handle_user:
                self.log(f"MANUALLY {action} -> {self.lighting}")

            if not self.lighting:
                new_state = State.IDLE
                self.log(f"{action} -> {self.lighting}")

        elif action == Action.ILLUMINANCE:
            # self.log(f"{action} -> {self.illuminance}")
            if self.motion:
                if not self.lighting:
                    self.motion_action(True)

        elif action == Action.TIMEOUT:
            self.log(f"{action}")
            new_state = State.IDLE

        elif action == Action.MOTION:
            self.log(f"{action} -> {self.motion}")
            result = self.motion_action(self.motion)
            # if result is not False => restriction occurred!
            if result:
                new_state = State.IDLE  # State.RESTRICTED
            else:
                new_state = State.DETECTED if self.motion else State.COWNTDOWN

        if self.current_state != new_state:
            self.log(f"{self.current_state.name} -> {new_state.name}")
            self.current_state = new_state

    def set_profile(self, profiles):
        """Set active profile"""
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
                        self.log(f"Set active profile: {profile_name}")
                        break

            if not found:
                if self.profile.active:
                    self.profile.active = False
                    self.log(f"Profile {self.profile.name} deactivated.")

    def on_override(self):
        """On override"""
        if not self.profile.active:
            return

        if self.override:
            if self.lighting:
                self.log("WatchDog: Lights overridden.")
                self.light_off(dict(mandatory=True))
        else:
            self.motion_action(self.motion)

    def motion_action(self, motion_detected):
        """Do on motion action is ON/OFF"""

        # is profile active?
        if not self.profile.active:
            return "PROFILE_INACTIVE"

        # check constraint
        check = self.constraint_check(self.conditions)
        if not check:
            self.log("Constraints is active")
            return "CONSTRAINT"

        # is it time to light?
        if not self.check_time(self.profile.start_time, self.profile.end_time):
            self.log(
                f"Time not meet - [{self.profile.start_time}..{self.profile.end_time}]"
            )
            return "TIME"

        if motion_detected:
            # light override?
            if self.override:
                self.log("Lights overridden.")
                return "OVERRIDE"

            # lux control
            if self.illuminance > self.profile.lux:
                # only if not light right now
                if not self.lighting:
                    self.log(f"lux: {self.illuminance}/{self.profile.lux}")
                    return "LUX"
                else:
                    # if already light
                    delta = self.illuminance - self.profile.lux
                    self.log(f"lux light ON control delta: {delta}")

            # do lighting....
            if not self.time_control:
                self.cancel()
                self.run_in(self.light_on, 0)
        else:
            # start downcount timer for lighting off
            delay = self.profile.delay
            method = self.light_off
            if self.profile.transition_delay > 0:
                delay = delay - self.profile.transition_delay
                method = self.light_dim
            self.cancel()
            self.handle = self.run_in(method, delay)

    def light_on(self, kwargs):
        """Do light on"""
        for on_entity in self.on_entities:
            self.log(f"Turned {on_entity} on")
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
            self.log(f"Dim {dim_entity}")
            device, _ = self.split_entity(dim_entity)
            if device == "switch":
                pass
            else:
                data = self.profile.transition_data
                self.turn_on(dim_entity, **data)

        self.handle = self.run_in(self.light_off, self.profile.transition_delay)

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
                self.log(f"Turned {off_entity} off")
                self.turn_off(off_entity)

    def on_idle(self, kwargs: dict[str, Any]):
        """On idle"""
        self.set_profile(self.args["profiles"] if "profiles" in self.args else None)

        check = self.constraint_check(self.conditions)
        if not check:
            if self.lighting:
                self.log("WatchDog: Constraints is active")
                self.light_off(dict(mandatory=True))

        # check lost devices...
        if self.is_idle():
            motion, time_out = self.is_motion_timeout(DEFAULT_WATCHDOG_TIMEOUT)
            if not motion and time_out:
                if self.lighting:
                    if not self.profile.turn_off_mode:
                        if self.is_lights_timeout(
                            0 if self.time_control else DEFAULT_WATCHDOG_TIMEOUT
                        ):
                            self.log("WatchDog: Light off by timeout")
                            self.light_off(None)

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
                self.log(f"WatchDog: Unknown state for entity {motion}")
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
            self.log(f"No sensor(s) {name} specified, doing nothing")
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
            # self.log(
            #     f"Light action: to '{new}' from '{old}' "
            #     f"user_id: '{user_id}' "
            #     f"context_id '{context_id}' "
            #     f"parent_id '{parent_id}'",
            #     level="INFO"
            # )

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
