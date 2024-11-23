import pathlib
from pathlib import Path


def write_tdr_to_csv_2D(
    filename: str = "parse.tcl",
    save_directory: Path | None = None,
    execution_directory: Path | None = None,
    fields_str: str = "eDensity hDensity",
    input_tdr: Path = "in.tdr",
    output_csv: str = "out.csv",
    temp_filename: str = "temp.csv",
    write_utilities: bool = True,
    x_coord: float = 0,
) -> None:
    """Writes a Sentaurus Visual TCL file that can return CSV data from 2D TDR data.

    SVisual will cd into the filename folder, so other files are referenced to it.

    Arguments:
        filename (str): filename of the conversion script
        save_directory: directory where tdr and csv files live
        execution_directory: directory where the script (and hence svisual) is run from
        fields_str (str): whitespace-separated field names to parse
        input_tdr (str): name of the input tdr file
        output_csv (str): name of the output csv file
        temp_filename (str): name of the temporary file
        write_utilities (bool): also write Python utility script
        x_coord: where to define the cutline to read y-values
    """
    save_directory = (
        Path("./sdevice/") if save_directory is None else Path(save_directory)
    )
    execution_directory = (
        Path("./") if execution_directory is None else Path(execution_directory)
    )

    save_directory.relative_to(execution_directory)

    # Setup TCL file
    out_file = pathlib.Path(save_directory / filename)
    save_directory.mkdir(parents=True, exist_ok=True)
    if out_file.exists():
        out_file.unlink()

    filetxt = f"""# Load TDR file.
set mydata2D [load_file {input_tdr!s}]

# Create new plot.
set myplot2D [create_plot -dataset $mydata2D]

# Cutline at origin's x axis to get a list of y values to export
set center1D [create_cutline -plot $myplot2D -type x -at {x_coord}]
set Y_values [ get_variable_data Y -dataset $center1D ]

# Create 1D cutline normal to y-axis at y in Y_values
exec touch {output_csv!s}

foreach y_value $Y_values {{
    set mydata1D [create_cutline -plot $myplot2D -type y -at $y_value]
    export_variables {{ {fields_str} X }} \\ -dataset $mydata1D -filename \"{temp_filename!s}\" -overwrite
    exec python add_column.py \"{temp_filename!s}\" Y $y_value
    exec python merge_data.py \"{temp_filename!s}\" \"{output_csv!s}\" \"{output_csv!s}\"
}}
exec rm \"{temp_filename!s}\"
    """

    with open(out_file, "a") as f:
        f.write(filetxt)

    if write_utilities:
        out_file = pathlib.Path(save_directory / "add_column.py")
        if out_file.exists():
            out_file.unlink()

        filetxt = """import sys

try:
    csv_filename = sys.argv[1]
    extra_label = sys.argv[2]
    extra_value = sys.argv[3]
    lines = []

    with open(csv_filename) as fi:
        for line in fi:
            lines.append(line)

    with open(csv_filename, "w") as fo:
        fo.write(lines[0].strip() + "," + extra_label + "\\n")
        # Skip second line!
        for line in lines[2:]:
            if line.strip() != "":
                fo.write(line.strip() + "," + extra_value + "\\n")

except OSError:
    print("Can't open file for reading/writing.")
    sys.exit(1)
"""

        with open(out_file, "a") as f:
            f.write(filetxt)

        # merge_data.py
        out_file = pathlib.Path(save_directory / "merge_data.py")
        if out_file.exists():
            out_file.unlink()

        filetxt = """import sys

try:
    out_filename = sys.argv[-1]

    all_lines = []
    for csv_filename in sys.argv[1:-1]:
        lines = []
        with open(csv_filename) as fi:
            for line in fi:
                lines.append(line)

        if len(lines) > 0:
            first_line = lines[0]
            all_lines.extend(lines[1:])

    with open(out_filename, "w") as fo:
        fo.write(first_line)
        if len(all_lines) > 1:
            for line in all_lines:
                fo.write(line)

except OSError:
    print("Can't open file for reading/writing.", sys.argv)
    sys.exit(1)
"""

        with open(out_file, "a") as f:
            f.write(filetxt)


if __name__ == "__main__":
    write_tdr_to_csv_2D()
