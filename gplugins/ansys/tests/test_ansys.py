"""Tests for the Ansys AEDT wrappers, against PyAEDT stand-ins."""

from collections.abc import Generator, Sequence
from pathlib import Path

import gdsfactory as gf
import polars as pl
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
from gplugins.ansys.base import (
    _first_real_value,
    _get_layer_number_from_level,
    logger,
    rename_imported_objects,
)
from gplugins.ansys.tests._mocks import (
    MockApp,
    MockDrivenPost,
    MockExpressionData,
    MockHfssApp,
    MockHfssDrivenApp,
    MockHfssImportApp,
    MockLogger,
    MockMaterials,
    MockModeler,
    MockPost,
    MockQ2dApp,
    MockQ3dApp,
    MockQ3dGeometryApp,
    MockQ3dNetsApp,
    MockSParameterSolution,
    MockStubbornObject,
)

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


@pytest.fixture
def warnings() -> Generator[list[str], None, None]:
    """Collect the plugin's warning messages."""
    messages: list[str] = []
    handler_id = logger.add(messages.append, level="WARNING")
    try:
        yield messages
    finally:
        logger.remove(handler_id)


def _ports(*specs: tuple[str, tuple[float, float], float]) -> list:
    """Return gdsfactory ports with the given names, centers and orientations."""
    c = gf.Component()
    for name, center, orientation in specs:
        c.add_port(name, center=center, width=1.0, orientation=orientation, layer=METAL)
    return list(c.ports)


def test_assign_nets_from_ports_with_a_port_at_the_origin():
    """A port at (0, 0) must not skew which conductor the other ports land on."""
    app = MockQ3dGeometryApp(
        {
            "near": [0.0, -5.0, 0.0, 10.0, 5.0, 0.2],
            "mid": [310.0, -5.0, 0.0, 320.0, 5.0, 0.2],
            "far": [1000.0, -5.0, 0.0, 1010.0, 5.0, 0.2],
        }
    )
    ports = _ports(("o1", (0, 0), 180), ("o2", (300, 0), 0))

    nets = Q3D(app).assign_nets_from_ports(ports, ["near", "mid", "far"])

    assert nets == ["o1", "o2"]
    owners = {b.name: b.props["Objects"] for b in app.boundaries}
    assert owners["o1"] == ["near"]
    assert owners["o2"] == ["mid"]


def test_assign_nets_from_ports_converts_model_units():
    """Bounding boxes in mm are compared with ports in µm after conversion."""
    app = MockQ3dGeometryApp(
        {
            "a": [0.0, -0.005, 0.0, 0.01, 0.005, 0.0002],
            "b": [0.31, -0.005, 0.0, 0.32, 0.005, 0.0002],
        },
        units="mm",
    )
    ports = _ports(("o1", (0, 0), 180), ("o2", (320, 0), 0))

    Q3D(app).assign_nets_from_ports(ports, ["a", "b"])

    owners = {b.name: b.props["Objects"] for b in app.boundaries}
    assert owners["o1"] == ["a"]
    assert owners["o2"] == ["b"]


def test_assign_nets_from_ports_prefers_the_inner_conductor(warnings: list[str]):
    """Both ends of a line enclosed by a ground plane name the line, once."""
    app = MockQ3dGeometryApp(
        {
            "ground": [-100.0, -100.0, 0.0, 400.0, 100.0, 0.2],
            "signal": [0.0, -5.0, 0.0, 300.0, 5.0, 0.2],
        }
    )
    ports = _ports(("o1", (0, 0), 180), ("o2", (300, 0), 0))

    nets = Q3D(app).assign_nets_from_ports(ports, ["ground", "signal"])

    assert nets == ["o1"]
    owners = {b.name: b.props["Objects"] for b in app.boundaries}
    assert owners["o1"] == ["signal"]
    assert owners["Net_ground"] == ["ground"]
    assert any("'o2'" in message for message in warnings)


@pytest.mark.parametrize(
    ("units", "port_center", "match"),
    [("furlong", (0, 0), "Unknown model length unit"), ("um", (5000, 0), "outside")],
)
def test_assign_nets_from_ports_rejects_mismatched_geometry(units, port_center, match):
    """Unknown units, or a port nowhere near the conductors, fail loudly."""
    app = MockQ3dGeometryApp({"a": [0.0, -5.0, 0.0, 10.0, 5.0, 0.2]}, units=units)

    with pytest.raises(ValueError, match=match):
        Q3D(app).assign_nets_from_ports(_ports(("o1", port_center, 0)), ["a"])


