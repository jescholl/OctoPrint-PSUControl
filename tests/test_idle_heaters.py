"""'Ignore Heaters' for idle power-off, with a stub printer (no OctoPrint server needed)."""

import logging
import threading

from octoprint_psucontrol import PSUControl


class StubPrinter:
    def __init__(self, temperatures):
        self._temperatures = temperatures
        self.set_calls = []

    def get_current_temperatures(self):
        return self._temperatures

    def set_temperature(self, heater, target):
        self.set_calls.append((heater, target))


def make_plugin(temperatures, ignore=""):
    plugin = PSUControl()
    plugin._logger = logging.getLogger("test")
    plugin._printer = StubPrinter(temperatures)
    plugin.config = dict(idleIgnoreHeaters=ignore, idleTimeoutWaitTemp=50)
    plugin._idleIgnoreHeatersArray = [h.strip() for h in ignore.split(",") if h.strip()]
    return plugin


def wait_for_heaters(plugin, timeout=3):
    """Run the wait, failing (rather than hanging the suite) if it never gives up on a hot heater."""
    result = {}
    thread = threading.Thread(target=lambda: result.update(value=plugin._wait_for_heaters()), daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        plugin._waitForHeaters = False  # let the loop end after its current sleep
        return "still waiting for a heater after %ss" % timeout
    return result["value"]


def test_ignored_heater_is_neither_switched_off_nor_waited_for():
    # e.g. a Prusa MK4 reports its heatbreak as "X", which cannot be set and reads hot.
    plugin = make_plugin({"tool0": {"actual": 22, "target": 0}, "X": {"actual": 90, "target": 60}}, ignore="X")

    assert wait_for_heaters(plugin) is True
    assert plugin._printer.set_calls == []


def test_without_the_setting_a_hot_target_is_switched_off():
    plugin = make_plugin({"tool0": {"actual": 22, "target": 200}})

    assert wait_for_heaters(plugin) is True
    assert plugin._printer.set_calls == [("tool0", 0)]


def test_ignoring_a_tool_heater_stops_it_blocking_power_off():
    plugin = make_plugin({"tool0": {"actual": 200, "target": 0}}, ignore="tool0")

    assert wait_for_heaters(plugin) is True  # would otherwise wait for it to cool down
