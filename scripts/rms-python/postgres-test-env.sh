#!/usr/bin/env bash
rms_test_tool_root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export RMS_DB_HOST="/tmp/rms-pg-$(printf '%s' "$rms_test_tool_root/postgres-test" | sha256sum | cut -c1-16)"
export RMS_DB_PORT=55471 RMS_DB_NAME=rms_synthetic RMS_DB_USER=rms_synthetic_test RMS_DB_PASSWORD=
unset rms_test_tool_root
