"""Public ticker utilities."""

import re

__all__ = ["normalize_ticker"]


def normalize_ticker(ticker: str) -> str:
    """Normalize a VN stock ticker and return its bare symbol.

    Args:
        ticker (str): Stock ticker in format CODE, EXCHANGE:CODE, or CODE.VN,
            such as Abc, HOSE:ABC, or abc.vn. Case and surrounding whitespace are
            ignored. These formats cannot be combined: EXCHANGE:CODE.VN is
            invalid. After case normalization, CODE contains nonempty ASCII
            alphanumeric parts separated by single dots, such as ABC.Z.
            An exchange prefix contains only ASCII letters. CODE itself must
            not end with .VN.

    Returns:
        str: The uppercase symbol code, with the exchange prefix and
            optional .VN suffix removed and internal dots retained. For example,
            " abc.z.vn " becomes "ABC.Z".

    Raises:
        TypeError: ticker is not a string.
        ValueError: ticker is empty or does not match a supported format.

    Notes:
        Exchange prefixes are discarded, not validated against a listing.
        Normalization does not confirm that an instrument exists. Only .VN is
        treated as a country suffix; other dotted endings remain part of CODE.
    """
    if not isinstance(ticker, str):
        raise TypeError("ticker must be a string")

    normalized = ticker.strip().upper()
    if ":" not in normalized:
        normalized = normalized.removesuffix(".VN")

    match = re.fullmatch(r"(?:[A-Z]+:)?([A-Z0-9]+(?:\.[A-Z0-9]+)*)", normalized)
    if match is None or match.group(1).endswith(".VN"):
        raise ValueError("Invalid ticker format: use CODE, EXCHANGE:CODE, or CODE.VN")
    return match.group(1)
