"""W2T-BKIN CLI - Thin presentation layer for Prefect flows.

This CLI provides user-friendly commands for the w2t-bkin pipeline.
All processing happens through Prefect deployments in the UI.

Command Structure:
    w2t-bkin server start     # Start Prefect server with deployments
    w2t-bkin server stop      # Stop Prefect server
    w2t-bkin server status    # Check server status
    w2t-bkin server restart   # Restart Prefect server
    w2t-bkin discover         # List available sessions
    w2t-bkin validate         # Validate NWB file
    w2t-bkin inspect          # Inspect NWB file
    w2t-bkin version          # Show version
    w2t-bkin data init        # Initialize experiment
    w2t-bkin data add-subject # Add subject
    w2t-bkin data add-session # Add session
    w2t-bkin data import-raw  # Import raw data
    w2t-bkin data validate    # Validate experiment structure

Workflow:
    1. w2t-bkin data init /path/to/workspace
    2. w2t-bkin data add-subject ...
    3. w2t-bkin data add-session ...
    4. w2t-bkin server start
       OR use --dev flag in step 4 for development
    6. Use Prefect UI at http://127.0.0.1:4200 to run workflows
"""

import typer

# Create main app
app = typer.Typer(
    name="w2t-bkin",
    help="W2T Body Kinematics Pipeline - Prefect-native NWB processing",
    add_completion=True,
)

# Import and register commands
from w2t_bkin.cli.data import data_app
from w2t_bkin.cli.pipeline import discover, version
from w2t_bkin.cli.server import server_app
from w2t_bkin.cli.validation import inspect, validate
from w2t_bkin.cli.worker import worker_app

# Register root-level commands
app.command()(discover)
app.command()(validate)
app.command()(inspect)
app.command()(version)

# Register subcommand groups
app.add_typer(data_app, name="data")
app.add_typer(server_app, name="server")
app.add_typer(worker_app, name="worker")

__all__ = ["app"]
