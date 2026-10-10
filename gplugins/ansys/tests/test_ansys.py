"""Tests for the Ansys AEDT wrappers, against PyAEDT stand-ins."""

from collections.abc import Sequence
from pathlib import Path

import gdsfactory as gf
import pytest
from gdsfactory.gpdk import PDK
from gdsfactory.technology import LayerLevel, LayerStack
from numpy.testing import assert_allclose

from gplugins.ansys import (
    DEFAULT_MATERIAL_PROPERTIES,
    HFSS,
    Q2D,
    Q3D,
    add_materials_to_aedt,
    detach_desktop_logging,
    export_component_to_gds_temp,
    fit_view,
    layer_stack_to_gds_mapping,
    lumped_port_rectangle_from_cpw,
    object_names_to_materials,
)
from gplugins.ansys._mocks import (
    MockApp,
    MockExpressionData,
    MockHfssApp,
    MockHfssImportApp,
    MockLogger,
    MockMaterials,
    MockPost,
    MockQ2dApp,
    MockQ3dApp,
    MockQ3dNetsApp,
)
from gplugins.ansys.base import _first_real_value, _get_layer_number_from_level, logger

PDK.activate()

METAL = (1, 0)
AIRBRIDGE = (10, 0)
AIRBRIDGE_VIA = (10, 1)
SIM_AREA = (99, 0)


def _level(layer: tuple[int, int], zmin: float, thickness: float, material: str):
    return LayerLevel(layer=layer, zmin=zmin, thickness=thickness, material=material)


@pytest.fixture
def stack() -> LayerStack:
    """A superconducting stack exercising the import-mapping edge cases."""
    return LayerStack(
        layers={
            "Substrate": _level(SIM_AREA, -500.0, 500.0, "si"),
            "Vacuum": _level(SIM_AREA, 0.0, 500.0, "vacuum"),
            "M1": _level(METAL, 0.0, 0.2, "Nb"),
            "Airbridge": _level(AIRBRIDGE, 0.3, 0.2, "Nb"),
            "Airbridge_Via": _level(AIRBRIDGE_VIA, 0.2, 0.1, "Nb"),
        }
    )


def test_layer_stack_to_gds_mapping(stack: LayerStack):
    """Every non-vacuum level maps once, with joinable spans merged."""
    mapping = layer_stack_to_gds_mapping(stack)

    # Vacuum shares the substrate's layer and is skipped, so the substrate keeps it
    assert mapping[99] == pytest.approx((-500.0, 500.0))
    assert mapping[1] == pytest.approx((0.0, 0.2))
    # Airbridge (0.3-0.5 um) and its via (0.2-0.3 um) merge to one box
    assert mapping[10] == pytest.approx((0.2, 0.3))
    assert set(mapping) == {1, 10, 99}

    # Sheets mode keeps the lowest elevation for colliding levels
    sheets = layer_stack_to_gds_mapping(stack, thickness_override=0.0)
    assert sheets[10] == pytest.approx((0.2, 0.0))
    assert sheets[99] == pytest.approx((-500.0, 0.0))


def test_layer_stack_to_gds_mapping_defaults_to_the_active_pdk():
    """Without a stack the active PDK's is used.

    The generic PDK draws substrate (si) and box (sio2) on the same wafer layer,
    which AEDT's importer cannot tell apart, so the mapping refuses it.
    """
    with pytest.raises(ValueError, match="different materials"):
        layer_stack_to_gds_mapping()


