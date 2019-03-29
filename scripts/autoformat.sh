#! /usr/bin/env bash
# Run code formatting tools across the codebase

PYGSTI=$(realpath $(dirname $(realpath $0))/..)

AUTOPEP8_BIN=$(which autopep8)
AUTOPEP8_BASIC_ARGS="--verbose --recursive --in-place"
AUTOPEP8_EXTRA_ARGS="--aggressive --select=W2"

if [ $? -ne 0 ]; then
    echo "No `autopep8` in path. Try running `pip install autopep8`."
    exit 1
fi

if [ $# -eq 0 ]; then
    TARGET="$PYGSTI"
else
    TARGET="$@"
fi

# General whitespace autoformatting
FORMAT_CMD="$AUTOPEP8_BIN $AUTOPEP8_BASIC_ARGS $TARGET"
echo "\$ $FORMAT_CMD"
$FORMAT_CMD

# Remove trailing whitespace, which requires --aggressive flag
# In principle, this can potentially alter semantics, but as long as
# we select only W2 warnings this is practically impossible.
FORMAT_CMD="$AUTOPEP8_BIN $AUTOPEP8_BASIC_ARGS $AUTOPEP8_EXTRA_ARGS $TARGET"
echo "\$ $FORMAT_CMD"
$FORMAT_CMD
