"""Tasks command wiring."""

import typer


def register(app: typer.Typer) -> None:
    """Register tasks commands on the root CLI app."""

    @app.command("tasks")
    def tasks() -> None:
        """Placeholder for future task commands."""
        return
