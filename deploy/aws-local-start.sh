#!/bin/sh
set -eu
cp -R /aws-source/. /home/app/.aws/
exec uvicorn memorias_licantropicas.main:app --host 0.0.0.0 --port 8000
