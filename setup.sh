#!/bin/bash
# Vercel build step (run by @vercel/static-build).
# Installs Python dependencies and collects static files into the
# distDir (staticfiles_build/) that Vercel serves at /static/.
set -e

pip install -r requirements.txt
python3 manage.py collectstatic --noinput --clear
