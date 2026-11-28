import subprocess
import sys
from dataclasses import asdict
from importlib.resources import files
from pathlib import Path

import vfinance
from vfinance.models import SymbolInfo


def test_package_imports_without_repository_on_python_path(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import vfinance; "
            "import vfinance._cache as cache; "
            "import vfinance._dnse as dnse; "
            "import vfinance.stocks as stocks; "
            "from vfinance.models import SymbolInfo; "
            "from vfinance.stocks import get_info; "
            "from vfinance._utils import fetch_url_async; "
            "from vfinance.utils import normalize_ticker; "
            "assert all(getattr(cache, name).__module__ == 'vfinance._cache' "
            "for name in cache.__all__); "
            "cache.set('isolated', 'key', 'value'); "
            "assert cache.get('isolated', 'key') == 'value'; "
            "cache.delete('isolated', 'key'); "
            "assert cache.get('isolated', 'key') is None; "
            "cache.delete_domain('isolated'); "
            "assert not hasattr(cache, 'LRUCache'); "
            "assert not hasattr(vfinance, 'Cache'); "
            "assert not hasattr(dnse, 'SymbolInfo'); "
            "assert not hasattr(stocks, 'SymbolInfo'); "
            "assert not hasattr(vfinance, 'SymbolInfo')",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_symbol_info_omits_removed_profile_fields() -> None:
    info = SymbolInfo(exchange="HOSE", symbol="FPT", name="CTCP FPT", overview="")

    assert {
        "address",
        "phone",
        "fax",
        "email",
        "tax_id",
        "business_status",
    }.isdisjoint(asdict(info))


def test_typing_marker_is_packaged() -> None:
    assert files(vfinance).joinpath("py.typed").is_file()
