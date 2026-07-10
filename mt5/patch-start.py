"""Deterministically patch the pinned upstream MT5 startup dependency blocks."""

from pathlib import Path

START = Path("/Metatrader/start.sh")

WINDOWS_OLD = """# Install mt5linux library in Windows if not installed
show_message "[6/7] Checking and installing mt5linux library in Windows if necessary"
if ! is_wine_python_package_installed "mt5linux"; then
    $wine_executable python -m pip install --no-cache-dir "mt5linux>=0.1.9"
fi
"""
WINDOWS_NEW = """# Install the audited RPyC server dependencies in Wine from verified local wheels.
show_message "[6/7] Installing pinned Wine RPyC server dependencies"
$wine_executable python -m pip install --no-index --no-deps --force-reinstall \\
    /opt/mt5-hardening/numpy-1.26.4-cp39-cp39-win32.whl \\
    /opt/mt5-hardening/plumbum-1.7.0-py2.py3-none-any.whl \\
    /opt/mt5-hardening/rpyc-6.0.2-py3-none-any.whl \\
    || exit 1
$wine_executable python -c "import rpyc; \
v=rpyc.__version__; \
assert tuple(v) == (6, 0, 2) if isinstance(v, tuple) else str(v) == '6.0.2'" \\
    || exit 1
"""

LINUX_OLD = """# Install mt5linux library in Linux if not installed
show_message "[6/7] Checking and installing mt5linux library in Linux if necessary"
if ! is_python_package_installed "mt5linux"; then
    pip install --break-system-packages --no-cache-dir --no-deps mt5linux && \\
    pip install --break-system-packages --no-cache-dir rpyc plumbum numpy
fi
"""
LINUX_NEW = """# Install the audited Linux bridge from verified local wheels
# into the persistent user site.
show_message "[6/7] Installing pinned Linux MT5 bridge dependencies"
python3 -m pip install --user --break-system-packages --no-index --no-deps \\
    --force-reinstall \\
    /opt/mt5-hardening/plumbum-1.7.0-py2.py3-none-any.whl \\
    /opt/mt5-hardening/rpyc-6.0.2-py3-none-any.whl \\
    /opt/mt5-hardening/numpy-2.4.6-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl \\
    /opt/mt5-hardening/mt5linux-0.1.9-py3-none-any.whl \\
    || exit 1
python3 -c "import importlib.metadata as m, rpyc; \
v=rpyc.__version__; \
assert m.version('mt5linux') == '0.1.9'; \
assert tuple(v) == (6, 0, 2) if isinstance(v, tuple) else str(v) == '6.0.2'" \\
    || exit 1
"""

source = START.read_text(encoding="utf-8")
for label, old, new in (
    ("Wine dependency block", WINDOWS_OLD, WINDOWS_NEW),
    ("Linux dependency block", LINUX_OLD, LINUX_NEW),
):
    if source.count(old) != 1:
        raise SystemExit(f"{label} did not match pinned upstream exactly")
    source = source.replace(old, new)
START.write_text(source, encoding="utf-8")
