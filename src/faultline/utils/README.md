# Utils Package

This package contains shared infrastructure helpers used across the application.

## Main Files

- `config.py` loads YAML config files such as mechanisms, stages, scoring, prompts, and provider settings.
- `env.py` bootstraps `.env` and `.env.local` discovery.
- `io.py` handles directory creation plus JSON and text serialization helpers.
- `logging.py` configures JSON logging for CLI and runtime use.

## What It Is For

- Keeping cross-cutting support code out of workflow and analysis modules.
- Providing one place for config and operational plumbing.

## Use This Package When

- You need shared helpers that are not specific to one workflow stage.
- You are changing config-loading behavior or adding a new YAML-backed config surface.
- You want consistent file output or logging behavior across the application.
