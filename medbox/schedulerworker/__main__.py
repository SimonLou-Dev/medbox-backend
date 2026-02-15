# medbox/schedulerworker/__main__.py

import subprocess


def run():
    subprocess.run(  # noqa: S603
        ["dramatiq", "medbox.schedulerworker.main"],  # noqa: S607
        check=True,
    )


if __name__ == "__main__":
    run()
