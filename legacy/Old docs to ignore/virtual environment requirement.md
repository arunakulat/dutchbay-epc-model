## reminder on how to activate virtual environment - script already in scripts folder as venv_up.sh

# from repo root
source scripts/venv_up.sh
# or (POSIX dot)
. scripts/venv_up.sh

# sanity check
which python
python -c "import sys; print(sys.executable); print(sys.version)"