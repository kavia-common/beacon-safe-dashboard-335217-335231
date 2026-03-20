#!/bin/bash
cd /home/kavia/workspace/code-generation/beacon-safe-dashboard-335217-335231/beacon_safe_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

