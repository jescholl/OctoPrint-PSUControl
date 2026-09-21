# coding=utf-8
"""Test-support plugin: a virtual printer that takes a while to answer.

OctoPrint's bundled virtual printer is Operational almost instantly, which hides
the race this test-suite exists for: with a real printer, opening the serial
port and getting through the handshake takes about a second, during which
``printer.is_operational()`` is still False.

The ``octoprint.comm.transport.serial.factory`` hook runs inside OctoPrint's
connect thread, so sleeping there reproduces that window faithfully. The actual
serial object is then supplied by the bundled virtual printer.
"""

import os
import time

import octoprint.plugin

PORT = "SLOWVIRTUAL"

__plugin_name__ = "Slow Virtual Printer (test support)"
__plugin_pythoncompat__ = ">=3.7,<4"


def _factory(comm_instance, port, baudrate, read_timeout, *args, **kwargs):
    if port != PORT:
        return None

    time.sleep(float(os.environ.get("SLOWVIRTUAL_CONNECT_DELAY", "1.5")))

    info = octoprint.plugin.plugin_manager().get_plugin_info("virtual_printer")
    return info.implementation.virtual_printer_factory(comm_instance, "VIRTUAL", baudrate, read_timeout)


def _port_names(*args, **kwargs):
    return [PORT]


__plugin_hooks__ = {
    "octoprint.comm.transport.serial.factory": _factory,
    "octoprint.comm.transport.serial.additional_port_names": _port_names,
}
