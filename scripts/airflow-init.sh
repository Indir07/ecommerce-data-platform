#!/usr/bin/env bash
set -euo pipefail

airflow db migrate
python /opt/airflow/scripts/create_airflow_user.py