def test_layer_stack_to_gds_mapping_unmergeable_collision_raises():
    """Unmergeable layer-number collisions raise a clear error."""
    gap = LayerStack(
        layers={
            "A": _level((7, 0), 0.0, 1.0, "Nb"),
            "B": _level((7, 1), 5.0, 1.0, "Nb"),
        }
    )
    with pytest.raises(ValueError, match="do not join into a single box"):
        layer_stack_to_gds_mapping(gap)

    mixed = LayerStack(
        layers={
            "A": _level((7, 0), 0.0, 1.0, "Nb"),
            "C": _level((7, 1), 1.0, 1.0, "sio2"),
        }
    )
    with pytest.raises(ValueError, match="different materials"):
        layer_stack_to_gds_mapping(mixed)
    # Sheets mode would still import both as one object with a single material
    with pytest.raises(ValueError, match="different materials"):
        layer_stack_to_gds_mapping(mixed, thickness_override=0.0)


def test_layer_stack_to_gds_mapping_order_independent():
    """Merged spans do not depend on layer stack insertion order."""

    def make_stack(names: Sequence[str]) -> LayerStack:
        spans = {"A": (0.0, 1.0), "B": (1.0, 3.0), "C": (3.0, 4.0)}
        return LayerStack(
            layers={
                name: _level(
                    (7, index), spans[name][0], spans[name][1] - spans[name][0], "Nb"
                )
                for index, name in enumerate(names)
            }
        )

    expected = layer_stack_to_gds_mapping(make_stack(("A", "B", "C")))
    assert expected[7] == pytest.approx((0.0, 4.0))
    assert layer_stack_to_gds_mapping(make_stack(("A", "C", "B"))) == expected
    assert layer_stack_to_gds_mapping(make_stack(("C", "B", "A"))) == expected


def test_get_layer_number_from_level():
    """Layer numbers resolve from plain and derived layer definitions."""

    class MockLevelTuple:
        layer = (1, 0)

    assert _get_layer_number_from_level(MockLevelTuple()) == 1

    class MockLogicalLayerInner:
        layer = (2, 0)

    class MockLogicalLayer:
        layer = MockLogicalLayerInner()

    class MockDerivedLevel:
        layer = None
        derived_layer = MockLogicalLayer()

    assert _get_layer_number_from_level(MockDerivedLevel()) == 2


def test_object_names_to_materials(stack: LayerStack):
    """Metals map to pec, dielectrics keep their material, unknowns fail closed."""
    result = object_names_to_materials(
        ["signal1", "signal99", "Substrate", "M1_offset", "Airbridge_Via_1"], stack
    )

    assert result == {
        "signal1": "pec",
        "signal99": "si",
        "Substrate": "si",
        "M1_offset": "pec",
        "Airbridge_Via_1": "pec",
    }

    with pytest.raises(ValueError, match="Could not resolve"):
        object_names_to_materials(["signal7", "unknown_object"], stack)


def test_object_names_to_materials_unregistered_material():
    """Levels with materials missing from the table fail closed."""
    stack = LayerStack(layers={"Custom": _level((50, 0), 0.0, 1.0, "unobtainium")})

    with pytest.raises(ValueError, match="not registered in material_properties"):
        object_names_to_materials(["signal50"], stack)

    # A table that knows the material resolves it
    table = {"unobtainium": {"relative_permittivity": 42.0}}
    assert object_names_to_materials(["signal50"], stack, table) == {
        "signal50": "unobtainium"
    }


def test_add_materials_to_aedt_adds_only_missing_materials():
    """Existing project materials are kept; metals get a huge conductivity."""

    class App:
        materials = MockMaterials()

    app = App()
    app.materials.material_names.append("si")
    added = {}
    original = app.materials.add_material

    def record(name):
        added[name] = original(name)
        return added[name]

    app.materials.add_material = record
    add_materials_to_aedt(
        app,
        {
            "si": {"relative_permittivity": 11.7},
            "sapphire": {"relative_permittivity": 9.4, "conductivity": 0.0},
            "Nb": {"relative_permittivity": float("inf")},
        },
    )

    assert set(added) == {"sapphire", "Nb"}
    assert added["sapphire"].permittivity == 9.4
    assert added["sapphire"].conductivity == 0.0
    assert added["Nb"].permittivity is None
    assert added["Nb"].conductivity == 1e30


