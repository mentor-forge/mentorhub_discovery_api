#!/usr/bin/env sh
set -e

root=$(cd "$(dirname "$0")/.." && pwd)
image="${DISCOVERY_API_IMAGE:-ghcr.io/mentor-forge/mentorhub_discovery_api:latest}"
exec docker build --build-arg "BUILT_AT=${BUILT_AT:-LOCAL}" -t "$image" -f "$root/Dockerfile" "$root"
