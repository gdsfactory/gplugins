# Tidy3D GPPlugin Workflow

## Overview

The Tidy3D plugin provides electromagnetic simulation capabilities for gdsfactory photonic components using the Tidy3D FDTD solver.

## Main Processing Pipeline

```text
┌─────────────────────────────┐
│ 1. INPUT: GDS Component     │
├─────────────────────────────┤
│ • gdsfactory component      │
│ • Layer stack definition    │
│ • Port locations            │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 2. EXTRACT: Get Polygons    │
├─────────────────────────────┤
│ • KLayout extracts shapes   │
│ • Merge overlapping polys   │
│ • Convert nm → μm           │
│ ⚠️  TODO: Keep in KLayout   │
│    (inefficient KLayout→    │
│     Shapely→KLayout cycle)  │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 3. CONVERT: Create 3D Model │
├─────────────────────────────┤
│ • Shapely → Tidy3D PolySlab│
│ • Add layer thickness (z)   │
│ • Assign materials          │
│ ⚠️  ISSUE: .buffer(0.0)     │
│    called unnecessarily     │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 4. BUILD: Setup Simulation  │
├─────────────────────────────┤
│ • Create simulation box     │
│ • Add PML boundaries        │
│ • Set mesh (λ/30 default)   │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 5. PORTS: Add Sources       │
├─────────────────────────────┤
│ • ModeSource at each port   │
│ • ModeMonitor at each port  │
│ • Set mode type (TE/TM)     │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 6. RUN: Execute FDTD        │
├─────────────────────────────┤
│ • Submit to cloud           │
│ • Run simulation            │
│ • Download results          │
│ ⚠️  QUIRK: time.sleep(0.2)  │
│    before run (unclear why) │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 7. EXTRACT: S-parameters    │
├─────────────────────────────┤
│ • Calculate mode overlaps   │
│ • Build S-matrix            │
│ • Return complex values     │
│ ⚠️  ISSUE: 4-level nested   │
│    for loops over all port  │
│    and mode combinations    │
└─────────────────────────────┘
```

## How It Works: Class Architecture

The workflow is implemented through two main classes:

### 1. Tidy3DComponent Class
Handles geometry conversion from gdsfactory to Tidy3D:

```text
┌─────────────────────────────┐
│   Tidy3DComponent           │
├─────────────────────────────┤
│ Properties:                 │
│ • polyslabs: geometry       │
│ • structures: with materials│
│ • ports: optical ports      │
│                             │
│ Methods:                    │
│ • get_ports()               │
│ • get_simulation()          │
│ • get_component_modeler()   │
└─────────────────────────────┘
```

### 2. ComponentModeler Class
Tidy3D's built-in class that handles simulation:

```text
┌─────────────────────────────┐
│   ComponentModeler          │
├─────────────────────────────┤
│ Automatically creates:      │
│ • ModeSource at each port   │
│ • ModeMonitor at each port  │
│ • Port-to-port connections  │
│                             │
│ Then:                       │
│ • Runs FDTD simulation      │
│ • Extracts S-parameters     │
└─────────────────────────────┘
```

## Usage Example

```python
import gdsfactory as gf
from gplugins.tidy3d import write_sparameters

# Create component
component = gf.components.mmi1x2()

# Run simulation
sparams = write_sparameters(
    component=component,
    wavelength=1.55,
    bandwidth=0.2,
    num_freqs=21,
    mode_spec=td.ModeSpec(num_modes=1, filter_pol="te"),
)

# Results:
# sparams = {"o1@0,o2@0": S_matrix, "o1@0,o3@0": S_matrix, ...}
```

The `write_sparameters()` function is the main entry point that orchestrates the entire workflow.

## Material System Issues

The plugin has **duplicated material systems** that need consolidation:

```text
Material Input → Result
─────────────────────────────────────────
1.45             → Simple refractive index
"si"             → Built-in silicon (n=3.47)
"sio2"           → Built-in silica (n=1.47)
("cSi", "...")   → Tidy3D library with dispersion
td.Medium(...)   → Custom material definition
```

**⚠️ Current Problems:**

1. **Two conflicting material mappings:**
   - `material_name_to_medium` (component.py) - simple permittivity values
   - `material_name_to_tidy3d` (materials.py) - full dispersive models

2. **Inconsistent defaults:**
   - Default uses simple values (si: n=3.47)
   - But dispersive library available (cSi: full Sellmeier model)

3. **User confusion:**
   - Different functions for grating couplers vs regular components
   - No clear guidance on when to use which material system

## Port and Mode Handling

The key insight is that **everything happens automatically** in step 5 above:

1. **Port Detection**: gdsfactory ports are automatically found
2. **Mode Sources**: Created at each port for excitation
3. **Mode Monitors**: Created at each port for measurement
4. **S-Matrix**: Built from all port-to-port transmissions

## Key Features

**Geometry:** Multi-layer, sidewall angles, holes, padding, extensions
**Materials:** Library access, custom definition, dispersion, anisotropy
**Simulation:** Auto S-parameters, multi-mode, batch processing, symmetry

## File Organization

```text
gplugins/tidy3d/
├── __init__.py                         # Main exports
├── component.py                        # Core classes
│   ├── Tidy3DComponent                # Main conversion class
│   ├── write_sparameters()            # S-param extraction
│   └── write_sparameters_batch()      # Batch processing
├── materials.py                        # Material system
│   ├── get_medium()                   # Material conversion
│   ├── get_index()                    # Index extraction
│   └── material_name_to_tidy3d        # Library mappings
├── modes.py                           # Mode solving
├── types.py                           # Type definitions
├── util.py                            # Helper functions
└── get_simulation_grating_coupler.py  # Grating specialization
```
