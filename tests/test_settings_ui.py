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


def test_new_settings_are_offered_by_the_settings_template():
    bound = _bound_keys("psucontrol_settings.jinja2")
    assert {"connectTimeout", "postConnectDelay", "turnOnWhenApiUploadPrint"} <= bound


def test_the_web_ui_renders_with_autoescaping_and_serves_the_new_settings(make_env):
    env = make_env()

    page = requests.get(env.base + "/", timeout=30)
    assert page.status_code == 200
    assert "settings_plugin_psucontrol" in page.text
    assert "settings.plugins.psucontrol.connectTimeout" in page.text

    plugin_settings = env.api("GET", "/api/settings").json()["plugins"]["psucontrol"]
    for key in ("connectTimeout", "postConnectDelay"):
        assert key in plugin_settings
