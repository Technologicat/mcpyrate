#!/bin/bash
VERSION="$1"
twine upload dist/mcpyrate-${VERSION}.tar.gz dist/mcpyrate-${VERSION}-py3-none-any.whl
