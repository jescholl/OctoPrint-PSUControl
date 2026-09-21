# OctoPrint PSU Control
This OctoPrint plugin controls an ATX/AUX power supply to help reduce power consumption and noise when the printer is not in use.

Power supply can be automatically switched on when user specified commands are sent to the printer and/or switched off when idle.

Supports Commands (G-Code or System) or GPIO to switch power supply on/off.

![PSUControl](psucontrol_navbar_settings.png?raw=true)

## About this fork
This is a maintained fork of [kantlivelong/OctoPrint-PSUControl](https://github.com/kantlivelong/OctoPrint-PSUControl), which has had no code changes since 2021. It is released under the same license (AGPL-3.0) and was modified from upstream version 1.0.6 in September 2026; the commit history has the details. The plugin identifier, settings and sub-plugin API are unchanged, so existing configuration and sub-plugins keep working.

What is different from 1.0.6:

- **"Upload and Print" starts the print when the printer is off.** With *Turn on, connect and start printing after an API upload* enabled, uploading a file with the print option (a slicer's "Upload and Print", for example) powers the printer on, connects, waits for it, and starts the job. Upstream only powered the printer on: OctoPrint decides whether to start a print at the moment the upload arrives, while the printer is still connecting, and silently drops the request. The upload now returns immediately instead of holding the slicer's connection open, and a request that cannot be honoured (the printer never came up, the PSU was switched off meanwhile, another print is running) is dropped rather than started later.
- **New settings:** *Connect Timeout*, and *Post Connect Delay* for printers that are not ready for a few seconds after they connect. Prusa printers, for example, restart when the serial port opens; a delay of 5-8 seconds is a reasonable start.
- **Ignore Heaters** for idle power-off, for printers that report a heater that cannot be switched off or never cools (the Prusa MK4 heatbreak sensor, `X`).
- **API and templates** are protected and auto-escaped, which OctoPrint 1.11 warns will become mandatory. OctoPrint 1.4 or newer is required.
- **Tests:** `tests/` runs a real OctoPrint with a virtual printer against the plugin. It is run against OctoPrint 1.11.8 and 2.0.0rc5.

Several of these changes were worked out by others in forks and pull requests that upstream never merged: oerkel47 (the upload, connect and print flow, and OctoPrint 2.0 preparation), Gifford47 (cancelling pending work when the PSU is switched off), and oxivanisher and tlachmann (ignoring heaters). Thank you.

Bugs and requests for this fork go to this repository's issues. The Support and Feature Requests links at the bottom belong to the original project.

To run the tests, in a virtualenv that has OctoPrint installed:

    pip install -e . pytest requests
    pytest tests
 
 
## Setup
Install the plugin using Plugin Manager from Settings
 
## Settings
See the [Wiki](https://github.com/kantlivelong/OctoPrint-PSUControl/wiki/Settings)
 
## Troubleshooting
See the [Wiki](https://github.com/kantlivelong/OctoPrint-PSUControl/wiki/Troubleshooting)

## API
See the [Wiki](https://github.com/kantlivelong/OctoPrint-PSUControl/wiki/API)

## Support
Help can be found at the [OctoPrint Community Forums](https://community.octoprint.org)

## Feature Requests
[![Feature Requests](https://feathub.com/kantlivelong/OctoPrint-PSUControl?format=svg)](https://feathub.com/kantlivelong/OctoPrint-PSUControl)
