#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""App Hub self-check (doctor).

Verifies everything the launcher chain depends on, plus live runtime state.
The point is to catch startup breakage BEFORE double-clicking the launcher --
the 2026-11-04 incident (missing backend/_spawn.ps1 + a health check that
only warned) shipped a "Done" message while the hub was refusing connections.

Run:  python backend/doctor.py
Exit: 0 = no FAIL (warnings allowed), 1 = at least one FAIL

Output is deliberately plain ASCII so cmd renders it cleanly on any code page.
"""
import importlib.util
import os
import socket
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get("PORT", "8787"))

rows = []


def add(level, name, detail):
    rows.append((level, name, detail))


def mod_version(name):
    """Best-effort human version string; never triggers a deprecation warning."""
    try:
        from importlib.metadata import version as _v
        return _v(name)
    except Exception:
        return "installed"


def mod_probe(name):
    """Return (version_or_None, present_bool)."""
    try:
        spec = importlib.util.find_spec(name)
    except Exception:
        return None, False
    if spec is None:
        return None, False
    try:
        __import__(name)
        return mod_version(name), True
    except Exception as exc:
        return "import failed: %s" % exc, True


# --- interpreter chain -------------------------------------------------
exe = sys.executable or "?"
add("ok", "python", "%s  %s" % (sys.version.split()[0], exe))

pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
if os.path.isfile(pythonw):
    add("ok", "pythonw", pythonw)
else:
    add("fail", "pythonw", "missing - windowless backend launch will fail")

# --- backend dependencies ----------------------------------------------
flask_v, has_flask = mod_probe("flask")
if has_flask:
    add("ok", "flask", flask_v or "installed")
else:
    add("fail", "flask", "not installed - pip install Flask flask-cors")

cors_v, has_cors = mod_probe("flask_cors")
if has_cors:
    add("ok", "flask-cors", cors_v or "installed")
else:
    add("warn", "flask-cors", "not installed - cross-origin calls may fail")

ak_v, has_ak = mod_probe("akshare")
if has_ak:
    add("ok", "akshare", "%s - LIVE data mode" % (ak_v or "installed"))
else:
    add("warn", "akshare", "not installed - OFFLINE mode, bundled cached data")

# --- files the launcher needs -----------------------------------------
required = [
    (os.path.join("backend", "app.py"), "backend/app.py", True),
    (os.path.join("backend", "_spawn.ps1"), "backend/_spawn.ps1", True),
    (os.path.join("backend", "doctor.py"), "backend/doctor.py", False),
    ("verify_all.py", "verify_all.py", True),
    ("index.html", "index.html", True),
]
for rel, label, hard in required:
    if os.path.isfile(os.path.join(ROOT, rel)):
        add("ok", label, "present")
    else:
        add("fail" if hard else "warn", label, "MISSING - %s" % rel.replace("\\", "/"))

data_dir = os.path.join(ROOT, "backend", "data")
if os.path.isdir(data_dir):
    n = len([f for f in os.listdir(data_dir) if f.endswith(".json")])
    add("ok", "backend/data", "%d json files" % n)
else:
    add("warn", "backend/data", "directory missing - apps fall back to samples")

# --- runtime state -----------------------------------------------------
sock = socket.socket()
sock.settimeout(1.5)
try:
    sock.connect(("127.0.0.1", PORT))
    listening = True
except Exception:
    listening = False
finally:
    sock.close()

if listening:
    add("ok", "port %d" % PORT, "LISTENING")
else:
    add("warn", "port %d" % PORT, "not listening - run hub.bat start")

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:
    resp = opener.open("http://127.0.0.1:%d/api/health" % PORT, timeout=5)
    body = resp.read()
    add("ok", "api/health", "HTTP %s  %d bytes" % (resp.status, len(body)))
except Exception as exc:
    add("warn", "api/health", "unreachable - %s" % type(exc).__name__)

# --- report ------------------------------------------------------------
print("=" * 62)
print("  App Hub - Doctor")
print("=" * 62)
for level, name, detail in rows:
    print("  [%-4s] %-16s %s" % (level.lower(), name, detail))
n_fail = sum(1 for r in rows if r[0] == "fail")
n_warn = sum(1 for r in rows if r[0] == "warn")
n_ok = len(rows) - n_fail - n_warn
print("-" * 62)
print("  %d ok / %d warn / %d fail" % (n_ok, n_warn, n_fail))
if n_fail:
    print("  RESULT: FAIL - fix the items above before starting the hub.")
    sys.exit(1)
if n_warn:
    print("  RESULT: PASS with warnings - the hub can start.")
else:
    print("  RESULT: PASS - everything the launcher needs is in place.")
sys.exit(0)
