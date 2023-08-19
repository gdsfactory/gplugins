from pathlib import Path

import holoviews as hv
import panel as pn

hv.extension("bokeh")


class SimpleSchematicEditor:
    def __init__(self, filename: str | Path):
        self.filename = filename
        self.instances = []
        self.nets = []

        # UI Components
        self.inst_name = pn.widgets.TextInput(name="Instance Name")
        self.component_name = pn.widgets.TextInput(name="Component Name")
        self.add_instance_btn = pn.widgets.Button(name="Add Instance")
        self.add_instance_btn.on_click(self.add_instance)

        self.inst1 = pn.widgets.TextInput(name="Net Inst1")
        self.port1 = pn.widgets.TextInput(name="Net Port1")
        self.inst2 = pn.widgets.TextInput(name="Net Inst2")
        self.port2 = pn.widgets.TextInput(name="Net Port2")
        self.add_net_btn = pn.widgets.Button(name="Add Net")
        self.add_net_btn.on_click(self.add_net)

        # Holoviews Components
        self.points_dmap = hv.DynamicMap(self.get_points)
        self.edges_dmap = hv.DynamicMap(self.get_edges)
        self.layout = self.points_dmap * self.edges_dmap

    def add_instance(self, event):
        self.instances.append(
            {
                "inst_name": self.inst_name.value,
                "component_name": self.component_name.value,
            }
        )
        self.inst_name.value = ""
        self.component_name.value = ""

    def add_net(self, event):
        self.nets.append(
            {
                "inst1": self.inst1.value,
                "port1": self.port1.value,
                "inst2": self.inst2.value,
                "port2": self.port2.value,
            }
        )
        self.inst1.value = ""
        self.port1.value = ""
        self.inst2.value = ""
        self.port2.value = ""

    def get_points(self):
        return hv.Points(
            [(i, 0) for i, _ in enumerate(self.instances)], vdims="y"
        ).opts(size=10, color="blue")

    def get_edges(self):
        edges = []
        for net in self.nets:
            inst1_index = next(
                i
                for i, inst in enumerate(self.instances)
                if inst["inst_name"] == net["inst1"]
            )
            inst2_index = next(
                i
                for i, inst in enumerate(self.instances)
                if inst["inst_name"] == net["inst2"]
            )
            edges.append((inst1_index, inst2_index))
        return hv.Path(edges).opts(color="red")

    def view(self):
        return pn.Column(
            pn.Row(self.inst_name, self.component_name, self.add_instance_btn),
            pn.Row(self.inst1, self.port1, self.inst2, self.port2, self.add_net_btn),
            self.layout,
        )


if __name__ == "__main__":
    editor = SimpleSchematicEditor("test.schem.yml")
    editor.view().servable()
