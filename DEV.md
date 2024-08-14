# Prepare environment
1. `py -3.10 -m venv .venv`
2. `.venv/source/activate`
3. `python -m pip install -r requirements/dev.txt`
4. `pre-commit install` - делает так, чтобы хуки запускались перед каждым коммитом

если активировать pre-commit, то станет невозможно делать коммиты через интерфейс vs code, только через консоль
