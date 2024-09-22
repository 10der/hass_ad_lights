"""Global variables."""

import appdaemon.plugins.hass.hassapi as hass


NOTIFY = "ios"
SUPERVISOR = "a855815cb80b4592beb9bdb1a28597c6"

#
# Global App
#
# Args:
#


class Globals(hass.Hass):
    """Global class"""

    def initialize(self):
        """Initialize."""
        self.log("Global module initialized...")

    def restore_entity_value(self, entity, default_value):
        """Restore value on the re-start."""
        if not self.entity_exists(entity):
            data = self.get_history(entity_id=entity)
            if (len(data) > 0) and (len(data[0]) > 0):
                state = data[0][-1]['state']
            else:
                state = default_value
            self.set_state(entity, state=state)
