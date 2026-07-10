from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from pathlib import Path, PurePosixPath

from packaging.requirements import Requirement

SDK_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = SDK_ROOT / "pyproject.toml"
LICENSE_PATH = SDK_ROOT / "LICENSE"
HATCHLING_VERSION = "1.31.0"


def _project_metadata() -> dict[str, object]:
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def _assert_apache_metadata(metadata: Message) -> None:
    assert metadata["License-Expression"] == "Apache-2.0"
    assert metadata.get_all("License-File") == ["LICENSE"]


def test_hatchling_build_backend_is_exactly_pinned() -> None:
    metadata = _project_metadata()
    build_system = metadata["build-system"]
    assert isinstance(build_system, dict)
    requirements = build_system["requires"]
    assert isinstance(requirements, list)

    hatchling_requirements = [
        Requirement(value)
        for value in requirements
        if isinstance(value, str) and Requirement(value).name == "hatchling"
    ]
    assert len(hatchling_requirements) == 1

    hatchling = hatchling_requirements[0]
    assert not hatchling.extras
    assert hatchling.marker is None
    assert hatchling.url is None
    assert str(hatchling.specifier) == f"=={HATCHLING_VERSION}"


def test_project_contains_the_canonical_apache_2_license() -> None:
    metadata = _project_metadata()
    project = metadata["project"]
    assert isinstance(project, dict)
    assert project["license"] == "Apache-2.0"
    assert LICENSE_PATH.is_file()

    license_text = LICENSE_PATH.read_text(encoding="utf-8")
    canonical_markers = (
        "Apache License",
        "Version 2.0, January 2004",
        "http://www.apache.org/licenses/",
        "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION",
        "END OF TERMS AND CONDITIONS",
        "APPENDIX: How to apply the Apache License to your work.",
    )
    assert len(license_text) > 10_000
    assert all(marker in license_text for marker in canonical_markers)


def test_offline_wheel_and_sdist_include_license_and_metadata(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to verify the distribution build"

    project_copy = tmp_path / "strategy-sdk"
    shutil.copytree(
        SDK_ROOT,
        project_copy,
        ignore=shutil.ignore_patterns(
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "__pycache__",
            "*.pyc",
            "dist",
        ),
    )
    output_dir = tmp_path / "dist"
    environment = os.environ.copy()
    environment.update(
        {
            "UV_COLOR": "never",
            "UV_NO_PROGRESS": "1",
            "UV_PYTHON_DOWNLOADS": "never",
        }
    )

    result = subprocess.run(
        [
            uv,
            "build",
            "--offline",
            "--no-sources",
            "--out-dir",
            str(output_dir),
            ".",
        ],
        cwd=project_copy,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    wheels = tuple(output_dir.glob("*.whl"))
    sdists = tuple(output_dir.glob("*.tar.gz"))
    assert len(wheels) == 1
    assert len(sdists) == 1

    with zipfile.ZipFile(wheels[0]) as wheel:
        wheel_names = wheel.namelist()
        wheel_licenses = [
            name for name in wheel_names if name.endswith(".dist-info/licenses/LICENSE")
        ]
        wheel_metadata = [name for name in wheel_names if name.endswith(".dist-info/METADATA")]
        assert len(wheel_licenses) == 1
        assert len(wheel_metadata) == 1
        expected_license = LICENSE_PATH.read_bytes()
        assert wheel.read(wheel_licenses[0]) == expected_license
        _assert_apache_metadata(
            BytesParser(policy=default).parsebytes(wheel.read(wheel_metadata[0]))
        )

    with tarfile.open(sdists[0], mode="r:gz") as sdist:
        sdist_members = sdist.getmembers()
        sdist_licenses = [
            member
            for member in sdist_members
            if PurePosixPath(member.name).name == "LICENSE"
            and len(PurePosixPath(member.name).parts) == 2
        ]
        package_metadata = [
            member
            for member in sdist_members
            if PurePosixPath(member.name).name == "PKG-INFO"
            and len(PurePosixPath(member.name).parts) == 2
        ]
        assert len(sdist_licenses) == 1
        assert len(package_metadata) == 1

        archived_license = sdist.extractfile(sdist_licenses[0])
        archived_metadata = sdist.extractfile(package_metadata[0])
        assert archived_license is not None
        assert archived_metadata is not None
        assert archived_license.read() == expected_license
        _assert_apache_metadata(BytesParser(policy=default).parsebytes(archived_metadata.read()))
