import dash
from dash import dcc, html
import plotly.graph_objects as go
import math

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HEAD_FRACTION = 0.3       # fraction of a vector's length occupied by the arrowhead
SLIDER_PADDING = 5        # slider range is created_value ± this, fixed at creation time
MIN_AXIS_EXTENT = 5       # plot never shows a smaller range than [-5, 5]


# ---------------------------------------------------------------------------
# Data helpers — building/shaping vector data
# ---------------------------------------------------------------------------
def build_vector(x: float, y: float, z: float, start: dict | None = None) -> dict:
    """Create a new vector's data, including a FIXED slider range computed
    once from the given values. This range is never recalculated later —
    that's what keeps slider ranges stable when other vectors are added
    or removed."""
    if start is None:
        start = {"x": 0, "y": 0, "z": 0}

    end = {"x": x, "y": y, "z": z}
    slider_range = {
        axis: (end[axis] - SLIDER_PADDING, end[axis] + SLIDER_PADDING)
        for axis in ("x", "y", "z")
    }
    return {"start": start, "end": end, "slider_range": slider_range}


def with_updated_end(vector: dict, x: float, y: float, z: float) -> dict:
    """Return a copy of `vector` with a new end point, keeping its
    start and (crucially) its original slider_range untouched."""
    return {
        "start": vector["start"],
        "end": {"x": x, "y": y, "z": z},
        "slider_range": vector["slider_range"],
    }


# ---------------------------------------------------------------------------
# Drawing — turning vector data into a Plotly figure
# ---------------------------------------------------------------------------
def make_vector_traces(start: dict, end: dict, color: str = "royalblue") -> list:
    """Build the traces (shaft + arrowhead) for ONE vector, from `start` to `end`."""
    dx = end["x"] - start["x"]
    dy = end["y"] - start["y"]
    dz = end["z"] - start["z"]

    # Shaft stops short of the tip so it doesn't poke through the cone.
    shaft_end = {
        "x": start["x"] + dx * (1 - HEAD_FRACTION),
        "y": start["y"] + dy * (1 - HEAD_FRACTION),
        "z": start["z"] + dz * (1 - HEAD_FRACTION),
    }

    shaft = go.Scatter3d(
        x=[start["x"], shaft_end["x"]],
        y=[start["y"], shaft_end["y"]],
        z=[start["z"], shaft_end["z"]],
        mode="lines",
        line=dict(color=color, width=6),
        showlegend=False,
        hoverinfo="skip",
    )

    arrowhead = go.Cone(
        x=[end["x"]], y=[end["y"]], z=[end["z"]],
        u=[dx], v=[dy], w=[dz],
        sizemode="scaled",
        sizeref=HEAD_FRACTION,
        anchor="tip",
        colorscale=[[0, color], [1, color]],
        showscale=False,
    )

    return [shaft, arrowhead]


def _compute_axis_extent(vectors: list) -> float:
    """Find how far the plot's axes need to reach to fit every vector,
    with some padding, never smaller than MIN_AXIS_EXTENT."""
    coords = []
    for vector in vectors:
        coords += [vector["start"]["x"], vector["end"]["x"]]
        coords += [vector["start"]["y"], vector["end"]["y"]]
        coords += [vector["start"]["z"], vector["end"]["z"]]

    max_extent = max(max(abs(c) for c in coords), MIN_AXIS_EXTENT)
    return math.ceil(max_extent * 1.2)


