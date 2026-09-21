"""The settings dialog is knockout data-binding against server-side settings.

A binding to a key the backend does not define fails silently in the browser
(the checkbox just does nothing), so check the template against the defaults.
"""

import os
import re

import requests

import octoprint_psucontrol
from octoprint_psucontrol import PSUControl

TEMPLATES = os.path.join(os.path.dirname(octoprint_psucontrol.__file__), "templates")


def _bound_keys(template):
    with open(os.path.join(TEMPLATES, template), encoding="utf-8") as f:
        return set(re.findall(r"settings\.plugins\.psucontrol\.(\w+)", f.read()))


def test_every_binding_in_the_settings_template_exists_in_the_backend():
    defaults = set(PSUControl().get_settings_defaults())

    for template in ("psucontrol_settings.jinja2", "psucontrol_navbar.jinja2", "psucontrol_wizard.jinja2"):
        assert _bound_keys(template) - defaults == set(), template
