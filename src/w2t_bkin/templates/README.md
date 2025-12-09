# Package Templates

This directory contains all templates bundled with the w2t-bkin package. These templates are automatically used by the CLI when initializing experiments.

## Template Structure

```text
templates/
├── README.md                           # This file
├── .env.template                       # Docker environment variables template
├── docker-compose.yml.template         # Docker Compose configuration template
├── configuration.toml.template         # Pipeline configuration template
├── full-metadata.toml.template         # NWB metadata template
└── scripts/                            # Click-to-start scripts
    ├── start-server.{bat,sh}.template  # Start Docker containers
    ├── stop-server.{bat,sh}.template   # Stop Docker containers
    ├── view-logs.{bat,sh}.template     # View container logs
    └── open-ui.{bat,sh}.template       # Open Prefect UI in browser
```

## Usage

Templates are automatically loaded by the CLI when running:

```bash
w2t-bkin data init <experiment-path> --lab "Lab Name" --institution "Institution"
```

This creates a self-contained experiment directory with:

- Data structure (`data/raw/`, `data/processed/`, etc.)
- Configuration files (from templates)
- Docker environment setup
- Platform-specific startup scripts

## Development Notes

**For developers working on the repository:**

The repository root contains working copies of some templates for development and testing:

- `/docker-compose.yml` - Actual working Docker Compose file
- `/.env.template` - Environment template for local development
- `/.env` - Generated from template (gitignored)

These root files are **NOT** templates and are **NOT** bundled with the package. The actual templates in this directory (`src/w2t_bkin/templates/`) are the single source of truth for pip-installed packages.

When making changes to Docker configurations or environment variables, update **both**:

1. The template file here (`src/w2t_bkin/templates/`)
2. The working file at repository root (for testing)

## Template Variables

Templates use `{{VARIABLE}}` syntax for substitution:

- `.env.template`: `{{DATA_ROOT}}`, `{{MODELS_ROOT}}`, `{{CONFIG_ROOT}}`, `{{OUTPUT_ROOT}}`
- Script templates: No substitution (used as-is)
- Config templates: No substitution (used as-is)

See `src/w2t_bkin/cli/utils.py:generate_docker_env()` for substitution logic.
