#! /usr/bin/env bash
# Run code formatting tools across the codebase

PYGSTI=$(realpath $(dirname $(realpath $0))/..)
AUTOPEP8_BIN=$(which autopep8)

if [ $? -ne 0 ]; then
    echo "No `autopep8` in path. Try running `pip install autopep8`."
    exit 1
fi

if [ $# -eq 0 ]; then
    # Default source targets
    TARGET_SRC=("$PYGSTI/packages/pygsti" "$PYGSTI/test" "$PYGSTI/scripts" "$PYGSTI/setup.py")
else
    # Use the supplied argument, if given
    TARGET_SRC=$@
fi

FORMAT_CMD="$AUTOPEP8_BIN --aggressive --experimental --verbose --recursive --in-place ${TARGET_SRC[*]}"
echo "\$ $FORMAT_CMD"
exec $FORMAT_CMD
