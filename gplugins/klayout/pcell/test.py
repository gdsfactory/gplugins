# Load PCell library
import pcell_example

pcell_example.MyLib()

# Using KLayout
import pya

# Create new layout and top cell
ly = pya.Layout()
topcell = ly.create_cell("top")

# Instantiate PCell
cell = ly.create_cell("Circle", "MyLib", {})
if cell:
    t = pya.Trans.from_s("r0 0,0")
    inst = topcell.insert(pya.CellInstArray(cell.cell_index(), t))
    ly.delete_cell(topcell.cell_index())
else:
    Exception("Cannot import PCell from KLayout library")

# Export layout
save_options = pya.SaveLayoutOptions()
save_options.write_context_info = False  # remove $$$CONTEXT_INFO$$$
ly.write("/tmp/tmp.gds", save_options)

# Using gdsfactory
import gdsfactory as gf

# Load the cell
c = gf.read.import_gds("/tmp/tmp.gds")

# display
# c.plot()

# create example layout
top = gf.Component()
top.name = "Top"
top.add_ref(c).movex(1)
top.add_ref(c).movey(1)
top.plot()

# save
top.write_gds("/tmp/tmp2.gds")
