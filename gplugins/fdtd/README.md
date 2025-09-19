# FDTD Module Workflow & Status

## Current Architecture

```
gplugins/fdtd/
├── simulation.py      # COMSOL-style modular architecture
├── component.py       # Tidy3DComponent (geometry conversion)
├── get_results.py     # S-parameter extraction
├── util.py           # Utility functions
└── example_usage.py   # Basic usage examples
```

## Workflow

**Input**: gdsfactory Component + LayerStack + Materials
**Output**: Tidy3D Simulation → S-parameters

```
GDS Component → Geometry → Material → Physics → Solver → Results
     ↓              ↓         ↓         ↓        ↓        ↓
  Polygons    Tidy3DComp   Mapping   Settings  Config   S-params
```

### 1. Geometry Module
- **Tidy3DComponent**: Converts GDS → 3D structures
- **Process**: KLayout extraction → Shapely polygons → Tidy3D PolySlabs
- **Handles**: Layer stacking, port definitions, visualization

### 2. Material Module
- **Maps**: Material names → Tidy3D Medium objects
- **Supports**: Both built-in and custom materials

### 3. Physics/Solver Modules
- **Configures**: Boundary conditions, mode specs, wavelengths
- **Handles**: Sources, monitors, symmetry planes

## API Example

```python
# Create simulation
sim = FDTDSimulation()

# Set components step by step
sim.geometry = Geometry(component=gf_comp, layer_stack=stack)
sim.material = Material(mapping={"si": td.Medium(...), "sio2": td.Medium(...)})
sim.physics = Physics(wavelength=1.55, bandwidth=0.2)

# Build and run
td_sim = sim.get_simulation()
```

## TODO Items

### High Priority
- [x] **Hybrid properties/methods API** - Clean step-by-step configuration
- [x] **Simplify API** - Minimal boilerplate for common use cases

### Medium Priority
- [ ] **Complete Solver module** - Basic settings only
- [ ] **Complete Results module** - Currently placeholder
- [ ] **Add validation** - Parameter checking and sensible defaults

### Low Priority
- [ ] **Performance optimization** - Address polygon processing inefficiencies
- [ ] **Documentation** - API docs and tutorials
- [ ] **Testing** - Unit tests for all modules
- [ ] **Complete Mesh module** - Currently placeholder
- [ ] **Better error handling** - More descriptive error messages

## Issues to Address
- Material mapping conflicts in Pydantic models
- Field override problems with LayeredComponentBase inheritance
- Need cleaner separation between simple properties and complex methods
