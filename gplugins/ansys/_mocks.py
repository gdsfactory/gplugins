"""Minimal stand-ins for PyAEDT objects, so the wrappers test without AEDT."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MockAEDTObject:
    """Minimal stand-in for a PyAEDT modeler object."""

    name: str


class MockModeler:
    """Minimal stand-in for a PyAEDT modeler."""

    def __init__(self, object_names: list[str]):
        """Initialize with the names of objects created by the GDS import."""
        self.object_names = list(object_names)
        self._objects = {name: MockAEDTObject(name) for name in object_names}
        self.fit_all_calls = 0

    def __getitem__(self, name: str) -> MockAEDTObject:
        """Return the modeler object with the given name."""
        return self._objects[name]

    def fit_all(self) -> None:
        """Count a view-fitting call, which a headless session must not make."""
        self.fit_all_calls += 1


@dataclass
class MockMaterial:
    """Minimal stand-in for a PyAEDT material."""

    permittivity: float | None = None
    conductivity: float | None = None


class MockMaterials:
    """Minimal stand-in for a PyAEDT materials manager."""

    def __init__(self) -> None:
        """Initialize an empty materials database."""
        self.material_names: list[str] = []

    def exists_material(self, name: str) -> bool:
        """Return whether the material exists in the project."""
        return name in self.material_names

    def add_material(self, name: str) -> MockMaterial:
        """Add a material to the project."""
        self.material_names.append(name)
        return MockMaterial()


class MockQ3dApp:
    """Minimal stand-in for a PyAEDT Q3d application."""

    def __init__(self, object_names: list[str]):
        """Initialize with the names of objects created by the GDS import."""
        self.imported_object_names = list(object_names)
        self.modeler = MockModeler([])
        self.materials = MockMaterials()
        self.assigned_materials: dict[str, str] = {}

    def import_gds_3d(self, **kwargs: object) -> bool:
        """Simulate a successful 3D GDS import creating the objects."""
        self.import_kwargs = kwargs
        self.modeler.object_names.extend(self.imported_object_names)
        for name in self.imported_object_names:
            self.modeler._objects[name] = MockAEDTObject(name)
        return True

    def assign_material(self, assignment: list, material: str) -> None:
        for obj in assignment:
            self.assigned_materials[str(obj)] = material


class MockDesktop:
    """Minimal stand-in for a PyAEDT desktop."""

    def __init__(self, non_graphical: bool) -> None:
        """Initialize with the mode the session was constructed in."""
        self.non_graphical = non_graphical


class MockLogger:
    """Minimal stand-in for PyAEDT's logger, which holds the desktop it logs through."""

    def __init__(self, desktop: MockDesktop | None = None) -> None:
        """Initialize holding a desktop, as a real logger does."""
        if desktop is not None:
            self._desktop_class = desktop


class MockApp:
    """Minimal stand-in for a PyAEDT application, for the session helpers."""

    def __init__(self, non_graphical: bool) -> None:
        """Initialize an application with a modeler, a desktop and a logger."""
        self.desktop_class = MockDesktop(non_graphical)
        self.modeler = MockModeler([])
        self.logger = MockLogger(self.desktop_class)


class MockSolutionData:
    """Minimal stand-in for a PyAEDT SolutionData built for one expression."""

    def __init__(self, expression: str, values: list[float], unit: str = "pF") -> None:
        """Initialize with the values that expression should read back as."""
        self.expressions = [expression]
        self.units_data = {expression: unit}
        self.calls: list[tuple[str | None, str | None]] = []
        self._values = values

    def get_expression_data(
        self, expression: str | None = None, formula: str | None = None
    ) -> tuple[list[float], list[float]]:
        """Return the canned values, recording how the caller asked for them."""
        self.calls.append((expression, formula))
        return [0.0], self._values


class MockExpressionData:
    """SolutionData stand-in whose real data is whatever the test hands it."""

    def __init__(self, returned: tuple | None) -> None:
        """Initialize with the pair get_expression_data should answer with."""
        self.returned = returned
        self.calls: list[dict] = []

    def get_expression_data(self, **kwargs):
        """Return the canned pair, recording how the caller asked for it."""
        self.calls.append(kwargs)
        return self.returned


