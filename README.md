# Smart Traffic Management Project

This repository contains simulation, computer vision, and web app components for a smart traffic management system.

## Current Structure

```text
.
├── smart_tms/
│   ├── backend/        # API/app logic
│   ├── frontend/       # UI assets
│   └── simulations/    # simulation modules
├── .gitignore
└── README.md
```

## Recommended Organization

- Keep production/project code inside `smart_tms/`.
- Treat root-level standalone scripts as temporary/prototype files.
- Keep large videos and raw datasets out of git (already covered by `.gitignore`).

Suggested target folders if you continue organizing:

- `scripts/` for one-off runnable files
- `data/` for local datasets/assets (ignored)
- `tests/` for test code

## Getting Started

1. Create and activate a virtual environment.
2. Install dependencies (create a `requirements.txt` or `pyproject.toml` if missing).
3. Run backend/frontend/simulations from the `smart_tms/` subfolders.

## Next Cleanup Steps

- Move root scripts into `smart_tms/simulations/` or `scripts/`.
- Add dependency management file (`requirements.txt` or `pyproject.toml`).
- Add basic tests under `tests/`.
