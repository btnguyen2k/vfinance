from typing import cast

import pytest

from vfinance.utils import normalize_ticker


@pytest.mark.parametrize(
    ("ticker", "expected"),
    [
        ("BID", "BID"),
        (" bid ", "BID"),
        ("HOSE:bid", "BID"),
        ("hnx:shs", "SHS"),
        ("UPCoM:vgt", "VGT"),
        ("bid.vn", "BID"),
        ("CBID2305", "CBID2305"),
        ("ABC.Z", "ABC.Z"),
        (" abc.z.vn ", "ABC.Z"),
        ("HOSE:abc.z", "ABC.Z"),
        ("A1.B2.C3.VN", "A1.B2.C3"),
        ("BID.US", "BID.US"),
        ("VN", "VN"),
        ("ABC.VNN.VN", "ABC.VNN"),
    ],
)
def test_normalize_ticker(ticker: str, expected: str) -> None:
    assert normalize_ticker(ticker) == expected


@pytest.mark.parametrize(
    "ticker",
    [
        "",
        "HOSE:",
        ":BID",
        "BID/../SHS",
        "HOSE:BID:SHS",
        "B ID",
        ".VN",
        "HOSE:BID.VN",
        "hnx:abc.z.vn",
        "ABC.VN.VN",
        ".ABC",
        "ABC.",
        "ABC..Z",
        ".",
        "HOSE:ABC.",
    ],
)
def test_normalize_ticker_rejects_malformed_strings(ticker: str) -> None:
    with pytest.raises(ValueError, match="Invalid ticker format"):
        normalize_ticker(ticker)


def test_normalize_ticker_rejects_non_string_input() -> None:
    with pytest.raises(TypeError, match="ticker must be a string"):
        normalize_ticker(cast(str, None))
