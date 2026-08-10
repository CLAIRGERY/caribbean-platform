"""Verify deployment files: existence, syntax, required directives."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DEPLOY = os.path.join(ROOT, "deploy")

EXPECTED = {
    "nginx.conf":                ["proxy_pass", "ssl_certificate", "http2", "gzip", "Strict-Transport-Security"],
    "sakgaze-backend.service":    ["uvicorn", "--workers 4", "Restart=always", "ProtectSystem=strict"],
    "sakgaze-scheduler.service":  ["sakgaze.src.pipeline", "weathernext.src.pipeline", "drift.src.engine"],
    "sakgaze-scheduler.timer":    ["OnCalendar", "Persistent=true"],
    "setup_vps.sh":               ["postgresql-17", "postgis", "certbot", "ufw", "/opt/sakgaze"],
}
ROOT_FILES = {
    "render.yaml": ["sakgaze-api", "uvicorn", "CORS_ORIGINS", "DATABASE_URL", "supabase.com"],
    "requirements.txt": ["fastapi", "uvicorn", "geopandas", "rasterio"],
}


def test_all_files_exist():
    for name in EXPECTED:
        path = os.path.join(DEPLOY, name)
        assert os.path.isfile(path), f"Missing deploy/{name}"
    for name in ROOT_FILES:
        path = os.path.join(ROOT, name)
        assert os.path.isfile(path), f"Missing {name}"


def test_setup_vps_executable():
    assert os.access(os.path.join(DEPLOY, "setup_vps.sh"), os.X_OK)


def test_nginx_directives():
    _check_deploy("nginx.conf")


def test_backend_service():
    _check_deploy("sakgaze-backend.service")


def test_scheduler_service():
    _check_deploy("sakgaze-scheduler.service")


def test_scheduler_timer():
    _check_deploy("sakgaze-scheduler.timer")


def test_setup_script():
    _check_deploy("setup_vps.sh")


def test_render_config():
    _check_root("render.yaml")


def test_requirements():
    _check_root("requirements.txt")


def test_readme():
    path = os.path.join(DEPLOY, "README.md")
    assert os.path.isfile(path), "Missing: README.md"
    text = open(path).read()
    for kw in ["VPS", "DNS", "systemctl", "systemd", "deploy"]:
        assert kw.lower() in text.lower(), f"README missing keyword: {kw}"


def _check_deploy(name):
    path = os.path.join(DEPLOY, name)
    text = open(path).read()
    for kw in EXPECTED[name]:
        assert kw in text, f"deploy/{name}: missing '{kw}'"


def _check_root(name):
    path = os.path.join(ROOT, name)
    text = open(path).read()
    for kw in ROOT_FILES[name]:
        assert kw in text, f"{name}: missing '{kw}'"
