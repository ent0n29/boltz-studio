# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Boltz Studio is a web UI for protein structure prediction using [Boltz](https://github.com/jwohlwend/boltz). It provides a FastAPI backend with a vanilla JavaScript frontend for running Boltz-2 predictions on protein sequences, ligands, and multi-chain complexes.

## Commands

### Development Setup
```bash
make dev          # Set up dev environment (Python venv)
```

### Build & Run
```bash
make build        # Verify backend imports
make run          # Start the server
```

### Testing & Linting
```bash
make test         # Run pytest (uses pytest-asyncio)
make lint         # Run ruff check
make lint-fix     # Auto-fix linting issues

# Run single test file:
. .venv/bin/activate && pytest tests/test_routes.py -v

# Run single test:
. .venv/bin/activate && pytest tests/test_routes.py::test_submit_prediction -v
```

### Cleanup
```bash
make clean        # Remove all build artifacts
make reset        # Clean + reinstall dev environment
```

## Architecture

### Backend (Python/FastAPI)

```
boltz_studio/
├── app.py          # FastAPI app factory, lifespan manager, route mounting
├── main.py         # Entry point (CLI), uvicorn launcher
├── config.py       # Pydantic settings (env vars with BOLTZ_STUDIO_ prefix)
├── routes/         # API endpoints (auth, prediction, design, social, websocket, pdb)
├── services/       # Business logic
│   ├── boltz_runner.py    # Core prediction execution (direct API or CLI fallback)
│   ├── model_manager.py   # Boltz model caching and initialization
│   ├── job_store.py       # In-memory job state
│   ├── database.py        # SQLite persistence
│   └── progress_manager.py # WebSocket progress broadcasting
└── models/         # Pydantic models (prediction, user, design, social)
```

### Frontend (Vanilla JavaScript)

```
boltz_studio/static/
├── index.html      # Main HTML with tabs, modals, auth UI
├── css/
│   └── style.css   # All styles (tabs, modals, community, social)
└── js/
    ├── app.js      # Core prediction, 3D viewer, tab switching
    ├── auth.js     # OAuth login/logout, user menu
    ├── community.js # Browse designs, search, design cards
    └── social.js   # Stars, forks, comments, collections
```

**Key patterns:**
- Routes depend on services via dependency injection
- `BoltzRunner` tries direct Boltz Python API first, falls back to CLI
- WebSocket (`/ws/{job_id}`) provides real-time prediction progress
- SQLite database for persistence (`boltz_studio.db`)
- Environment variables prefixed with `BOLTZ_STUDIO_` (e.g., `BOLTZ_STUDIO_PORT`)
- Static files served directly from `boltz_studio/static/`

## Key Technical Details

- **Boltz integration**: The runner generates YAML input files, handles MSA generation via ColabFold server, and parses PDB/confidence outputs
- **Model caching**: `ModelManager` caches the Boltz model to avoid reloading between predictions
- **Async predictions**: Long-running predictions run in thread pools to not block the event loop
- **Session management**: Uses Starlette's SessionMiddleware for OAuth state; custom session store for user sessions
- **3D Visualization**: Uses 3Dmol.js for protein structure rendering with pLDDT coloring

## Configuration

Settings are in `config.py`. Key environment variables:
- `BOLTZ_STUDIO_PORT` - Server port (default: 8000)
- `BOLTZ_STUDIO_DEBUG` - Enable dev features like dev login
- `BOLTZ_STUDIO_GOOGLE_CLIENT_ID/SECRET` - Google OAuth
- `BOLTZ_STUDIO_GITHUB_CLIENT_ID/SECRET` - GitHub OAuth
- `BOLTZ_STUDIO_SESSION_SECRET` - Cookie signing key
