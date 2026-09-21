"""'Upload and Print' from a slicer against a printer that is powered off.

The plugin's ``turnOnWhenApiUploadPrint`` option promises: send a print job,
the printer powers on, connects, and the job starts. These tests hold it to that.
"""

from conftest import gcode

CLOSED_STATES = ("Closed", "Offline")


def test_cold_printer_upload_and_print_starts_the_print(make_env):
    env = make_env()
    assert not env.psu_on
    assert env.printer_state() in CLOSED_STATES

    r = env.upload("cold.gcode", gcode(60))
    assert r.status_code == 201, r.text

    assert env.wait_for(lambda: env.started_count("cold.gcode") == 1, timeout=60), (
        "print never started\n" + env.diagnostics()
    )
    assert env.psu_on


def test_psu_already_on_but_printer_disconnected(make_env):
    env = make_env()
    env.flag.touch()  # e.g. switched on from Home Assistant or the wall
    assert env.wait_for(env.plugin_thinks_psu_on)
    assert env.printer_state() in CLOSED_STATES

    r = env.upload("halfway.gcode", gcode(60))
    assert r.status_code == 201, r.text

    assert env.wait_for(lambda: env.started_count("halfway.gcode") == 1, timeout=60), (
        "print never started\n" + env.diagnostics()
    )


def test_already_connected_printer_is_unaffected(make_env):
    """Regression guard: the normal case must still print exactly once."""
    env = make_env()
    env.psu("turnPSUOn")
    assert env.wait_for(lambda: env.printer_state() == "Operational", timeout=45)

    r = env.upload("warm.gcode", gcode(60))
    assert r.status_code == 201, r.text

    assert env.wait_for(lambda: env.started_count("warm.gcode") >= 1, timeout=30), env.diagnostics()
    env.wait_for(lambda: False, timeout=6)  # give any duplicate start time to show up
    assert env.started_count("warm.gcode") == 1


def test_upload_without_print_flag_never_prints(make_env):
    env = make_env()
    r = env.upload("noprint.gcode", gcode(20), print_=False)
    assert r.status_code == 201, r.text
    env.wait_for(lambda: False, timeout=8)
    assert env.started_count("noprint.gcode") == 0
    assert not env.psu_on  # print=false must not power anything on
