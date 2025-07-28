from statemachine.contrib.diagram import DotGraphMachine 
import pydot
from pathlib import Path




class FFDotGraph(DotGraphMachine):
    state_font_size        = "16"
    transition_font_size   = "12"
    font_name              = "Arial"
    state_active_fillcolor = "#007bff"
    transition_edge_color  = "#f8f9fa"
    ratio                  = "auto"
    size                   = "512,512!"
    dpi                    = 5.12

    def __init__(self, machine):
        super().__init__(machine)
        self.label = machine.name

    def _get_graph(self):
        machine = self.machine
        return pydot.Dot(
            "list",
            graph_type="digraph",
            label=self.label,
            fontcolor="#ffffff",
            # top, left
            labelloc="t",
            # labeljust="l",
            fontname=self.font_name,
            fontsize=self.state_font_size,
            rankdir=self.graph_rankdir,
            ratio=self.ratio,
            size=self.size,
            # dpi=self.dpi,
            bgcolor= "#212529",
            # _background="transparent",
        )


    def _state_as_node(self, state):
        # actions = self._state_actions(state)

        label = f"{state.name}"

        node = pydot.Node(
            state.id,
            label=label,
            shape="rounrectangle",
            style="rounded, filled",
            fontname=self.font_name,
            fontsize=self.state_font_size,
            fontcolor="#ffffff",
            peripheries=2 if state.final else 1,
        )
        if state == self.machine.current_state:
            node.set_penwidth(self.state_active_penwidth)
            node.set_fillcolor(self.state_active_fillcolor)
        else:
            node.set_fillcolor("#6c757d")
        return node


    def get_graph(self):
        graph = self._get_graph()
        graph.add_node(self._initial_node())
        graph.add_edge(self._initial_edge())


        for state in self.machine.states:
            graph.add_node(self._state_as_node(state))
            for transition in state.transitions:
                if transition.internal:
                    continue

                if transition.event.startswith("t_automatic"):
                    continue

                graph.add_edge(self._transition_as_edge(transition))

        return graph

    def _initial_edge(self):
        return pydot.Edge(
            "i",
            self.machine.initial_state.id,
            label="",
            color=self.transition_edge_color,
            fontname=self.font_name,
            fontsize=self.transition_font_size,
        )
    
    def _transition_as_edge(self, transition):

        cond = ", ".join([str(cond) for cond in transition.cond])
        if cond:
            cond = f"\n[{cond}]"

        # label = f"{transition.event}{cond}"
        label = f"{transition.event}"
        
        return pydot.Edge(
            transition.source.id,
            transition.target.id,
            label=label,
            color=self.transition_edge_color,
            fontcolor="#ffffff",
            fontname=self.font_name,
            fontsize=self.transition_font_size,
        )
    
class SceneDotGraph(FFDotGraph):
    graph_rankdir          = "TB"
    ratio                  = "auto"
    size                   = "512,2048!"
    dpi                    = 512

    def __init__(self, machine):
        super().__init__(machine)
        self.label = "Scene Manager"

    def get_graph(self):

        graph = self._get_graph()

        graph.add_node(self._initial_node())
        graph.add_edge(self._initial_edge())

        for state in self.machine.states:
            if self._should_skip(state):

                continue

            graph.add_node(self._state_as_node(state))

            for transition in state.transitions:
                if transition.internal:
                    continue

                if self._should_skip(transition.target):
                    continue

                graph.add_edge(self._transition_as_edge(transition))

        return graph

    def _should_skip(self, state):
        ret = state.id in ["s_unknown_fault"]
        return ret

    def _state_actions(self, state):
        getter = self._actions_getter()

        entry = str(getter(state.enter))
        exit_ = str(getter(state.exit))
        internal = ", ".join(
            f"{transition.event} / {str(getter(transition.on))}"
            for transition in state.transitions
            if transition.internal
        )

        if entry:
            entry = f"entry / {entry}"
        if exit_:
            exit_ = f"exit / {exit_}"

        actions = "\n".join(x for x in [entry, exit_, internal] if x)

        if actions:
            actions = f"\n{actions}"

        return actions
    

    
class BehaviorDotGraph(FFDotGraph):
    state_font_size        = "18"
    transition_font_size   = "16"
    graph_rankdir          = "TB"
    # ratio                  = "fill"
    size                   = "512,512!"
    # size                   = "1,1!"
    # dpi                    = 512

    def __init__(self, machine):
        super().__init__(machine)
        label = "<"
        label += f'<B>Character:</B> {machine.display_name}'
        label += "<br/>"
        label += f'<B>Behavior:</B>  {machine.name}'
        label += ">"

        self.label = label

    def _state_actions(self, state):
        getter = self._actions_getter()

        entry = str(getter(state.enter))
        exit_ = str(getter(state.exit))
        internal = ", ".join(
            f"{transition.event} / {str(getter(transition.on))}"
            for transition in state.transitions
            if transition.internal
        )

        if entry:
            entry = f"entry / {entry}"
        if exit_:
            exit_ = f"exit / {exit_}"

        actions = "\n".join(x for x in [entry, exit_, internal] if x)

        if actions:
            actions = f"\n{actions}"

        return actions

def save_sm_diagram(sm, path):
    if Path(path).suffix == ".png":
        graph = SceneDotGraph(sm)
        dot = graph()
        dot.write_png(path)
    elif(Path(path).suffix == ".svg"):
        graph = SceneDotGraph(sm)
        dot = graph()
        dot.write_svg(path)
    else:
        raise ValueError("Invalid file format. Use .png or .svg")

    
def save_behavior_diagram(sm, path):
    if Path(path).suffix == ".png":
        graph = BehaviorDotGraph(sm)
        dot = graph()
        dot.write_png(path)
    elif(Path(path).suffix == ".svg"):
        graph = BehaviorDotGraph(sm)
        dot = graph()
        dot.write_svg(path)
    else:
        raise ValueError("Invalid file format. Use .png or .svg")