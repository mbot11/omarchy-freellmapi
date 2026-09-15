#!/usr/bin/env bash
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
python3 "$here/test_normalize.py" -v
python3 "$here/test_collect_write.py" -v
python3 "$here/test_security.py" -v
