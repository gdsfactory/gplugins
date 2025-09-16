# gplugins - GDSFactory Plugins

gplugins is a Python library providing plugins for gdsfactory for running photonic device simulations including FDTD, FEM, EME, Mode Solvers, TCAD, and Circuit simulations.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively

### Bootstrap, Build and Test the Repository

**CRITICAL: Install uv package manager first (required for all operations):**
```bash
pip install uv  # Use pip since curl may be blocked in some environments
```

**Create virtual environment and install dependencies:**
```bash
uv venv --python 3.12
uv sync --extra dev  # Takes under 1 second. NEVER CANCEL. Set timeout to 60+ seconds.
```

**Download test data (required for most tests):**
```bash
make test-data  # Takes 8 seconds. Downloads gdsfactory test data.
```

**Install pre-commit hooks:**
```bash
uv run pre-commit install  # Takes under 1 second
```

### Plugin-Specific Dependencies

Each plugin requires specific extra dependencies. Install only the plugins you need:

**Working plugins (validated to pass tests):**
```bash
# ALWAYS include --extra dev when testing plugins
uv sync --extra dev --extra klayout    # KLayout integration - takes under 1 second
uv sync --extra dev --extra sax        # S-parameter circuit solver - takes under 1 second  
uv sync --extra dev --extra vlsir      # Circuit netlists - takes under 1 second
uv sync --extra dev --extra path_length_analysis  # Path length analysis - takes under 1 second

# Multiple plugins at once (recommended)
uv sync --extra dev --extra klayout --extra sax --extra vlsir
```

**Plugins requiring external tools (not installable via pip):**
- `meow`: Requires meow-sim package
- `femwell`: Requires femwell package  
- `gmsh`: Requires gmsh system package: `sudo apt-get install -y python3-gmsh gmsh libglu1-mesa libxi-dev libxmu-dev libglu1-mesa-dev`
- `elmer`: Requires ElmerFEM: `sudo apt-add-repository ppa:elmer-csc-ubuntu/elmer-csc-ppa && sudo apt-get update && sudo apt-get install -y elmerfem-csc mpich`
- `meep`: Requires conda: `conda install -c conda-forge pymeeus=*=mpi_mpich_* nlopt -y`
- `tidy3d`: Requires tidy3d package
- `devsim`: Requires devsim package

### Testing

**Run tests for specific plugins:**
```bash
# Test individual plugins (each takes 1-20 seconds) - ALWAYS include dev extras
uv run pytest gplugins/klayout -q                    # Takes 7 seconds - 39 tests, 27 pass, 12 skip
uv run pytest gplugins/sax -q                        # Takes 9 seconds - 2 tests pass  
uv run pytest gplugins/vlsir -q                      # Takes 2 seconds - 5 tests pass
uv run pytest gplugins/path_length_analysis -q       # Takes 20 seconds - 32 tests, 27 pass, 5 skip

# Test multiple plugins with proper dependencies
uv sync --extra dev --extra klayout --extra sax
uv run pytest gplugins/klayout gplugins/sax -q       # Takes 9 seconds - 41 tests total
```

**NEVER CANCEL builds or tests.** Most operations complete within 30 seconds, but allow up to 60 seconds timeout.

### Linting and Code Quality

**Run linting:**
```bash
uv run pre-commit run --all-files ruff               # Takes 10 seconds for full codebase
uv run pre-commit run --all-files ruff-format        # Auto-formats code
```

**Check specific file patterns:**
```bash
# Only check specific plugin directories (faster)
uv run pre-commit run ruff --files gplugins/klayout/
```

### Documentation

**Build documentation (will fail with missing plugins):**
```bash
uv sync --extra docs  # Takes 4 seconds, installs 99+ packages including jupyter-book, sphinx
make docs             # Takes 6 seconds, fails due to missing elmer/gmsh dependencies - this is expected
```

The documentation build requires all plugin dependencies to be installed, which includes external tools like elmer and gmsh that cannot be installed via pip alone.

## Validation

**Always manually validate changes by running tests:**
- ALWAYS install the dev extra: `uv sync --extra dev`
- ALWAYS run `make test-data` before running tests
- Test plugins individually with their specific extras installed
- Use `-q` flag for quiet output, `-v` for verbose
- Use `--collect-only` to check what tests would run without executing them

**Expected timing for common operations:**
- Installing uv: 5 seconds
- Creating venv: under 1 second  
- Installing dev dependencies: under 1 second
- Installing plugin dependencies: under 1 second per plugin
- Running klayout tests: 7 seconds
- Running sax tests: 9 seconds
- Running path_length_analysis tests: 20 seconds
- Pre-commit hooks: 10 seconds
- Downloading test-data: 8 seconds

**Never cancel operations that appear to hang** - wait at least 60 seconds before considering alternatives.

## Common Tasks

### Repository Root Structure
```
.
..
.github/              # GitHub workflows and configuration
.pre-commit-config.yaml
CHANGELOG.md
Dockerfile  
LICENSE
Makefile             # Build automation
README.md
docs/                # Documentation source
gplugins/            # Main plugin packages
notebooks/           # Example notebooks  
pyproject.toml       # Python project configuration
uv.lock             # Dependency lock file
test-data/          # Test data (created by make test-data)
```

### Key Plugin Directories
```
gplugins/
├── common/          # Shared utilities
├── klayout/         # KLayout integration (works)
├── sax/            # S-parameter solver (works)  
├── vlsir/          # Circuit netlists (works)
├── path_length_analysis/  # Path analysis (works)
├── femwell/        # FEM solver (requires external deps)
├── gmsh/           # Mesh generation (requires gmsh)
├── elmer/          # Electrostatic simulation (requires elmer)
├── meow/           # EME solver (requires meow-sim)
├── tidy3d/         # FDTD solver (requires tidy3d)
└── devsim/         # TCAD solver (requires devsim)
```

### Plugin Testing Status
- ✅ **klayout**: 39 tests (27 pass, 12 skip) - fully functional
- ✅ **sax**: 2 tests pass - fully functional  
- ✅ **vlsir**: 5 tests pass - fully functional
- ✅ **path_length_analysis**: 32 tests (27 pass, 5 skip) - fully functional
- ⚠️ **femwell, gmsh, elmer, meow, tidy3d, devsim**: Require external dependencies

### GitHub Workflows
The repository uses GitHub Actions with:
- **test_code.yml**: Tests individual plugins on ubuntu-latest with Python 3.12
- **pages.yml**: Builds and deploys documentation  
- **release.yml**: Handles releases
- Matrix testing across plugins: femwell, gmsh, meow, sax, tidy3d, klayout, vlsir, path_length_analysis

Always run `uv run pre-commit run --all-files` before committing to ensure CI passes.