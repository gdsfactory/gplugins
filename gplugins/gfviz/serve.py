from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from gplugins.gfviz.gfviz import load_sample_netlist, schemedit_html

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def index(height=None):
    netlist = load_sample_netlist()
    return schemedit_html(netlist, height=height)
