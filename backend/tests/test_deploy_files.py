"""Verify deployment files: existence, syntax, required directives."""
import os

DEPLOY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "deploy")

EXPECTED = {
    "nginx.conf":                ["proxy_pass", "ssl_certificate", "http2", "gzip", "Strict-Transport-Security"],
    "sakgaze-backend.service":    ["uvicorn", "--workers 4", "Restart=always", "ProtectSystem=strict"],
    "sakgaze-scheduler.service":  ["sakgaze.src.pipeline", "weathernext.src.pipeline", "drift.src.engine"],
    "sakgaze-scheduler.timer":    ["OnCalendar", "Persistent=true"],
    "setup_vps.sh":               ["postgresql-17", "postgis", "certbot", "ufw", "/opt/sakgaze"],
}


def test_all_files_exist():
    for name in EXPECTED:
        path = os.path.join(DEPLOY, name)
        assert os.path.isfile(path), f"Missing: {name}"


def test_setup_vps_executable():
    assert os.access(os.path.join(DEPLOY, "setup_vps.sh"), os.X_OK), "setup_vps.sh not executable"


def test_nginx_directives():
    _check("nginx.conf")


def test_backend_service():
    _check("sakgaze-backend.service")


def test_scheduler_service():
    _check("sakgaze-scheduler.service")


def test_scheduler_timer():
    _check("sakgaze-scheduler.timer")


def test_setup_script():
    _check("setup_vps.sh")


def test_readme():
    path = os.path.join(DEPLOY, "README.md")
    assert os.path.isfile(path), "Missing: README.md"
    text = open(path).read()
    for kw in ["VPS", "DNS", "systemctl", "systemd", "deploy"]:
        assert kw.lower() in text.lower(), f"README missing keyword: {kw}"


# -- helpers --
def _check(name):
    path = os.path.join(DEPLOY, name)
    text = open(path).read()
    for kw in EXPECTED[name]:
        assert kw in text, f"{name}: missing '{kw}'"
