#!/bin/bash
# Vercel build step (run by @vercel/static-build).
# Installs Python dependencies and collects static files into the
# distDir (staticfiles_build/) that Vercel serves at /static/.
#
# Vercel's build image uses a uv-managed Python that blocks plain pip
# (PEP 668), so we pass --break-system-packages for this build-only install.
set -e

python3 -m pip install --break-system-packages -r requirements.txt
python3 manage.py collectstatic --noinput --clear
