#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
case "$(uname -m)" in
  x86_64) triplet=x64-linux-release ;;
  aarch64) triplet=arm64-linux-release ;;
  *) echo 'Unsupported architecture' >&2; exit 1 ;;
esac
export VCPKG_FORCE_SYSTEM_BINARIES=1
./vcpkg/bootstrap-vcpkg.sh -disableMetrics
cmake -S . -B build/cli -DCMAKE_BUILD_TYPE=Release \
  -DASSFONTS_BUILD_GUI=OFF \
  -DVCPKG_MANIFEST_DIR="$PWD/packaging/cli" \
  -DVCPKG_TARGET_TRIPLET="$triplet" \
  -DVCPKG_HOST_TRIPLET="$triplet"
cmake --build build/cli --target assfonts --parallel 2
cmake -S tests -B build/queue-tests -DCMAKE_BUILD_TYPE=Release
cmake --build build/queue-tests --parallel 2
ctest --test-dir build/queue-tests --output-on-failure
python3 tests/cli_batch_test.py build/cli/src/cli/assfonts
