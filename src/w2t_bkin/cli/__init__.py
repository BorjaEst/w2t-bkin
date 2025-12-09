"""W2T-BKIN CLI - Thin presentation layer for Prefect flows.

This CLI provides user-friendly commands for the w2t-bkin pipeline.
All business logic resides in flows/ and operations/ modules.

Command Structure:
    w2t-bkin run              # Process single session
    w2t-bkin batch            # Process multiple sessions
    w2t-bkin discover         # List available sessions
    w2t-bkin validate         # Validate NWB file
    w2t-bkin inspect          # Inspect NWB file
    w2t-bkin version          # Show version
    w2t-bkin data init        # Initialize experiment
    w2t-bkin data add-subject # Add subject
    w2t-bkin data add-session # Add session
    w2t-bkin data import-raw  # Import raw data
    w2t-bkin data validate    # Validate experiment structure
"""

import typer

# Create main app
app = typer.Typer(
    name="w2t-bkin",
    help="W2T Body Kinematics Pipeline - Prefect-native NWB processing",
    add_completion=True,
)

# Import and register commands
from .data import data_app
from .pipeline import batch, discover, run, version
from .validation import inspect, validate

# Register root-level commands
app.command()(run)
app.command()(batch)
app.command()(discover)
app.command()(validate)
app.command()(inspect)
app.command()(version)

# Register subcommand groups
app.add_typer(data_app, name="data")

__all__ = ["app"]
