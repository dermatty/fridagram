from subprocess import run

_APP_PACKAGE = "fridagram"


def start():
    command = ["poetry", "run", "python", "-u", "-m", _APP_PACKAGE]
    run(command)
