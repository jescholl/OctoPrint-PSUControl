"""OctoPrint 1.11 warns about plugins that leave API protection and template autoescaping to the defaults.

Both defaults are going to change (autoescaping is enforced from OctoPrint 1.13), so declare them.
"""

import requests


def test_api_rejects_anonymous_callers(make_env):
    env = make_env()

    assert requests.get(env.base + "/api/plugin/psucontrol", timeout=10).status_code in (401, 403)
    assert env.api("GET", "/api/plugin/psucontrol").status_code == 200


def test_octoprint_does_not_warn_about_this_plugin(make_env):
    env = make_env()

    env.api("GET", "/api/plugin/psucontrol")  # the API warning is logged on use
    assert requests.get(env.base + "/", timeout=30).status_code == 200

    warnings = [
        line for line in env.log_text().splitlines()
        if "octoprint.plugins.psucontrol" in line and ("is_api_protected" in line or "autoescaped" in line)
    ]
    assert warnings == []
