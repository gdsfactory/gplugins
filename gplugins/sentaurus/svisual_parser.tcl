# Load TDR file.
set mydata2D [load_file n@node|sdevice@_des.tdr]

# Create new plot.
set myplot2D [create_plot -dataset $mydata2D]

# Cutline at origin's x axis to get a list of y values to export
set center1D [create_cutline -plot $myplot2D -type x -at 0]
set Y_values [ get_variable_data Y -dataset $center1D ]

# Create 1D cutline normal to y-axis at y in Y_values
exec touch n@node|sdevice@_des.csv

foreach y_value $Y_values {
    set mydata1D [create_cutline -plot $myplot2D -type y -at $y_value]
    export_variables { eDensity hDensity eMobility hMobility X } \ -dataset $mydata1D -filename "n@node@_tmp_data.csv" -overwrite
    exec python add_column.py "n@node@_tmp_data.csv" Y $y_value
    exec python merge_data.py "n@node@_tmp_data.csv" "n@node|sdevice@_des.csv" "n@node|sdevice@_des.csv"
}
exec rm "n@node@_tmp_data.csv"
