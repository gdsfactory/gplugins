from pathlib import Path

import bokeh
import bokeh.io
import bokeh.plotting as bp
import gdsfactory as gf
import holoviews as hv
import panel as pn
import yaml
from gdsfactory.picmodel import (
    PicYamlConfiguration,
    Route,
    RouteSettings,
    SchematicConfiguration,
)

from gplugins.schematic_editor import circuitviz

pn.extension("bokeh")
hv.extension("bokeh")


class SchematicEditor:
    def __init__(self, filename: str | Path, pdk: gf.Pdk | None = None) -> None:
        self._connected_ports = {}
        self._inst_boxes = list()

        filepath = Path(filename)
        self.path = filepath
        self.pdk = pdk or gf.get_active_pdk()
        self.component_list = list(gf.get_active_pdk().cells.keys())
        self._initialize_schematic(filepath)
        self.setup_events()

    def create_instance_row(self, instance_name=None, instance_type=None):
        inst_name = pn.widgets.TextInput(value=instance_name or "")
        inst_type = pn.widgets.TextInput(value=instance_type or "")
        inst_remove = pn.widgets.Button(name="Remove", button_type="danger")
        inst_remove.on_click(self.remove_instance_row)
        return pn.Row(inst_name, inst_type, inst_remove)

    def remove_instance_row(self, event):
        # Remove a row
        # The actual implementation depends on how you manage the rows
        self.instances.pop(event.instance_name)

    @property
    def panel(self) -> pn.layout.Column:
        instances = [
            self.create_instance_row(iname, itype.settings.function_name)
            for iname, itype in self.instances.items()
        ]

        # Instance selectors and input
        inst_selector = pn.widgets.Select(
            name="Select instance", options=self.component_list
        )
        inst_input = pn.widgets.TextInput(
            name="Enter instance name", placeholder="Instance name"
        )
        inst_add = pn.widgets.Button(name="Add", button_type="primary")
        inst_row = pn.Row(inst_selector, inst_input, inst_add)

        # Assuming circuitviz.show_netlist returns a Bokeh plot
        # circuit_plot = circuitviz.show_netlist(self.schematic, self.symbols, self.path)
        circuit_plot = self.bokeh_plot()

        return pn.Column(*instances, inst_row, circuit_plot)

    def setup_events(self):
        self.on_instance_added = [
            self.write_netlist,
            self._update_instance_options,
            self._make_instance_removable,
        ]
        self.on_settings_updated = [self.write_netlist]
        self.on_nets_modified = [self.write_netlist]
        self.on_instance_removed = [self.write_netlist]

    def _initialize_schematic(self, filepath):
        if filepath.is_file():
            print("is file")
            self.load_netlist()
        else:
            print(f"not file {filepath}")
            self._schematic = SchematicConfiguration(
                instances={}, schematic_placements={}, nets=[], ports={}
            )

    def serve(self):
        pn.serve(self.panel)

    def _get_instance_selector(self, inst_name=None, component_name=None):
        instance_box = pn.widgets.TextInput(
            name="Instance Name", placeholder="Enter a name"
        )
        component_selector = pn.widgets.Select(
            name="Component", options=self.component_list
        )
        return self._add_remove_option(
            inst_name, instance_box, component_name, component_selector
        )

    def _get_port_selector(self, port_name: str | None = None, port: str | None = None):
        instance_port_selector = pn.widgets.TextInput(
            name="Instance:Port", placeholder="Enter instance and port"
        )
        port_name_box = pn.widgets.TextInput(
            name="Port Name", placeholder="Enter a name"
        )
        return self._add_remove_option(
            port_name, port_name_box, port, instance_port_selector
        )

    def _add_remove_option(self, arg0, arg1, arg2, arg3):
        can_remove = False
        if arg0:
            arg1.value = arg0
        if arg2:
            arg3.value = arg2
            can_remove = True
        remove_button = pn.widgets.Button(
            name="Remove", button_type="danger", disabled=not can_remove
        )
        remove_button.on_click(self._on_remove_button_clicked)
        row = pn.Row(arg1, arg3, remove_button)
        row._component_selector = arg3
        row._instance_box = arg1
        row._remove_button = remove_button
        remove_button._row = row
        arg1._row = row
        arg3._row = row
        return row

    def _update_instance_options(self, **kwargs) -> None:
        inst_names = self._schematic.instances.keys()
        for inst_box in self._inst_boxes:
            inst_box.options = list(inst_names)

    def _make_instance_removable(self, instance_name, **kwargs) -> None:
        for row in self._instance_grid.children:
            if row._instance_box.value == instance_name:
                row._remove_button.disabled = False
                return

    def _get_net_selector(self, inst1=None, port1=None, inst2=None, port2=None):
        inst_names = list(self._schematic.instances.keys())
        inst1_selector = pn.widgets.AutocompleteInput(
            placeholder="inst1", options=inst_names, ensure_option=True, disabled=False
        )
        inst2_selector = pn.widgets.AutocompleteInput(
            placeholder="inst2", options=inst_names, ensure_option=True, disabled=False
        )
        self._inst_boxes.extend([inst1_selector, inst2_selector])
        port1_selector = pn.widgets.TextInput(placeholder="port1", disabled=False)
        port2_selector = pn.widgets.TextInput(placeholder="port2", disabled=False)
        if inst1:
            inst1_selector.value = inst1
        if inst2:
            inst2_selector.value = inst2
        if port1:
            port1_selector.value = port1
        if port2:
            port2_selector.value = port2
        return pn.Row([inst1_selector, port1_selector, inst2_selector, port2_selector])

    def _add_row_when_full(self, change) -> None:
        if change["old"] == "" and change["new"] != "":
            this_box = change["owner"]
            last_box = self._instance_grid.children[-1].children[0]
            if this_box is last_box:
                new_row = self._get_instance_selector()
                self._instance_grid.children += (new_row,)
                new_row.children[0].observe(self._add_row_when_full, names=["value"])
                new_row.children[1].observe(
                    self._on_instance_component_modified, names=["value"]
                )
                new_row._associated_component = None

    def _add_net_row_when_full(self, change) -> None:
        if change["old"] == "" and change["new"] != "":
            this_box = change["owner"]
            last_box = self._net_grid.children[-1].children[0]
            if this_box is last_box:
                new_row = self._get_net_selector()
                self._net_grid.children += (new_row,)
                new_row.children[0].observe(
                    self._add_net_row_when_full, names=["value"]
                )
                for child in new_row.children:
                    child.observe(self._on_net_modified, names=["value"])
                new_row._associated_component = None

    def _update_schematic_plot(self, **kwargs) -> None:
        circuitviz.update_schematic_plot(
            schematic=self._schematic,
            instances=self.symbols,
        )

    def _on_instance_component_modified(self, change) -> None:
        this_box = change["owner"]
        inst_box = this_box._instance_selector
        inst_name = inst_box.value
        component_name = this_box.value

        if change["old"] == "":
            if change["new"] != "":
                self.add_instance(instance_name=inst_name, component=component_name)
        elif change["new"] != change["old"]:
            self.update_component(instance=inst_name, component=component_name)

    def _on_remove_button_clicked(self, button) -> None:
        row = button._row
        self.remove_instance(instance_name=row._instance_box.value)
        self._instance_grid.children = tuple(
            child for child in self._instance_grid.children if child is not row
        )

    def _get_data_from_row(self, row):
        inst_name, component_name = (w.value for w in row.children)
        return {"instance_name": inst_name, "component_name": component_name}

    def _get_instance_data(self):
        inst_data = [
            self._get_data_from_row(row) for row in self._instance_grid.children
        ]
        inst_data = [d for d in inst_data if d["instance_name"] != ""]
        return inst_data

    def _get_net_from_row(self, row):
        return [c.value for c in row.children]

    def _get_net_data(self):
        net_data = [self._get_net_from_row(row) for row in self._net_grid.children]
        net_data = [d for d in net_data if "" not in d]
        return net_data

    def _on_net_modified(self, change) -> None:
        if change["new"] == change["old"]:
            return
        net_data = self._get_net_data()
        new_nets = [[f"{n[0]},{n[1]}", f"{n[2]},{n[3]}"] for n in net_data]
        connected_ports = {}
        for n1, n2 in new_nets:
            connected_ports[n1] = n2
            connected_ports[n2] = n1
            self._connected_ports = connected_ports
        old_nets = self._schematic.nets
        self._schematic.nets = new_nets
        for callback in self.on_nets_modified:
            callback(old_nets=old_nets, new_nets=new_nets)

    @property
    def instance_widget(self):
        return self._instance_grid

    @property
    def net_widget(self):
        return self._net_grid

    @property
    def port_widget(self):
        return self._port_grid

    def bokeh_plot(self):
        # global data
        circuitviz.data["netlist"] = self.schematic

        fig = bp.figure(width=800, height=500)
        circuitviz.viz_bk(
            self.schematic,
            instances=self.instances,
            fig=fig,
            instance_size=50,
            netlist_filename=self.path,  # Assuming this is the desired filename
        )
        return pn.pane.Bokeh(fig)

    def visualize(self) -> None:
        circuitviz.show_netlist(self.schematic, self.symbols, self.path)

        self.on_instance_added.append(self._update_schematic_plot)
        self.on_settings_updated.append(self._update_schematic_plot)
        self.on_nets_modified.append(self._update_schematic_plot)
        self.on_instance_removed.append(self._update_schematic_plot)

    @property
    def instances(self):
        insts = {}
        inst_data = self._schematic.instances
        for inst_name, inst in inst_data.items():
            component_spec = inst.dict()
            # if component_spec['settings'] is None:
            #     component_spec['settings'] = {}
            # validates the settings
            insts[inst_name] = gf.get_component(component_spec)
        return insts

    @property
    def symbols(self):
        insts = {}
        inst_data = self._schematic.instances
        for inst_name, inst in inst_data.items():
            component_spec = inst.dict()
            insts[inst_name] = self.pdk.get_symbol(component_spec)
        return insts

    def add_instance(self, instance_name: str, component: str | gf.Component) -> None:
        self._schematic.add_instance(name=instance_name, component=component)
        for callback in self.on_instance_added:
            callback(instance_name=instance_name)

    def remove_instance(self, instance_name: str) -> None:
        self._schematic.instances.pop(instance_name)
        if instance_name in self._schematic.placements:
            self._schematic.placements.pop(instance_name)
        for callback in self.on_instance_removed:
            callback(instance_name=instance_name)

    def update_component(self, instance, component) -> None:
        self._schematic.instances[instance].component = component
        self.update_settings(instance=instance, clear_existing=True)

    def update_settings(
        self, instance, clear_existing: bool = False, **settings
    ) -> None:
        old_settings = self._schematic.instances[instance].settings.copy()
        if clear_existing:
            self._schematic.instances[instance].settings.clear()
        if settings:
            self._schematic.instances[instance].settings.update(settings)
        for callback in self.on_settings_updated:
            callback(
                instance_name=instance, settings=settings, old_settings=old_settings
            )

    def add_net(self, inst1, port1, inst2, port2):
        p1 = f"{inst1},{port1}"
        p2 = f"{inst2},{port2}"
        if p1 in self._connected_ports:
            if self._connected_ports[p1] == p2:
                return
            current_port = self._connected_ports[p1]
            raise ValueError(
                f"{p1} is already connected to {current_port}. Can't connect to {p2}"
            )
        self._connected_ports[p1] = p2
        self._connected_ports[p2] = p1
        old_nets = self._schematic.nets.copy()
        self._schematic.nets.append([p1, p2])
        new_row = self._get_net_selector(
            inst1=inst1, inst2=inst2, port1=port1, port2=port2
        )
        existing_rows = self._net_grid.children
        new_rows = existing_rows[:-1] + (new_row, existing_rows[-1])
        self._net_grid.children = new_rows
        for callback in self.on_nets_modified:
            callback(old_nets=old_nets, new_nets=self._schematic.nets)

    def get_netlist(self):
        return self._schematic.dict()

    @property
    def schematic(self):
        return self._schematic

    def write_netlist(self, **kwargs) -> None:
        netlist = self.get_netlist()
        with open(self.path, mode="w") as f:
            yaml.dump(netlist, f, default_flow_style=None, sort_keys=False)

    def load_netlist(self) -> None:
        with open(self.path) as f:
            netlist = yaml.safe_load(f)

        schematic = SchematicConfiguration.parse_obj(netlist)
        self._schematic = schematic

        # process instances
        instances = netlist["instances"]
        nets = netlist.get("nets", [])
        new_rows = []
        for inst_name, inst in instances.items():
            component_name = inst["component"]
            new_row = self._get_instance_selector(
                inst_name=inst_name, component_name=component_name
            )
            new_row[0].param.watch(self._add_row_when_full, "value")
            new_row[1].param.watch(self._on_instance_component_modified, "value")
            new_rows.append(new_row)
        self._instance_grid = pn.Column(*new_rows)

        # process nets
        unpacked_nets = []
        net_rows = []
        for net in nets:
            unpacked_net = []
            for net_entry in net:
                inst_name, port_name = net_entry.split(",")
                unpacked_net.extend([inst_name, port_name])
            unpacked_nets.append(unpacked_net)
            net_rows.append(self._get_net_selector(*unpacked_net))
            self._connected_ports[net[0]] = net[1]
            self._connected_ports[net[1]] = net[0]
        self._net_grid = pn.Column(*net_rows)

        # process ports
        ports = netlist.get("ports", {})
        schematic.ports = ports
        new_rows = []
        for port_name, port in ports.items():
            new_row = self._get_port_selector(port_name=port_name, port=port)
            new_row[0].param.watch(self._add_row_when_full, "value")
            new_row[1].param.watch(self._on_instance_component_modified, "value")
            new_rows.append(new_row)
        self._port_grid = pn.Column(*new_rows)

    def instantiate_layout(
        self,
        output_filename,
        default_router="get_bundle",
        default_cross_section="strip",
    ):
        schematic = self._schematic
        routes = {}
        for inet, net in enumerate(schematic.nets):
            route = Route(
                routing_strategy=default_router,
                links={net[0]: net[1]},
                settings=RouteSettings(cross_section=default_cross_section),
            )
            routes[f"r{inet}"] = route
        pic_conf = PicYamlConfiguration(
            instances=schematic.instances,
            placements=schematic.placements,
            routes=routes,
            ports=schematic.ports,
        )
        pic_conf.to_yaml(output_filename)
        return pic_conf

    def save_schematic_html(
        self, filename: str | Path, title: str | None = None
    ) -> None:
        """Saves the schematic visualization to a standalone html file (read-only).

        Args:
            filename: the (*.html) filename to write to
            title: title for the output page
        """
        filename = Path(filename)
        if title is None:
            title = f"{filename.stem} Schematic"
        if "doc" not in circuitviz.data:
            self.visualize()
        if "doc" in circuitviz.data:
            bokeh.io.save(circuitviz.data["doc"], filename=filename, title=title)
        else:
            raise ValueError(
                "Unable to save the schematic to a standalone html file! Has the visualization been loaded yet?"
            )


if __name__ == "__main__":
    from gplugins.config import PATH

    se = SchematicEditor(PATH.module / "schematic_editor" / "test.schem.yml")
    # se = SchematicEditor("a.schem.yml")
    se.serve()
    # print(se.schematic)
