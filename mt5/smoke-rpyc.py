#!/usr/bin/env python3
"""Read-only compatibility smoke for the hardened MT5 RPyC bridge."""

from __future__ import annotations

import argparse

import rpyc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8001, type=int)
    args = parser.parse_args()

    connection = rpyc.classic.connect(args.host, args.port)
    connection._config["sync_request_timeout"] = 15
    try:
        connection.execute("import MetaTrader5 as mt5; import rpyc")
        server_version = connection.eval(
            "'.'.join(map(str, rpyc.__version__)) if isinstance(rpyc.__version__, tuple) "
            "else str(rpyc.__version__)"
        )
        if server_version != "6.0.2":
            raise RuntimeError(f"unexpected Wine RPyC version: {server_version}")
        terminal_info = rpyc.classic.obtain(connection.eval("mt5.terminal_info()"))
        print(
            "RPyC compatibility smoke passed; "
            f"terminal_info_available={terminal_info is not None}"
        )
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
