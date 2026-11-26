import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import vfinance


def test_package_imports_without_repository_on_python_path(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", "import vfinance"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_typing_marker_is_packaged() -> None:
    assert files(vfinance).joinpath("py.typed").is_file()
