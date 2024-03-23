import json
import os
import warnings
from copy import deepcopy

import gdsfactory as gf
from jinja2 import Environment, PackageLoader, select_autoescape

from .b64 import load_schemedit_wasm_b64
from .netlist import get_netlist, patch_netlist

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

jinja = Environment(
    loader=PackageLoader("gplugins.gfviz"),
    autoescape=select_autoescape(),
)


def is_notebook() -> bool:
    try:
        shell = get_ipython().__class__.__name__  # type: ignore
        if shell == "ZMQInteractiveShell":
            return True  # Jupyter notebook or qtconsole
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False  # Probably standard Python interpreter


def load_sample_netlist():
    netlist = json.load(open(os.path.join(TEMPLATES_DIR, "example.json")))
    return netlist


def schemedit_html(comp_or_net, height=None, patch=True):
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        if isinstance(comp_or_net, str):
            comp_or_net = gf.get_component(comp_or_net)

        if isinstance(comp_or_net, gf.Component):
            netlist = get_netlist(comp_or_net)
        else:
            netlist = deepcopy(comp_or_net)
        if patch:
            netlist = patch_netlist(netlist)
        if not height:
            height = 0
        height = int(height)
        template = jinja.get_template("index.html")
        schemedit_js = open(os.path.join(STATIC_DIR, "schemedit.js")).read()
        schemedit_b64 = load_schemedit_wasm_b64()
        return template.render(
            netlist=json.dumps(netlist),
            schemedit_js=schemedit_js,
            schemedit_b64=schemedit_b64,
            height=height,
        )


def show(netlist, height=300):
    if not is_notebook():
        raise RuntimeError("gfviz.show only works inside a jupyter notebook!")
    from IPython.display import HTML

    return HTML(schemedit_html(netlist, height=height))