class MockPost:
    """Minimal stand-in for a PyAEDT post processor returning canned results."""

    def __init__(
        self,
        quantities: dict[str, dict[str, float | None]],
        unit: str = "pF",
        solved: bool = True,
    ) -> None:
        """Initialize with the value to return for each reported quantity.

        An expression mapping to ``None`` stands for one AEDT lists but has no
        samples for, which PyAEDT answers with empty arrays. ``solved=False`` stands
        for a setup that was never solved, where ``get_solution_data`` returns False.
        """
        self.quantities = quantities
        self.unit = unit
        self.solved = solved
        self.solutions: list[MockSolutionData] = []
        self.requests: list[tuple[str | None, dict]] = []

    def available_report_quantities(self, quantities_category: str) -> list[str]:
        """Return the expression names a report category offers."""
        return list(self.quantities.get(quantities_category, {}))

    def get_solution_data(self, expressions: str | None = None, **kwargs):
        """Return a SolutionData for an expression, or False as PyAEDT does."""
        self.requests.append((expressions, kwargs))
        if not self.solved or expressions is None:
            return False
        for category in self.quantities.values():
            if expressions in category:
                value = category[expressions]
                values = [] if value is None else [value]
                solution = MockSolutionData(expressions, values, self.unit)
                self.solutions.append(solution)
                return solution
        return False


class MockHfssApp:
    """Minimal stand-in for a PyAEDT Hfss application exposing its post processor."""

    def __init__(self, post: MockPost) -> None:
        """Initialize with the canned post processor."""
        self.post = post


class MockBoundary:
    """Minimal stand-in for a PyAEDT boundary."""

    def __init__(self, name: str, boundary_type: str) -> None:
        """Initialize with the name and type a real boundary reports."""
        self.name = name
        self.type = boundary_type


class MockQ3dNetsApp:
    """Minimal stand-in for a PyAEDT Q3d application with nets and a post processor."""

    def __init__(self, post: MockPost, net_names: list[str]) -> None:
        """Initialize with signal nets drawn from the given names."""
        self.post = post
        self.boundaries = [MockBoundary(name, "SignalNet") for name in net_names]


class MockHfssImportApp(MockQ3dApp):
    """Minimal stand-in for a PyAEDT Hfss application that records PerfectE boundaries."""

    def __init__(self, object_names: list[str]):
        """Initialize with the names of objects created by the GDS import."""
        super().__init__(object_names)
        self.perfect_e: dict[str, list[str]] = {}

    def assign_perfect_e(self, assignment: list, name: str) -> None:
        """Record a PerfectE boundary on 3D objects."""
        self.perfect_e[name] = list(assignment)

    def assign_perfecte_to_sheets(self, assignment: list, name: str) -> None:
        """Record a PerfectE boundary on sheets."""
        self.perfect_e[name] = list(assignment)


@dataclass
class MockRectangle:
    """Minimal stand-in for a PyAEDT rectangle."""

    name: str
    origin: list[float]
    sizes: list[float]
    material: str


class MockQ2dModeler:
    """Minimal stand-in for a PyAEDT 2D modeler."""

    def __init__(self) -> None:
        """Initialize with no rectangles drawn."""
        self.model_units: str | None = None
        self.rectangles: dict[str, MockRectangle] = {}

    def create_rectangle(
        self, name: str, origin: list[float], sizes: list[float], material: str
    ) -> MockRectangle:
        """Draw a rectangle."""
        rectangle = MockRectangle(name, origin, sizes, material)
        self.rectangles[name] = rectangle
        return rectangle


class MockMesh:
    """Minimal stand-in for a PyAEDT mesh manager."""

    def __init__(self) -> None:
        """Initialize with no mesh operations."""
        self.length_meshes: list[dict] = []

    def assign_length_mesh(self, **kwargs: object) -> None:
        """Record a length-based mesh operation."""
        self.length_meshes.append(kwargs)


class MockQ2dApp:
    """Minimal stand-in for a PyAEDT Q2d application."""

    def __init__(self) -> None:
        """Initialize an empty 2D design."""
        self.modeler = MockQ2dModeler()
        self.materials = MockMaterials()
        self.mesh = MockMesh()
        self.conductors: dict[str, dict] = {}

    def assign_single_conductor(self, name: str, **kwargs: object) -> None:
        """Record a conductor assignment."""
        self.conductors[name] = kwargs
