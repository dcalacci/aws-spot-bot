import os
import subprocess
import click
from os.path import expanduser

def _highlight(x, fg='green'):
    click.secho(x, fg=fg)

if __name__ == "__main__":
    _highlight("Making directory ~/.lab_config")
    if not os.path.exists(expanduser("~/.lab_config")):
        os.mkdir(expanduser("~/.lab_config"))
    if not os.path.exists(expanduser("~/.lab_config/aws-spot-bot")):
        os.mkdir(expanduser("~/.lab_config/aws-spot-bot"))

    _highlight("Copying files...")
    path = expanduser("~/.lab_config/aws-spot-bot")
    subprocess.call(["cp", "-R", ".", path])

    _highlight("Making executable script `labbox` in /usr/local/bin")
    script_text = """#!/usr/bin/env bash
export PYTHONPATH=$PYTHONPATH:$HOME/.lab_config/
python -m aws-spot-bot.main $@
"""

    with open("/usr/local/bin/labbox", 'w') as f:
        f.write(script_text)

    subprocess.call(["chmod", "+x", "/usr/local/bin/labbox"])
    _highlight("Done! run labbox --help to get started.")
