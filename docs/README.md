# W2T-BKIN Documentation

Complete documentation for the W2T Body Kinematics Pipeline.

## Getting Started

- **[Quick Reference](QUICK_REFERENCE.md)** - Fast lookup for common tasks
- **[Migration Guide](MIGRATION_GUIDE.md)** - Migrate from Docker-first to Python-first workflow
- **[FAQ](FAQ.md)** - Frequently asked questions
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions

## User Guides

### CLI Commands

- **[CLI Overview](cli/README.md)** - Command-line interface reference
- **[Data Management](cli/data-management.md)** - Setting up workspace and data
- **[Pipeline Commands](cli/pipeline-commands.md)** - Running processing workflows
- **[Validation](cli/validation.md)** - Validating NWB outputs

### Workflow Patterns

- **[Caching and Reprocessing](user-guide/caching-and-reprocessing.md)** - Understanding artifact caching
- **[Advanced Configuration](user-guide/advanced-configuration.md)** - Customizing pipeline behavior

## Technical References

### Configuration

- **[Configuration Parameters](reference/configuration-parameters.md)** - Complete TOML reference
- **[Pydantic Config Implementation](reference/pydantic-config-implementation.md)** - Type-safe config models

### Architecture

- **[Architecture Diagram](reference/architecture_diagram.mmd)** - System design overview
- **[Data Manager Utilities](reference/data-manager-utilities.md)** - Workspace management

### Orchestration

- **[Prefect UI Configuration](reference/prefect-ui-configuration.md)** - Using Prefect for monitoring (optional)

## Developer Documentation

### Development

- **[Requirements](development/requirements.md)** - Project requirements specification
- **[Design](development/design.md)** - Technical design and architecture
- **[Tasks](development/tasks.md)** - Development task tracking

## Quick Links by Task

### Installation

1. Install from PyPI: `pip install w2t-bkin` or `pip install w2t-bkin[worker]`
2. Initialize workspace: `w2t-bkin data init /path/to/workspace`
3. Add subjects and sessions: `w2t-bkin data add-subject ...`

### Running Pipeline

- **Start Server**: `w2t-bkin server start`
- **Use Prefect UI**: Visit `http://localhost:4200` to trigger workflows
- **Python API**: `from w2t_bkin.flows import process_session_flow; ...`

### Batch Processing

- **Prefect UI**: Use batch-process deployment at `http://localhost:4200`
- **Python API**: `from w2t_bkin.flows import batch_process_flow; ...`

### Validation

- **Validate NWB**: `w2t-bkin validate /path/to/file.nwb`
- **Validate Structure**: `w2t-bkin data validate /path/to/workspace`

## Documentation Structure

```
docs/
├── README.md (this file)
├── QUICK_REFERENCE.md          # Fast lookup
├── MIGRATION_GUIDE.md          # Docker → Python migration
├── FAQ.md                      # Common questions
├── TROUBLESHOOTING.md          # Problem solving
├── cli/                        # CLI documentation
│   ├── README.md
│   ├── data-management.md
│   ├── pipeline-commands.md
│   └── validation.md
├── user-guide/                 # User workflow guides
│   ├── caching-and-reprocessing.md
│   └── advanced-configuration.md
├── reference/                  # Technical references
│   ├── architecture_diagram.mmd
│   ├── configuration-parameters.md
│   ├── pydantic-config-implementation.md
│   ├── data-manager-utilities.md
│   └── prefect-ui-configuration.md
└── development/                # Developer docs
    ├── requirements.md
    ├── design.md
    └── tasks.md
```

## Contributing

See [development/](development/) for development guidelines and architecture documentation.

## Support

- **Issues**: https://github.com/BorjaEst/w2t-bkin/issues
- **Discussions**: https://github.com/BorjaEst/w2t-bkin/discussions
