"""Entrée CLI : démarre le worker Celery IoT."""

import subprocess


def run() -> None:
    """Lance celery worker sur la queue 'iot'."""
    subprocess.run(  # noqa: S603
        [  # noqa: S607
            "celery",
            "-A", "medbox.iotworker.broker",
            "worker",
            "--loglevel=info",
            "-Q", "iot",
            "-c", "4",
            "-n", "iot@%h",
        ],
        check=True,
    )


if __name__ == "__main__":
    run()