def make_scene_figure(vectors: list) -> go.Figure:
    """Build the full 3D figure from a list of vectors."""
    fig = go.Figure()
    for vector in vectors:
        for trace in make_vector_traces(vector["start"], vector["end"]):
            fig.add_trace(trace)

    extent = _compute_axis_extent(vectors)

    fig.update_layout(
        scene=dict(
            xaxis=dict(range=[-extent, extent], title="x"),
            yaxis=dict(range=[-extent, extent], title="y"),
            zaxis=dict(range=[-extent, extent], title="z"),
            aspectmode="cube",
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        uirevision="constant",  # keeps camera angle/zoom stable across re-renders
        scene_uirevision="constant",
    )
    return fig


# ---------------------------------------------------------------------------
# UI builders
# ---------------------------------------------------------------------------
def _make_slider(index: int, axis: str, value: float, value_range: tuple) -> html.Div:
    lo, hi = value_range
    return html.Div(
        children=[
            html.Label(f"Vector {index + 1} - {axis}", style={"font-size": "13px"}),
            dcc.Slider(
                id={"type": "vector-slider", "axis": axis, "index": index},
                min=lo, max=hi, step=0.1, value=value,
                tooltip={"placement": "bottom", "always_visible": True},
            ),
        ],
        style={"margin-bottom": "10px"},
    )


def vector_slider_group(index: int, vector: dict) -> html.Div:
    """Build one card of x/y/z sliders for the vector at `index`.
    Uses the vector's OWN stored slider_range — never recalculated here."""
    end = vector["end"]
    slider_range = vector["slider_range"]

    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Strong(f"Vector {index + 1}"),
                    html.Button(
                        "⋮",
                        id={"type": "vector-menu-button", "index": index},
                        n_clicks=0,
                        style={"border": "none", "background": "none", "font-size": "20px",
                               "cursor": "pointer", "padding": "0 5px"},
                    ),
                ],
                style={"display": "flex", "justify-content": "space-between",
                       "align-items": "center", "margin-bottom": "10px"},
            ),
            _make_slider(index, "x", end["x"], slider_range["x"]),
            _make_slider(index, "y", end["y"], slider_range["y"]),
            _make_slider(index, "z", end["z"], slider_range["z"]),
            html.Div(
                id={"type": "vector-menu", "index": index},
                children=[
                    html.Button(
                        "Remove vector",
                        id={"type": "remove-vector-button", "index": index},
                        n_clicks=0,
                        style={"border": "none", "background": "none", "color": "crimson",
                               "cursor": "pointer", "width": "100%", "text-align": "left", "padding": "5px"},
                    )
                ],
                style={"display": "none"},
            ),
        ],
        style={"padding": "16px", "border-radius": "12px", "background-color": "white",
                "box-shadow": "0 2px 8px rgba(0, 0, 0, 0.08)", "position": "relative"},
    )


def build_slider_cards(vectors: list) -> list:
    """Rebuild every slider card from the current vectors list, WITHOUT
    touching any vector's stored slider_range."""
    return [vector_slider_group(i, vector) for i, vector in enumerate(vectors)]

def span_input_row(index: int) -> html.Div:
    """One row of x/y/z inputs for the span feature, identified by
    `index` so a variable number of rows can exist at once."""
    return html.Div(
        children=[
            dcc.Input(id={"type": "span-row-input", "axis": "x", "index": index},
                       type="number", placeholder="x", value=0, style={"width": "60px"}),
            dcc.Input(id={"type": "span-row-input", "axis": "y", "index": index},
                       type="number", placeholder="y", value=0, style={"width": "60px"}),
            dcc.Input(id={"type": "span-row-input", "axis": "z", "index": index},
                       type="number", placeholder="z", value=0, style={"width": "60px"}),
        ],
        style={"display": "flex", "gap": "10px", "margin-top": "10px"},
    )


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = dash.Dash(__name__, assets_folder="../assets")
app.title = "Vector Space Visualizer"

initial_vector = build_vector(1, 1, 1)