def test_default_material_properties_cover_the_generic_pdk():
    """Every material in the generic PDK's stack has a default entry."""
    stack = gf.get_active_pdk().layer_stack
    materials = {level.material for level in stack.layers.values()}

    assert materials <= set(DEFAULT_MATERIAL_PROPERTIES)


def test_q3d_import_assigns_materials_from_layer_stack(
    tmp_path: Path, stack: LayerStack
):
    """Q3D import must not blanket-assign pec: the substrate gets its own material."""
    component = gf.components.rectangle(size=(10, 10), layer=METAL)
    app = MockQ3dApp(["signal1", "signal99"])
    sim = Q3D(app, layer_stack=stack)

    conductors = sim.import_component(component, gds_path=tmp_path / "comp.gds")

    # Only conductor objects are returned for downstream net assignment
    assert conductors == ["M1"]
    assert app.assigned_materials == {"M1": "pec", "Substrate": "si"}
    assert app.import_kwargs["mapping_layers"] == layer_stack_to_gds_mapping(stack)
    assert "si" in app.materials.material_names


@pytest.mark.parametrize(
    ("import_as_sheets", "boundary"), [(False, "PEC_3D"), (True, "PEC_Sheets")]
)
def test_hfss_import_assigns_perfect_e_to_metals_only(
    tmp_path: Path, stack: LayerStack, import_as_sheets: bool, boundary: str
):
    """PerfectE is a conductor boundary, so the substrate must not get it."""
    component = gf.components.rectangle(size=(10, 10), layer=METAL)
    app = MockHfssImportApp(["signal1", "signal99"])

    assert HFSS(app).import_component(
        component,
        stack,
        import_as_sheets=import_as_sheets,
        gds_path=tmp_path / "comp.gds",
    )

    assert app.perfect_e == {boundary: ["M1"]}
    thickness = app.import_kwargs["mapping_layers"][1][1]
    assert thickness == (0.0 if import_as_sheets else pytest.approx(0.2))


def test_fit_view_skips_a_non_graphical_session():
    """Fitting the view is a screen operation, so a headless session must not try."""
    graphical = MockApp(non_graphical=False)
    headless = MockApp(non_graphical=True)

    fit_view(graphical)
    fit_view(headless)

    assert graphical.modeler.fit_all_calls == 1
    assert headless.modeler.fit_all_calls == 0


def test_detach_desktop_logging_drops_the_desktop_reference():
    """PyAEDT's logger reads the desktop on every message unless it is dropped."""
    app = MockApp(non_graphical=True)
    assert app.logger._desktop_class is app.desktop_class

    detach_desktop_logging(app)

    assert app.logger._desktop_class is None


def test_detach_desktop_logging_tolerates_a_renamed_attribute():
    """A PyAEDT that renamed the attribute must not get a dead one instead."""
    app = MockApp(non_graphical=True)
    app.logger = MockLogger()

    messages = []
    handler_id = logger.add(messages.append, level="WARNING")
    try:
        detach_desktop_logging(app)
    finally:
        logger.remove(handler_id)

    assert not hasattr(app.logger, "_desktop_class")
    assert any("_desktop_class" in str(message) for message in messages)


@pytest.mark.parametrize("keep_file", [True, False])
def test_export_component_to_gds_temp_writes_no_context_info(
    tmp_path: Path, keep_file: bool
):
    """AEDT's importer fails on the context info gdsfactory writes by default."""
    component = gf.components.rectangle(size=(10, 10), layer=METAL)
    gds_path = tmp_path / "component.gds" if keep_file else None

    with export_component_to_gds_temp(component, gds_path) as path:
        layout = gf.kdb.Layout()
        layout.read(str(path))
        context_info = [info.name for info in layout.each_meta_info()]

    assert not any(name.startswith("kfactory:") for name in context_info)

    # The flag is what leaves the info out: the same component written by hand
    # carries it.
    with_context_info = tmp_path / "with_context_info.gds"
    component.write_gds(str(with_context_info), with_metadata=True)
    layout = gf.kdb.Layout()
    layout.read(str(with_context_info))

    assert any(info.name.startswith("kfactory:") for info in layout.each_meta_info())


