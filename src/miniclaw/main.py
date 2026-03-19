"""
MiniClaw Entry Points
"""

from miniclaw.cli import app as cli_app

__all__ = ["cli_app"]


def main():
    cli_app()


if __name__ == "__main__":
    main()
