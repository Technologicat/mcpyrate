#!/bin/bash
# This measures the coverage for a single macro-enabled script or module.
coverage run --source=. -m mcpyrate.repl.macropython $1
coverage html