app.layout = html.Div(
    children=[
        html.Div(
            style={"display": "flex", "gap": "20px"},
            children=[
                html.Div(
                    id="sidebar",
                    style={"width": "60px", "flex-shrink": "0","display": "flex", "flex-direction": "column",
                            "gap": "10px","transition": "width 0.2s", "padding-top": "20px", "padding-left": "10px",
                            "padding-right": "10px", "box-shadow": "2px 0 12px rgba(0, 0, 0, 0.5)", "background-color": "gray",
                    },
                    children=[
                        dcc.Store(id="vectors-store", data=[initial_vector]),
                        dcc.Store(id="span-vectors-store", data=[]),
                        dcc.Store(id="sidebar-state", data={"add_vector_open": False, "span_open": False}),

                        html.Button("+ Add Vector", id="toggle-add-vector-button", n_clicks=0),
                        html.Div(
                            id="add-vector-fields",
                            style={"display": "none", "flex-direction": "column", "gap": "10px", "margin-top": "10px"},
                            children=[
                                dcc.Input(id="input-x", type="number", placeholder="x", value=0, style={"width": "60px"}),
                                dcc.Input(id="input-y", type="number", placeholder="y", value=0, style={"width": "60px"}),
                                dcc.Input(id="input-z", type="number", placeholder="z", value=0, style={"width": "60px"}),
                                html.Button("Create Vector", id="add-vector-button", n_clicks=0),
                            ],
                        ),

                        html.Button("+ Span", id="toggle-span-button", n_clicks=0),
                        html.Div(
                            id="span-fields",
                            style={"display": "none", "flex-direction": "column", "gap": "10px", "margin-top": "10px"},
                            children=[
                                html.Div(id="span-input-rows", children=[span_input_row(0)]),
                                html.Button("+ Add another vector", id="add-span-row-button", n_clicks=0),
                                html.Button("Show Span", id="show-span-button", n_clicks=0),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    style={"flex-grow": "1"},
                    children=[
                        dcc.Graph(id="vector-plot", figure=make_scene_figure([initial_vector])),
                    ],
                ),
            ],
        ),
        html.Div(
            id="sliders-container",
            children=build_slider_cards([initial_vector]),
            style={"display": "grid", "grid-template-columns": "repeat(auto-fill, minmax(220px, 1fr))", "gap": "16px",
                    "padding": "16px", "box-shadow": "60px 0 12px rgba(0, 0, 0, 0.3)", "background-color": "#f5f5f7", "position": "relative", "z-index": "1",},
        ),
    ],
)


@app.callback(
    dash.Output("sidebar", "style"),
    dash.Output("add-vector-fields", "style"),
    dash.Output("span-fields", "style"),
    dash.Output("sidebar-state", "data"),
    dash.Input("toggle-add-vector-button", "n_clicks"),
    dash.Input("toggle-span-button", "n_clicks"),
    dash.State("sidebar-state", "data"),
    prevent_initial_call=True,
)
def toggle_sidebar_sections(add_clicks, span_clicks, state):
    triggered = dash.ctx.triggered_id

    if triggered == "toggle-add-vector-button":
        state["add_vector_open"] = not state["add_vector_open"]
    elif triggered == "toggle-span-button":
        state["span_open"] = not state["span_open"]

    any_open = state["add_vector_open"] or state["span_open"]

    sidebar_style = {
        "width": "260px" if any_open else "60px",
        "flex-shrink": "0","display": "flex", "flex-direction": "column",
        "gap": "10px","transition": "width 0.2s", "padding-top": "20px", "padding-left": "10px",
        "padding-right": "10px", "box-shadow": "2px 0 12px rgba(0, 0, 0, 0.5)",
        "background-color": "gray"
    }
    add_vector_style = {
        "display": "flex" if state["add_vector_open"] else "none",
        "flex-direction": "row", "gap": "10px", "margin-top": "10px",
    }
    span_style = {
        "display": "flex" if state["span_open"] else "none",
        "flex-direction": "column", "gap": "10px", "margin-top": "10px",
    }

    return sidebar_style, add_vector_style, span_style, state

@app.callback(
    dash.Output("span-input-rows", "children"),
    dash.Input("add-span-row-button", "n_clicks"),
    dash.State("span-input-rows", "children"),
    prevent_initial_call=True,
)
def add_span_row(n_clicks, current_rows):
    if len(current_rows) >= 3:
        return dash.no_update  # already at the max of 3 vectors
    new_index = len(current_rows)
    return current_rows + [span_input_row(new_index)]

@app.callback(
    dash.Output("span-vectors-store", "data"),
    dash.Input("show-span-button", "n_clicks"),
    dash.State({"type": "span-row-input", "axis": "x", "index": dash.ALL}, "value"),
    dash.State({"type": "span-row-input", "axis": "y", "index": dash.ALL}, "value"),
    dash.State({"type": "span-row-input", "axis": "z", "index": dash.ALL}, "value"),
    prevent_initial_call=True,
)
def show_span(n_clicks, x_values, y_values, z_values):
    span_vectors = [
        {"x": x_values[i], "y": y_values[i], "z": z_values[i]}
        for i in range(len(x_values))
    ]
    return span_vectors

# ---------------------------------------------------------------------------
# Callback: add / remove / drag — split into small helpers, dispatched by
# what actually triggered the callback (dash.ctx.triggered_id)
# ---------------------------------------------------------------------------
def _handle_add(input_x, input_y, input_z, current_vectors, current_sliders):
    new_vector = build_vector(input_x, input_y, input_z)
    updated_vectors = current_vectors + [new_vector]
    new_index = len(current_vectors)
    updated_sliders = current_sliders + [vector_slider_group(new_index, new_vector)]
    return updated_vectors, updated_sliders


def _handle_remove(index, current_vectors):
    if len(current_vectors) <= 1:
        # Don't allow removing the last vector; just rebuild as-is.
        return current_vectors, build_slider_cards(current_vectors)

    updated_vectors = [v for i, v in enumerate(current_vectors) if i != index]
    # Each remaining vector keeps its OWN stored slider_range — no recentering.
    return updated_vectors, build_slider_cards(updated_vectors)


def _handle_slider_move(x_values, y_values, z_values, current_vectors):
    updated_vectors = [
        with_updated_end(vector, x_values[i], y_values[i], z_values[i])
        for i, vector in enumerate(current_vectors)
    ]
    # Sliders themselves are untouched — dash.no_update below.
    return updated_vectors, dash.no_update


@app.callback(
    dash.Output("vectors-store", "data"),
    dash.Output("sliders-container", "children"),
    dash.Input("add-vector-button", "n_clicks"),
    dash.Input({"type": "remove-vector-button", "index": dash.ALL}, "n_clicks"),
    dash.Input({"type": "vector-slider", "axis": "x", "index": dash.ALL}, "value"),
    dash.Input({"type": "vector-slider", "axis": "y", "index": dash.ALL}, "value"),
    dash.Input({"type": "vector-slider", "axis": "z", "index": dash.ALL}, "value"),
    dash.State("input-x", "value"),
    dash.State("input-y", "value"),
    dash.State("input-z", "value"),
    dash.State("vectors-store", "data"),
    dash.State("sliders-container", "children"),
    prevent_initial_call=True,
)
def handle_vector_updates(n_clicks, remove_clicks, x_values, y_values, z_values,
                           input_x, input_y, input_z, current_vectors, current_sliders):
    triggered = dash.ctx.triggered_id

    if triggered == "add-vector-button":
        return _handle_add(input_x, input_y, input_z, current_vectors, current_sliders)

    if isinstance(triggered, dict) and triggered.get("type") == "remove-vector-button":
        return _handle_remove(triggered["index"], current_vectors)

    return _handle_slider_move(x_values, y_values, z_values, current_vectors)


# ---------------------------------------------------------------------------
# Callback: redraw plot whenever the store changes
# ---------------------------------------------------------------------------
@app.callback(
    dash.Output("vector-plot", "figure"),
    dash.Input("vectors-store", "data"),
)
def update_plot_from_store(vectors: list) -> go.Figure:
    return make_scene_figure(vectors)


# ---------------------------------------------------------------------------
# Callback: per-vector "⋮" menu toggle
# ---------------------------------------------------------------------------
@app.callback(
    dash.Output({"type": "vector-menu", "index": dash.MATCH}, "style"),
    dash.Input({"type": "vector-menu-button", "index": dash.MATCH}, "n_clicks"),
    prevent_initial_call=True,
)
def toggle_vector_menu(n_clicks):
    if n_clicks % 2 == 1:
        return {"display": "block", "position": "absolute", "right": "10px", "top": "35px",
                "background": "white", "border": "1px solid #ddd", "padding": "5px", "z-index": "10"}
    return {"display": "none"}


if __name__ == "__main__":
    app.run(debug=True)