def test_get_eigenmode_results_reads_real_values():
    """The readback uses get_expression_data, not the removed data_real."""
    post = MockPost(
        {
            "Eigen Modes": {"Mode 1": 4.8389e9},
            "Eigen Q": {"Q(Mode 1)": 1234.5},
        }
    )
    sim = HFSS(MockHfssApp(post))

    results = sim.get_eigenmode_results("EigenmodeSetup")

    assert results["frequencies"] == pytest.approx([4.8389])
    assert results["q_factors"] == pytest.approx([1234.5])
    assert results["setup"] == "EigenmodeSetup"
    assert [solution.calls for solution in post.solutions] == [[(None, "real")]] * 2


@pytest.mark.parametrize(
    "returned",
    [(None, None), ([], []), ([0.0], [])],
    ids=["no-rows", "empty-arrays", "empty-values"],
)
def test_first_real_value_returns_none_without_data(returned):
    """An expression with no data reads as None, whatever shape PyAEDT returns."""
    solution = MockExpressionData(returned)

    assert _first_real_value(solution) is None
    assert solution.calls == [{"formula": "real"}]


def test_first_real_value_reads_the_first_value():
    """Real data comes back as a sweep and its values; the value is what counts."""
    solution = MockExpressionData(([1.0, 2.0], [4.5, 5.5]))

    assert _first_real_value(solution) == pytest.approx(4.5)


def test_get_eigenmode_results_skips_a_quantity_without_samples():
    """A quantity AEDT has no samples for is left out, not indexed into."""
    post = MockPost(
        {
            "Eigen Modes": {"Mode 1": 4.8389e9, "Mode 2": None},
            "Eigen Q": {"Q(Mode 1)": None},
        }
    )
    results = HFSS(MockHfssApp(post)).get_eigenmode_results("EigenmodeSetup")

    assert results["frequencies"] == pytest.approx([4.8389])
    assert results["q_factors"] == []


def test_get_eigenmode_results_handles_an_unsolved_setup():
    """An unsolved setup returns False from get_solution_data, not an empty solution."""
    post = MockPost(
        {"Eigen Modes": {"Mode 1": 4.8389e9}, "Eigen Q": {"Q(Mode 1)": 1234.5}},
        solved=False,
    )
    results = HFSS(MockHfssApp(post)).get_eigenmode_results("EigenmodeSetup")

    assert results["frequencies"] == []
    assert results["q_factors"] == []


def test_get_capacitance_matrix_converts_the_reported_unit():
    """Q3D reports the matrix in pF or fF, and the values must come back in farads."""
    post = MockPost(
        {"Capacitance": {"C(o1,o1)": 8.77, "C(o1,o2)": 1.23, "C(o2,o2)": 4.0}},
        unit="fF",
    )
    matrix = Q3D(MockQ3dNetsApp(post, ["o1", "o2"])).get_capacitance_matrix("Q3DSetup")

    assert matrix.columns == ["C(o1,o1)", "C(o1,o2)", "C(o2,o2)"]
    assert matrix.item(0, "C(o1,o1)") == pytest.approx(8.77e-15)
    assert matrix.item(0, "C(o1,o2)") == pytest.approx(1.23e-15)
    assert [solution.calls for solution in post.solutions] == [[(None, "real")]] * 3


def test_get_capacitance_matrix_skips_an_expression_without_samples():
    """An expression AEDT has no samples for is left out, not indexed into."""
    post = MockPost(
        {"Capacitance": {"C(o1,o1)": 8.77, "C(o1,o2)": None, "C(o2,o2)": 4.0}},
        unit="fF",
    )
    matrix = Q3D(MockQ3dNetsApp(post, ["o1", "o2"])).get_capacitance_matrix("Q3DSetup")

    assert matrix.columns == ["C(o1,o1)", "C(o2,o2)"]