def test_get_sparameter_results_returns_complex_s_not_db():
    """S-parameters are read as S(i,j) real and imaginary parts, not dB."""
    sweep = [1.0, 2.0, 3.0]
    s11 = [0.1 + 0.2j, 0.3 - 0.1j, -0.5 + 0.0j]
    s21 = [0.9 + 0.0j, 0.8 + 0.1j, 0.7 - 0.2j]
    post = MockDrivenPost(
        {
            "S(1,1)": MockSParameterSolution("S(1,1)", sweep, s11),
            "S(2,1)": MockSParameterSolution("S(2,1)", sweep, s21),
        }
    )
    app = MockHfssDrivenApp(post)

    df = HFSS(app).get_sparameter_results("DrivenSetup", "FrequencySweep")

    assert app.trace_categories == ["S"]
    assert df.columns == [
        "frequency_ghz",
        "re(S(1,1))",
        "im(S(1,1))",
        "re(S(2,1))",
        "im(S(2,1))",
    ]
    assert all(dtype == pl.Float64 for dtype in df.dtypes)
    assert_allclose(df["frequency_ghz"].to_numpy(), sweep)
    rebuilt = df["re(S(2,1))"].to_numpy() + 1j * df["im(S(2,1))"].to_numpy()
    assert_allclose(rebuilt, s21)
    assert post.requests[0][1]["setup_sweep_name"] == "DrivenSetup : FrequencySweep"


def test_get_sparameter_results_converts_the_sweep_unit():
    """A sweep AEDT reports in MHz comes back in GHz."""
    post = MockDrivenPost(
        {"S(1,1)": MockSParameterSolution("S(1,1)", [500.0], [0.5j], "MHz")}
    )

    df = HFSS(MockHfssDrivenApp(post)).get_sparameter_results()

    assert df["frequency_ghz"].to_list() == pytest.approx([0.5])


@pytest.mark.parametrize("import_as_sheets", [False, True])
def test_hfss_import_assigns_dielectric_materials(
    tmp_path: Path, stack: LayerStack, import_as_sheets: bool
):
    """Dielectric levels get their material, which is added to the project first.

    Sheets flatten only the conductors; the substrate keeps its thickness.
    """
    component = gf.components.rectangle(size=(10, 10), layer=METAL)
    app = MockHfssImportApp(["signal1", "signal99"])

    HFSS(app).import_component(
        component,
        stack,
        import_as_sheets=import_as_sheets,
        gds_path=tmp_path / "comp.gds",
    )

    assert app.assigned_materials == {"Substrate": "si"}
    assert "si" in app.materials.material_names
    assert app.import_kwargs["mapping_layers"][99] == (-500.0, 500.0)


def test_hfss_import_raises_when_the_import_fails(tmp_path: Path, stack: LayerStack):
    """A failed GDS import raises, as in Q3D, instead of returning False."""
    app = MockHfssImportApp(["signal1"])
    app.import_gds_3d = lambda **kwargs: False

    with pytest.raises(RuntimeError, match="HFSS GDS import failed"):
        HFSS(app).import_component(
            gf.components.rectangle(size=(10, 10), layer=METAL),
            stack,
            gds_path=tmp_path / "comp.gds",
        )


@pytest.mark.parametrize("wrapper", [HFSS, Q3D])
def test_import_rejects_units_other_than_um(wrapper, stack: LayerStack):
    """The layer stack is in µm, so other geometry units would mis-scale it."""
    with pytest.raises(ValueError, match="units='um'"):
        wrapper(MockHfssImportApp([])).import_component(
            gf.components.rectangle(size=(10, 10), layer=METAL), stack, units="mm"
        )


def test_layer_stack_to_gds_mapping_override_materials(stack: LayerStack):
    """The thickness override can be limited to some materials."""
    mapping = layer_stack_to_gds_mapping(
        stack, thickness_override=0.0, override_materials={"Nb"}
    )

    assert mapping[1] == (0.0, 0.0)
    assert mapping[99] == (-500.0, 500.0)


def test_layer_stack_to_gds_mapping_warns_on_an_unresolvable_level(
    warnings: list[str],
):
    """A level without a GDS layer number is reported, not silently dropped."""
    level = _level(METAL, 0.0, 0.2, "Nb")
    stack = LayerStack(layers={"M1": level, "Mystery": _level(METAL, 1.0, 0.2, "Nb")})
    stack.layers["Mystery"].layer = None

    mapping = layer_stack_to_gds_mapping(stack)

    assert mapping == {1: (0.0, 0.2)}
    assert any("'Mystery'" in message for message in warnings)


