#!/usr/bin/env python3
"""
Minimal smoke test used by CI: hits a running Paradox AI server and checks
that the core endpoints respond. This is NOT a substitute for a real unit/
integration test suite -- it only catches "the container doesn't even
start" or "a route 500s" class failures. Assumes single-tenant mode (no
PARADOX_API_KEYS set), which is what CI runs with.
"""
import json
import sys
import urllib.request

BASE = "http://localhost:8000"


def check(path, expect_keys=None):
    url = BASE + path
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            if resp.status != 200:
                print(f"FAIL {path}: status {resp.status}")
                return False
            data = json.loads(resp.read())
            if expect_keys:
                missing = [k for k in expect_keys if k not in data]
                if missing:
                    print(f"FAIL {path}: missing keys {missing}")
                    return False
            print(f"OK   {path}")
            return True
    except Exception as e:
        print(f"FAIL {path}: {e}")
        return False


def main():
    results = [
        check("/api/meta", expect_keys=["name", "tagline", "multi_tenant"]),
        check("/api/providers", expect_keys=["providers"]),
        check("/api/workspace/files", expect_keys=["files"]),
    ]
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
