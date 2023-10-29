'''
This is an example PCell written in KLayout's Python API

requires KLayout installed via pip:
    pip install klayout


'''


import pya
import math

"""
This sample PCell implements a library called "MyLib" with a single PCell that
draws a circle. It demonstrates the basic implementation techniques for a PCell 
and how to use the "guiding shape" feature to implement a handle for the circle
radius.
"""

class Circle(pya.PCellDeclarationHelper):
  """
  The PCell declaration for the circle
  """

  def __init__(self):

    # Important: initialize the super class
    super(Circle, self).__init__()

    # declare the parameters
    self.param("l", self.TypeLayer, "Layer", default = pya.LayerInfo('1/0'))
    self.param("s", self.TypeShape, "", default = pya.DPoint(0, 0))
    self.param("r", self.TypeDouble, "Radius", default = 0.1)
    self.param("n", self.TypeInt, "Number of points", default = 64)     

  def display_text_impl(self):
    # Provide a descriptive text for the cell
    return "Circle(L=" + str(self.l) + ",R=" + ('%.3f' % self.r) + ")"
    
  def produce_impl(self):
  
    # This is the main part of the implementation: create the layout

    # compute the circle
    da = math.pi * 2 / self.n
    pts = [ pya.DPoint(self.r * math.cos(i * da), self.r * math.sin(i * da)) for i in range(0, self.n) ]
    
    # create the shape
    self.cell.shapes(self.l_layer).insert(pya.DPolygon(pts))


class MyLib(pya.Library):
  """
  The library where we will put the PCell into 
  """

  def __init__(self):
  
    # Set the description
    self.description = "My First Library"
    
    # Create the PCell declarations
    self.layout().register_pcell("Circle", Circle())
    # That would be the place to put in more PCells ...
    
    # Register us with the name "MyLib".
    # If a library with that name already existed, it will be replaced then.
    self.register("MyLib")


# Instantiate and register the library
MyLib()

