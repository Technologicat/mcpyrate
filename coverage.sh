#!/bin/bash
coverage run --source=. -m mcpyrate.repl.macropython $1
coverage html
