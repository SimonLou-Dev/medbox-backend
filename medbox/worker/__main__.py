# medbox/worker/__main__.py

import subprocess

def run():
    subprocess.run(
        ["dramatiq", "medbox.worker.main"],
        check=True
    )
