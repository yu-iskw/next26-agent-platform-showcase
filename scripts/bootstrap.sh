#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/bin/activate
pip install -e .
cp -n .env.example .env || true
echo "Bootstrap complete. Edit .env before deploying."