def test_add_lumped_ports_draws_a_port_per_gdsfactory_port():
    """Each port gets a sheet at the conductor's elevation and a lumped port."""
    app = MockHfssApp()
    ports = _ports(("o1", (0, 0), 180), ("o2", (300, 0), 0))

    HFSS(app).add_lumped_ports(ports, cpw_gap=6.0, cpw_width=10.0, elevation=0.2)

    assert [r.name for r in app.modeler.rectangles] == ["o1_face", "o2_face"]
    assert app.modeler.rectangles[0].kwargs["origin"] == pytest.approx(
        [-6.0, -5.0, 0.2]
    )
    assert [p["name"] for p in app.lumped_ports] == ["o1", "o2"]
    assert app.lumped_ports[1]["assignment"] == "o2_face"


def test_add_lumped_ports_rejects_a_port_without_orientation():
    """An electrical port without orientation names itself in the error."""

    class Port:
        name = "e1"
        center = (0.0, 0.0)
        orientation = None

    with pytest.raises(ValueError, match="Port 'e1': Port has no orientation"):
        HFSS(MockHfssApp()).add_lumped_ports([Port()], cpw_gap=6.0, cpw_width=10.0)


def test_add_air_region_adds_a_lateral_margin():
    """The air box clears the component by the margin on every side."""
    app = MockHfssApp()
    component = gf.components.rectangle(size=(100, 50), layer=METAL)

    name = HFSS(app).add_air_region(
        component, height=200.0, substrate_thickness=300.0, lateral_margin=25.0
    )

    box = app.modeler.boxes[0]
    assert name == box.name == "AirRegion"
    assert box.kwargs["origin"] == pytest.approx([-25.0, -25.0, -300.0])
    assert box.kwargs["sizes"] == pytest.approx([150.0, 100.0, 500.0])
    assert app.perfect_e == {}

    with pytest.raises(ValueError, match="lateral_margin"):
        HFSS(app).add_air_region(component, lateral_margin=-1.0)


def test_add_substrate_adds_its_material_to_the_project():
    """The substrate's material exists in the project before the box uses it."""
    app = MockHfssApp()
    component = gf.components.rectangle(size=(100, 50), layer=METAL)

    HFSS(app).add_substrate(component, thickness=500.0, material="silicon")

    assert "silicon" in app.materials.material_names
    assert app.modeler.boxes[0].kwargs["material"] == "silicon"


def test_get_capacitance_matrix_rejects_an_unknown_unit():
    """A unit the converter does not know raises instead of assuming pF."""
    post = MockPost({"Capacitance": {"C(o1,o1)": 8.77}}, unit="zF")

    with pytest.raises(ValueError, match="Unknown capacitance unit 'zF'"):
        Q3D(MockQ3dNetsApp(post, ["o1"])).get_capacitance_matrix("Q3DSetup")


def test_get_capacitance_matrix_reads_attofarads():
    """Q3D reports small couplings in aF."""
    post = MockPost({"Capacitance": {"C(o1,o1)": 5.0}}, unit="aF")

    matrix = Q3D(MockQ3dNetsApp(post, ["o1"])).get_capacitance_matrix("Q3DSetup")

    assert matrix.item(0, "C(o1,o1)") == pytest.approx(5e-18)


def test_rename_imported_objects_names_objects_after_their_level(stack: LayerStack):
    """signal<N> objects take the lowest non-vacuum level's name on that number."""
    app = MockApp(non_graphical=True)
    app.modeler = MockModeler(["signal1", "signal99_1", "other"])

    renamed = rename_imported_objects(app, ["signal1", "signal99_1", "other"], stack)

    assert renamed == ["M1", "Substrate_1", "other"]


def test_rename_imported_objects_keeps_a_refused_name(stack: LayerStack):
    """When AEDT refuses a rename, the object keeps its old name."""
    app = MockApp(non_graphical=True)
    app.modeler = MockModeler([])
    app.modeler._objects["signal1"] = MockStubbornObject("signal1")

    assert rename_imported_objects(app, ["signal1"], stack) == ["signal1"]


def test_rename_imported_objects_propagates_aedt_errors(stack: LayerStack):
    """An error from AEDT, e.g. a dead session, is not swallowed."""

    class BrokenObject:
        @property
        def name(self) -> str:
            return "signal1"

        @name.setter
        def name(self, value: str) -> None:
            raise RuntimeError("gRPC session closed")

    app = MockApp(non_graphical=True)
    app.modeler = MockModeler([])
    app.modeler._objects["signal1"] = BrokenObject()

    with pytest.raises(RuntimeError, match="gRPC"):
        rename_imported_objects(app, ["signal1"], stack)
