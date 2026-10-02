"""Auto-On: a trigger G-code (G1, M104, ...) while the PSU is sensed off switches it on.

The power-on runs inside OctoPrint's G-code queuing hook, so the triggering command is held
until the PSU is on. That is right when the PSU really was off; when the sensed state is wrong
(the PSU is on but sensing still says off), repeating it on every trigger G-code stalls the
print for postOnDelay per line. Auto-On must try once, then stop the print safely.
"""

import pytest

from conftest import gcode


def start_job(env, name, data):
    assert env.upload(name, data, print_=False).status_code == 201
    r = env.api("POST", "/api/files/local/" + name, json={"command": "select", "print": True})
    assert r.status_code == 204, r.text


@pytest.mark.parametrize("timing", [
    dict(postOnDelay=1, sensePollingInterval=1),
    # The plugin's defaults: no post-on delay, so the sensed state is still stale when Auto-On checks it.
    dict(postOnDelay=0, sensePollingInterval=5),
])
def test_power_off_print_is_switched_on_once_and_keeps_printing(make_env, timing):
    """The case Auto-On exists for: printer reachable, PSU off, a print starts."""
    env = make_env(autoOn=True, turnOnWhenApiUploadPrint=False, connectOnPowerOn=False, **timing)
    env.connect_printer()  # the virtual printer answers without "power"
    assert env.wait_for(lambda: env.printer_state() == "Operational", timeout=45)
    assert not env.psu_on

    start_job(env, "cold.gcode", gcode(40))

    assert env.wait_for(lambda: "Print job done" in env.log_text(), timeout=60), env.diagnostics()
    assert env.psu_on
    assert env.log_text().count("Auto-On - Turning PSU On") == 1
    assert "Pausing" not in env.log_text()


def test_sensing_stuck_off_pauses_instead_of_retrying_every_line(make_env):
    """The PSU switches on but sensing never agrees (e.g. a stale Home Assistant switch)."""
    env = make_env(autoOn=True, turnOnWhenApiUploadPrint=False, connectOnPowerOn=False,
                   senseSystemCommand="false")
    env.connect_printer()
    assert env.wait_for(lambda: env.printer_state() == "Operational", timeout=45)

    start_job(env, "stuck.gcode", gcode(40))

    assert env.wait_for(lambda: env.printer_state() == "Paused", timeout=60), env.diagnostics()
    assert "PSU still reported off" in env.log_text()
    env.wait_for(lambda: False, timeout=5)
    assert env.log_text().count("Auto-On - Turning PSU On") == 1, env.diagnostics()

    # Resuming continues the print without another Auto-On attempt.
    r = env.api("POST", "/api/job", json={"command": "pause", "action": "resume"})
    assert r.status_code == 204, r.text
    assert env.wait_for(lambda: "Print job done" in env.log_text(), timeout=60), env.diagnostics()
    assert env.log_text().count("Auto-On - Turning PSU On") == 1
