#!/bin/sh
set -eu
cp -R /aws-source/. /home/app/.aws/
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
