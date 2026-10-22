# urllib3 (imported by dbt) checks IPv6 support at import time by binding a
# socket to ::1; nothing leaves the machine. Importing it here, before
# pytest-socket blocks sockets for each test, keeps that local probe out of the
# blocked-socket warnings, so any warning that remains is a real network attempt.
import urllib3  # noqa: F401
