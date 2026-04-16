from __future__ import annotations

import logging
import sys

from ndn.app import NDNApp
from ndn.security import KeychainDigest

from .server import SeedServer

logging.basicConfig(
    format="[{asctime}]{levelname}:{message}",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    style="{",
)


def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else "/seed"
    print(f"Starting seed server on prefix: {prefix}")
    print(f"  Send Interest with JSON ApplicationParameters to {prefix}")
    print(f"  CREATE: {{\"type\": \"CREATE\", \"name\": \"/foo\", \"content\": \"bar\"}}")
    print(f"  DELETE: {{\"type\": \"DELETE\", \"name\": \"/foo\"}}")
    print(f"  LIST  : Interest to {prefix} (no ApplicationParameters)")

    app = NDNApp(keychain=KeychainDigest())
    server = SeedServer(prefix=prefix, app=app)
    server.run()


if __name__ == "__main__":
    main()
