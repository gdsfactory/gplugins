import pytest
import gdsfactory as gf


from gdsfactory.components import bend_circular, add_frame
from gdsfactory.generic_tech.layer_stack import get_layer_stack
from meshwell.cad import cad
from meshwell.mesh import mesh
from pathlib import Path
from tempfile import TemporaryDirectory
from gplugins.meshwell import (
    get_meshwell_prisms, get_meshwell_cross_section
)
from shapely.geometry import  LineString

@pytest.mark.parametrize("component", [(bend_circular), (add_frame)])
def test_prisms(component) -> None:
    prisms = get_meshwell_prisms(
        component=component(),
        layer_stack=get_layer_stack(sidewall_angle_wg=0),
        name_by="layer",
    )

    with TemporaryDirectory() as tmp_dir:
        xao_file = Path(tmp_dir) / "meshwell_prisms_3D.xao"
        msh_file = Path(tmp_dir) / "meshwell_prisms_3D.msh"
        cad(entities_list=prisms, output_file=xao_file)
        mesh(
            input_file=xao_file,
            output_file=msh_file,
            default_characteristic_length=1000,
            dim=3,
            verbosity=10,
        )


def test_prisms_empty_component() -> None:
    """Test that get_meshwell_prisms handles empty components gracefully."""
    c = gf.Component()
    prisms = get_meshwell_prisms(
        component=c,
        layer_stack=get_layer_stack(sidewall_angle_wg=0),
        name_by="layer",
        wafer_padding=None,
    )
    assert len(prisms) == 0


@pytest.mark.parametrize("component", [(bend_circular), (add_frame)])
def test_cross_section(component) -> None:
    cross_section_line = LineString([(4, -15), (4, 15)])
    surfaces = get_meshwell_cross_section(
        component=component(),
        line=cross_section_line,
        layer_stack=get_layer_stack(sidewall_angle_wg=0),
        name_by="layer",
    )

    with TemporaryDirectory() as tmp_dir:
        xao_file = Path(tmp_dir) / "meshwell_prisms_3D.xao"
        msh_file = Path(tmp_dir) / "meshwell_prisms_3D.msh"
        cad(entities_list=surfaces, output_file=xao_file)
        mesh(
            input_file=xao_file,
            output_file=msh_file,
            default_characteristic_length=1000,
            dim=2,
            verbosity=10,
        )
