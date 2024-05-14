# Lumerical plugins

## FDTD

Allows you to write Sparameters using FDTD.


## Lumerical INTERCONNECT-GDSFactory Schematic Driven Layout Flow

This is a circuit design flow that takes a SPICE netlist exported from an INTERCONNECT schematic and generates a GDS layout from the netlist using GDSFactory.
This plugin parases an interconnect netlist to a YAML netlist such that gdsfactory can take care of the placement and routing.

Each PDK requires a mapping file to map the cell names and port names from the Interconnect CML models to the GDSFactory layout objects.

## Commands:

The following arguments are required to run this script:

```bash
python .py working_directory –mapping_file_name –mode -netlist_file_name
```

- `working_dir` : working directory where YAML netlist will be saved
- `mapping_file_name` : Mapping* file that maps CML models to layout cells [should end with .yml]
- `mode` : Mode for netlist export (overwrite or update), where overwrite is the [default]
- `netlist_file_name` : Netlist file name exported from INTC [should end with .spi].

*Note: Mapping file also maps the GDSFactory PDK to be used for parsing. If the YAML mapping file is not provided, then we get the PDK name from netlist and assume that the port mapping will be the same (eg - `opt_1`, `opt_2`) between the layout PDK and the CML PDK.

## Package features:

- The current plugin supports the following features:
  - Parses a netlist.spi file to convert SPICE to YAML netlist.
  - Filters any non-PDK elements that do not belong the the PDK library (CML). This is done by looking for the 'library=' param in the .MODEL or X_instance.
  - Handles parsing of subcircuits (eg- COMPOUND elements) in the root element circuit
  - Adds pads for each electrical port of each PDK element which is routed.
  - Captures mirrored elements as well as element rotations and transfers them to layout cells.
  - LOG will mention all import messages regarding the parsing process.
  - Outputs YAML netlist as pic.yml files to support the gf file watch flow
    - ROOT element -> TOP.pic.yml
    - COMPOUND element -> COMPOUND_1.pic.yml
  - Running gdsfactory watch.py will update a GDS layout in KLayout based on YAML netlist.
    - KLayout is only used for visualization and pic.yml files can be adjusted to get ideal placements.

### NOTES:

- Multiple PDKs can be supported if user creates a custom combined PDK using gdsfactory and activate the PDK through the mapping file; hence a combined mapping file needs to be created. Multiple mapping files are not supported.
- 'update' mode is currently unsupported. Overwrite mode keeps creating a new TOP.PIC.YAML file and update mode looks for the existing TOP.PIC.YAML file and updates it - so the update mode will be necessary when we integrate electrical routing information and so on.
- Electrical routing is supported. Each electrical port of each PDK element gets its own pad.
- If PDK is missing layout cells that are available in the CML, then this will be logged. The script is currently not going into check which cells are available in the GDSfactory layout PDK.
- It is assumed that the instance names to not have any whitespaces in them (eg – `Si crossing_1` is not correct, but `Si_crossing_1` is correct).
