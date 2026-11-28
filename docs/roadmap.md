# Roadmap

Implementation status is tracked here, separately from the
[product overview](../README.md).

## Current status

The package provides packaging and development tooling, private async HTTP
utilities, and an async symbol-information API backed by DNSE/Entrade for
HOSE, HNX, and UPCOM.

## Core capabilities

- [x] Fetch a Vietnamese ticker's information, including company stocks and ETFs.
- [ ] Fetch a Vietnamese ticker's quote.
- [ ] Fetch a ticker's historical market data.
- [ ] Fetch events such as new listings, dividends, and other market events.

The remaining capabilities require additional data-source adapters and public APIs.
See the [development guide](development.md) for contributor setup and conventions.
