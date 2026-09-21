"""End-to-end test rig: a real OctoPrint + virtual printer + this plugin.

PSU "power" is a flag file, so the switching/sensing commands are plain
``touch`` / ``rm`` / ``test`` and no hardware or Home Assistant is involved.
The tests drive OctoPrint through its real HTTP API, exactly as a slicer does.

Run inside a virtualenv that has OctoPrint installed plus this plugin
(``pip install -e .``); the OctoPrint under test is whichever one that is.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
import warnings
from datetime import datetime

import pytest
import requests
import yaml

import octoprint

API_KEY = "psucontroltestkey0123456789abcdef"
PORT = "SLOWVIRTUAL"  # see support/slowvirtual.py
HERE = os.path.dirname(os.path.abspath(__file__))
OCTOPRINT_MAJOR = int(octoprint.__version__.split(".")[0])

# Bundled plugins that only add startup time or talk to the internet.
DISABLED_PLUGINS = [
    "announcements",
    "errortracking",
    "health_check",
    "pluginmanager",
    "softwareupdate",
    "tracking",
    "discovery",
]


def gcode(lines):
    body = ["G28", "G90"] + ["G1 X%d Y%d F6000" % (i % 100, i % 100) for i in range(lines)] + ["M84"]
    return ("\n".join(body) + "\n").encode()


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class OctoPrintEnv:
    def __init__(self, tmp_path, psu_settings, connect_delay=None):
        self.connect_delay = connect_delay
        self.basedir = tmp_path / "octoprint"
        self.basedir.mkdir()
        self.flag = tmp_path / "psu_on"
        self.port = _free_port()
        self.base = "http://127.0.0.1:%d" % self.port
        self.proc = None
        self._write_config(psu_settings)

    # -- setup ---------------------------------------------------------

    def _write_config(self, psu_settings):
        psu = {
            "switchingMethod": "SYSTEM",
            "onSysCommand": "touch %s" % self.flag,
            "offSysCommand": "rm -f %s" % self.flag,
            "sensingMethod": "SYSTEM",
            "senseSystemCommand": "test -f %s" % self.flag,
            "sensePollingInterval": 1,
            "postOnDelay": 1,
            "connectOnPowerOn": True,
            "disconnectOnPowerOff": True,
            "turnOnWhenApiUploadPrint": True,
        }
        psu.update(psu_settings)

        cfg = {
            "api": {"key": API_KEY},
            "server": {
                "host": "127.0.0.1",
                "port": self.port,
                "firstRun": False,
                "onlineCheck": {"enabled": False},
                "pluginBlacklist": {"enabled": False},
            },
            "feature": {"sdSupport": False},
            "webcam": {"webcamEnabled": False, "timelapseEnabled": False},
            "plugins": {
                "_disabled": DISABLED_PLUGINS,
                "virtual_printer": {"enabled": True},
                "psucontrol": psu,
            },
        }
        if OCTOPRINT_MAJOR >= 2:
            cfg["printerConnection"] = {
                "autoconnect": False,
                "preferred": {"connector": "serial", "parameters": {"port": PORT, "baudrate": 115200}},
            }
        else:
            cfg["serial"] = {"port": PORT, "baudrate": 115200, "autoconnect": False}

        with open(self.basedir / "config.yaml", "w") as f:
            yaml.safe_dump(cfg, f)

    def _spawn(self):
        plugins_dir = self.basedir / "plugins"
        plugins_dir.mkdir(exist_ok=True)
        shutil.copy(os.path.join(HERE, "support", "slowvirtual.py"), plugins_dir / "slowvirtual.py")

        env = dict(os.environ, PYTHONUNBUFFERED="1")
        if self.connect_delay is not None:
            env["SLOWVIRTUAL_CONNECT_DELAY"] = str(self.connect_delay)
        self.stdout = open(self.basedir / "stdout.log", "w")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "octoprint", "--basedir", str(self.basedir), "serve",
             "--host", "127.0.0.1", "--port", str(self.port)],
            stdout=self.stdout, stderr=subprocess.STDOUT, env=env,
            # `python -m` puts the cwd on sys.path. Run from a neutral directory so the plugin
            # under test is always the one installed in this virtualenv, never a stray checkout.
            cwd=str(self.basedir),
        )

    def _output_seen(self):
        try:
            stdout = (self.basedir / "stdout.log").read_text(errors="replace")
        except FileNotFoundError:
            stdout = ""
        return bool(stdout.strip() or self.log_text().strip())

    def start(self):
        self._spawn()
        if self.wait_for(self._plugin_answers, timeout=45):
            return

        # A start that produced no output at all never reached the plugin (seen rarely on
        # OctoPrint 2.0 release candidates). Retry that once, loudly; anything else is a real failure.
        if not self._output_seen():
            warnings.warn("OctoPrint printed nothing in 45s (state: %s); restarting it once" % self._proc_state())
            self.stop()
            self.port = _free_port()
            self.base = "http://127.0.0.1:%d" % self.port
            self._spawn()
            if self.wait_for(self._plugin_answers, timeout=90):
                return

        raise AssertionError("OctoPrint/plugin never came up (%s):\n%s" % (self._proc_state(), self.diagnostics()))

    def _proc_state(self):
        if self.proc is None:
            return "not started"
        code = self.proc.poll()
        return "still running" if code is None else "exited with code %s" % code

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if getattr(self, "stdout", None):
            self.stdout.close()

    # -- helpers -------------------------------------------------------

    def api(self, method, path, **kw):
        headers = kw.pop("headers", {})
        headers["X-Api-Key"] = API_KEY
        return requests.request(method, self.base + path, headers=headers, timeout=60, **kw)

    def _plugin_answers(self):
        try:
            return self.api("POST", "/api/plugin/psucontrol", json={"command": "getPSUState"}).status_code == 200
        except requests.RequestException:
            return False

    def wait_for(self, predicate, timeout=45, interval=0.4):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if predicate():
                    return True
            except requests.RequestException:
                pass
            time.sleep(interval)
        return False

    @property
    def psu_on(self):
        return self.flag.exists()

    def plugin_thinks_psu_on(self):
        return self.api("POST", "/api/plugin/psucontrol", json={"command": "getPSUState"}).json()["isPSUOn"]

    def printer_state(self):
        return self.api("GET", "/api/connection").json()["current"]["state"]

    def connect_printer(self):
        r = self.api("POST", "/api/connection", json={"command": "connect", "port": PORT, "baudrate": 115200})
        assert r.status_code == 204, r.text

    def psu(self, command):
        r = self.api("POST", "/api/plugin/psucontrol", json={"command": command})
        assert r.status_code in (200, 204), r.text
        return r

    def upload(self, name, data, print_=True):
        # PrusaSlicer's "Upload and Print": a multipart POST with print=true.
        return self.api(
            "POST", "/api/files/local",
            files={"file": (name, data)},
            data={"print": "true" if print_ else "false"},
        )

    def log_text(self):
        try:
            return (self.basedir / "logs" / "octoprint.log").read_text(errors="replace")
        except FileNotFoundError:
            return ""

    def first_time(self, needle):
        """Timestamp of the first octoprint.log line containing ``needle`` (or None)."""
        for line in self.log_text().splitlines():
            if needle in line:
                return datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S,%f")
        return None

    def started_count(self, name):
        return self.log_text().count("Print job started - origin: local, path: %s" % name)

    def diagnostics(self):
        tail = "\n".join(self.log_text().splitlines()[-60:])
        try:
            out = (self.basedir / "stdout.log").read_text(errors="replace")[-1500:]
        except FileNotFoundError:
            out = ""
        return "---- octoprint.log (tail) ----\n%s\n---- stdout ----\n%s" % (tail, out)


@pytest.fixture
def make_env(tmp_path, request):
    envs = []

    def factory(connect_delay=None, **psu_settings):
        env = OctoPrintEnv(tmp_path, psu_settings, connect_delay=connect_delay)
        envs.append(env)
        env.start()
        return env

    yield factory
    for env in envs:
        env.stop()

    # Set PSUCONTROL_TEST_LOGS=<dir> to keep each test's octoprint.log, even when it passes.
    keep = os.environ.get("PSUCONTROL_TEST_LOGS")
    if keep and envs:
        os.makedirs(keep, exist_ok=True)
        src = envs[-1].basedir / "logs" / "octoprint.log"
        if src.exists():
            shutil.copy(src, os.path.join(keep, request.node.name + ".log"))
