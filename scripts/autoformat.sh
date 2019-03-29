#! /usr/bin/env bash
# Run code formatting tools across the codebase

PYGSTI=$(realpath $(dirname $(realpath $0))/..)

AUTOPEP8_BIN=$(which autopep8)
AUTOPEP8_BASIC_ARGS="--verbose --recursive --in-place"
AUTOPEP8_EXTRA_ARGS="--aggressive --select=W291"

if [ $? -ne 0 ]; then
    echo "No `autopep8` in path. Try running `pip install autopep8`."
    exit 1
fi

# General whitespace autoformatting
FORMAT_CMD="$AUTOPEP8_BIN $AUTOPEP8_BASIC_ARGS $@"
echo "\$ $FORMAT_CMD"
exec $FORMAT_CMD

# Remove trailing whitespace (requires --aggressive flag, which can potentially change semantics)
FORMAT_CMD="$AUTOPEP8_BIN $AUTOPEP8_BASIC_ARGS $AUTOPEP8_EXTRA_ARGS $@"
echo "\$ $FORMAT_CMD"
exec $FORMAT_CMD
