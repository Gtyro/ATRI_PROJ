"""Verify that the standalone WebUI browser endpoint is reachable."""

import os
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    host = os.getenv("WEBUI_HOST", "127.0.0.1")
    port = os.getenv("WEBUI_PORT", "8188")
    url = f"http://{host}:{port}/health"
    deadline = time.monotonic() + 10

    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    print(f"WebUI health check passed: {url}")
                    return 0
        except URLError:
            time.sleep(0.25)

    print(f"WebUI health check failed: {url}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
