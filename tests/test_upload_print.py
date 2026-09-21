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


def test_settle_delay_is_honoured(make_env):
    """The printer reports Operational before it has finished booting; wait before printing."""
    env = make_env(postConnectDelay=4)
    assert env.upload("settle.gcode", gcode(60)).status_code == 201
    assert env.wait_for(lambda: env.started_count("settle.gcode") == 1, timeout=60), env.diagnostics()

    operational = env.first_time('to "Operational"')
    started = env.first_time("Print job started - origin: local, path: settle.gcode")
    assert (started - operational).total_seconds() >= 3.8


def test_pending_print_is_abandoned_when_the_printer_never_comes_up(make_env):
    """If the wait times out the request is dropped, and must not fire when the printer connects later."""
    env = make_env(connect_delay=12, connectTimeout=3)
    assert env.upload("late.gcode", gcode(60)).status_code == 201

    assert env.wait_for(lambda: "Not starting late.gcode" in env.log_text(), timeout=30), env.diagnostics()
    assert env.wait_for(lambda: env.printer_state() == "Operational", timeout=40), env.diagnostics()
    env.wait_for(lambda: False, timeout=6)
    assert env.started_count("late.gcode") == 0


def test_turning_the_psu_off_cancels_a_pending_print(make_env):
    env = make_env(connect_delay=8, connectTimeout=30)
    assert env.upload("cancelled.gcode", gcode(60)).status_code == 201
    assert env.wait_for(lambda: env.psu_on, timeout=20)

    env.psu("turnPSUOff")
    assert env.wait_for(lambda: "Cancelled pending print of cancelled.gcode" in env.log_text(), timeout=15), env.diagnostics()
    env.wait_for(lambda: False, timeout=14)
    assert env.started_count("cancelled.gcode") == 0


def test_a_print_queued_behind_a_busy_printer_never_starts_later(make_env):
    """Upload-and-print while another job runs is refused by OctoPrint; we must not resurrect it."""
    env = make_env()
    env.psu("turnPSUOn")
    assert env.wait_for(lambda: env.printer_state() == "Operational", timeout=45)

    assert env.upload("first.gcode", gcode(20000)).status_code == 201
    assert env.wait_for(lambda: env.printer_state() == "Printing", timeout=30), env.diagnostics()

    assert env.upload("second.gcode", gcode(60)).status_code == 201
    env.wait_for(lambda: False, timeout=3)

    r = env.api("POST", "/api/job", json={"command": "cancel"})
    assert r.status_code == 204, r.text
    assert env.wait_for(lambda: env.printer_state() == "Operational", timeout=30), env.diagnostics()

    # The moment the printer is free again is when anything queued behind it would fire.
    env.wait_for(lambda: False, timeout=6)
    assert env.started_count("second.gcode") == 0

    # ...and so would an unrelated power cycle.
    env.psu("turnPSUOff")
    assert env.wait_for(lambda: not env.psu_on, timeout=15)
    env.psu("turnPSUOn")
    assert env.wait_for(lambda: env.printer_state() == "Operational", timeout=45)
    env.wait_for(lambda: False, timeout=8)

    assert env.started_count("second.gcode") == 0