@pytest.mark.parametrize(
    ("orientation", "expected_origin", "expected_sizes", "expected_int_line"),
    [
        (0, [10.0, 19.0, 0.0], [6.0, 2.0], [[16.0, 20.0, 0.0], [10.0, 20.0, 0.0]]),
        (90, [9.0, 20.0, 0.0], [2.0, 6.0], [[10.0, 26.0, 0.0], [10.0, 20.0, 0.0]]),
        (180, [4.0, 19.0, 0.0], [6.0, 2.0], [[4.0, 20.0, 0.0], [10.0, 20.0, 0.0]]),
        (270, [9.0, 14.0, 0.0], [2.0, 6.0], [[10.0, 14.0, 0.0], [10.0, 20.0, 0.0]]),
    ],
)
def test_lumped_port_rectangle_from_cpw_valid_angles(
    orientation, expected_origin, expected_sizes, expected_int_line
):
    """The port rectangle sits in the gap, oriented along the port."""
    result = lumped_port_rectangle_from_cpw(
        center=(10.0, 20.0, 0.0), orientation=orientation, cpw_gap=6.0, cpw_width=2.0
    )

    assert_allclose(result["origin"], expected_origin)
    assert_allclose(result["sizes"], expected_sizes)
    assert_allclose(result["integration_line"], expected_int_line)


def test_lumped_port_rectangle_from_cpw_invalid_angle():
    """An off-axis port has no lumped port rectangle."""
    with pytest.raises(ValueError, match="Unsupported port orientation: 45°"):
        lumped_port_rectangle_from_cpw(
            center=(10.0, 20.0, 0.0), orientation=45, cpw_gap=6.0, cpw_width=2.0
        )


def test_q2d_create_2d_cpw_draws_the_cross_section(stack: LayerStack):
    """Signal and grounds sit side by side on the substrate, gaps between them."""
    app = MockQ2dApp()
    q2d = Q2D(app, layer_stack=stack)

    names = q2d.create_2d_cpw(
        10.0, 6.0, substrate_level="Substrate", conductor_level="M1"
    )

    rectangles = app.modeler.rectangles
    assert names == {n: n for n in ("signal", "gnd_left", "gnd_right", "substrate")}
    # Ground width defaults to 10x the gap
    assert rectangles["gnd_left"].origin == [0, 0, 0]
    assert rectangles["gnd_left"].sizes == [60.0, 2.0]
    assert rectangles["signal"].origin == [66.0, 0, 0]
    assert rectangles["gnd_right"].origin == [82.0, 0, 0]
    # The 0.2 um film is thickened to 2 um for Q2D stability
    assert rectangles["signal"].sizes == [10.0, 2.0]
    assert rectangles["signal"].material == "Nb"
    assert rectangles["substrate"].material == "si"
    assert rectangles["substrate"].sizes == [142.0 + 100.0, 500.0]
    assert app.conductors["signal"]["conductor_type"] == "SignalLine"
    assert app.conductors["gnd"]["conductor_type"] == "ReferenceGround"
    assert app.modeler.model_units == "um"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"units": "mm"}, "units='um'"),
        ({"conductor_level": "M9"}, "no level 'M9'"),
        ({"cpw_gap": 0.0}, "must be positive"),
    ],
)
def test_q2d_create_2d_cpw_rejects_bad_input(stack: LayerStack, kwargs, match):
    """Bad dimensions, units, or level names fail before anything is drawn."""
    app = MockQ2dApp()
    arguments = {
        "cpw_width": 10.0,
        "cpw_gap": 6.0,
        "substrate_level": "Substrate",
        "conductor_level": "M1",
    } | kwargs

    with pytest.raises(ValueError, match=match):
        Q2D(app, layer_stack=stack).create_2d_cpw(**arguments)

    assert app.modeler.rectangles == {}
