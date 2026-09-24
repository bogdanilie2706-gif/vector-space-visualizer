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

def make_span_traces(basis: list, extent: float, color: str = "orange") -> list:
    """Traces for the span of an already-independent `basis`.
    1 vector -> line through the origin, 2 vectors -> plane, otherwise nothing."""
    if len(basis) == 1:
        d = basis[0]
        # Scale so the largest component reaches the axis edge; the other
        # two components are then automatically inside the cube.
        t = extent / max(abs(c) for c in d)
        return [go.Scatter3d(
            x=[-t * d[0], t * d[0]],
            y=[-t * d[1], t * d[1]],
            z=[-t * d[2], t * d[2]],
            mode="lines",
            line=dict(color=color, width=4),
            showlegend=False,
            hoverinfo="skip",
        )]

    if len(basis) == 2:
        v1, v2 = basis
        # Every point is s*v1 + t*v2. Choosing s,t in [-k, k] with this k
        # guarantees no coordinate can exceed the axis range.
        k = extent / (max(abs(c) for c in v1) + max(abs(c) for c in v2))
        params = [-k, k]

        def coord(i):
            # 2x2 grid of the i-th coordinate (0=x, 1=y, 2=z)
            return [[s * v1[i] + t * v2[i] for s in params] for t in params]

        return [go.Surface(
            x=coord(0), y=coord(1), z=coord(2),
            opacity=0.4,
            showscale=False,
            colorscale=[[0, color], [1, color]],
            hoverinfo="skip",
        )]

    return []  # 0 vectors (only origin) or 3 vectors (handled with a message)

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

def make_scene_figure(vectors: list, spans: list | None = None) -> go.Figure:
    """Build the full 3D figure from a list of vectors, plus any number of spans."""
    fig = go.Figure()
    extent = _compute_axis_extent(vectors)

    full_space_messages = []
    for i, span in enumerate(spans or []):
        basis = independent_basis(span["vectors"])
        for trace in make_span_traces(basis, extent, span["color"]):
            fig.add_trace(trace)
        if len(basis) == 3:
            full_space_messages.append(f"Span {i + 1} spans all of 3D space")

    for vector in vectors:
        for trace in make_vector_traces(vector["start"], vector["end"]):
            fig.add_trace(trace)

    if full_space_messages:
        fig.add_annotation(
            text="<br>".join(full_space_messages),
            xref="paper", yref="paper", x=0.5, y=1.0, yanchor="top",
            showarrow=False, font=dict(size=16),
        )

    fig.update_layout(
        scene=dict(
            xaxis=dict(range=[-extent, extent], title="x", showspikes=False),
            yaxis=dict(range=[-extent, extent], title="y", showspikes=False),
            zaxis=dict(range=[-extent, extent], title="z", showspikes=False),
            aspectmode="cube",
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        uirevision="constant",
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
                        "✕",
                        id={"type": "remove-vector-button", "index": index},
                        n_clicks=0,
                        style={"border": "none", "background": "none", "color": "crimson",
                               "cursor": "pointer", "font-size": "16px", "padding": "0 5px"},
                    ),
                ],
                style={"display": "flex", "justify-content": "space-between",
                       "align-items": "center", "margin-bottom": "10px"},
            ),
            _make_slider(index, "x", end["x"], slider_range["x"]),
            _make_slider(index, "y", end["y"], slider_range["y"]),
            _make_slider(index, "z", end["z"], slider_range["z"]),
        ],
        style={"padding": "16px", "border-radius": "12px", "background-color": "white",
               "box-shadow": "0 2px 8px rgba(0, 0, 0, 0.08)"},
    )

def span_card(index: int, span: dict) -> html.Div:
    """One card describing a span: color swatch, its vectors, and what it spans."""
    basis = independent_basis(span["vectors"])
    vector_lines = [
        html.Div(f"v{i + 1} = ({x:g}, {y:g}, {z:g})", style={"font-size": "13px"})
        for i, (x, y, z) in enumerate(_as_tuple(v) for v in span["vectors"])
    ]

    return html.Div(
        children=[
            html.Div(
                children=[
                    html.Div(
                        children=[
                            html.Span(style={"display": "inline-block", "width": "12px",
                                             "height": "12px", "border-radius": "50%",
                                             "background-color": span["color"],
                                             "margin-right": "8px"}),
                            html.Strong(f"Span {index + 1}"),
                        ],
                    ),
                    html.Button(
                        "✕",
                        id={"type": "remove-span-card-button", "index": index},
                        n_clicks=0,
                        style={"border": "none", "background": "none", "color": "crimson",
                               "cursor": "pointer", "font-size": "16px", "padding": "0 5px"},
                    ),
                ],
                style={"display": "flex", "justify-content": "space-between",
                       "align-items": "center", "margin-bottom": "10px"},
            ),
            *vector_lines,
            html.Div(SPAN_LABELS[len(basis)],
                     style={"margin-top": "10px", "font-size": "13px", "color": "#555"}),
        ],
        style={"padding": "16px", "border-radius": "12px", "background-color": "white",
               "box-shadow": "0 2px 8px rgba(0, 0, 0, 0.08)"},
    )

def build_span_cards(spans: list) -> list:
    return [span_card(i, span) for i, span in enumerate(spans)]

def build_slider_cards(vectors: list) -> list:
    """Rebuild every slider card from the current vectors list, WITHOUT
    touching any vector's stored slider_range."""
    return [vector_slider_group(i, vector) for i, vector in enumerate(vectors)]

def span_input_row(index: int) -> html.Div:
    """One row of x/y/z inputs for the span feature. Every row except the
    first also gets a remove button."""
    children = [
        dcc.Input(id={"type": "span-row-input", "axis": "x", "index": index},
                  type="number", placeholder="x", value=0, style={"width": "60px"}),
        dcc.Input(id={"type": "span-row-input", "axis": "y", "index": index},
                  type="number", placeholder="y", value=0, style={"width": "60px"}),
        dcc.Input(id={"type": "span-row-input", "axis": "z", "index": index},
                  type="number", placeholder="z", value=0, style={"width": "60px"}),
    ]
    if index != 0:
        children.append(
            html.Button(
                "✕",
                id={"type": "remove-span-row-button", "index": index},
                n_clicks=0,
                style={"border": "none", "background": "none", "color": "crimson",
                       "cursor": "pointer", "font-size": "16px", "padding": "0 5px"},
            )
        )
    return html.Div(
        id={"type": "span-row", "index": index},
        children=children,
        style={"display": "flex", "gap": "10px", "margin-top": "10px", "align-items": "center"},
    )

# ---------------------------------------------------------------------------
# Span helpers — figuring out what a set of vectors spans
# ---------------------------------------------------------------------------
EPSILON = 1e-9  # anything smaller than this counts as zero (float safety)
MAX_SPAN_VECTORS = 3      # most vectors the span feature accepts
SPAN_COLORS = ["orange", "mediumseagreen", "mediumpurple", "crimson", "teal", "goldenrod"]
SPAN_LABELS = {0: "Just the origin", 1: "A line", 2: "A plane", 3: "All of 3D space"}


def _next_span_color(spans: list) -> str:
    """First palette color not already used; cycle if all are taken."""
    used = {span["color"] for span in spans}
    for color in SPAN_COLORS:
        if color not in used:
            return color
    return SPAN_COLORS[len(spans) % len(SPAN_COLORS)]

def _as_tuple(v: dict) -> tuple:
    # Empty dcc.Input fields come back as None, so treat those as 0.
    return (v["x"] or 0, v["y"] or 0, v["z"] or 0)


def _cross(a: tuple, b: tuple) -> tuple:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: tuple, b: tuple) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def independent_basis(span_vectors: list) -> list:
    """Return the largest linearly independent subset, in input order.
    len(result) is the dimension of the span:
      0 -> just the origin, 1 -> a line, 2 -> a plane, 3 -> all of 3D."""
    basis = []
    for raw in span_vectors:
        v = _as_tuple(raw)

        if len(basis) == 0:
            # Only need it to be non-zero.
            if _dot(v, v) > EPSILON:
                basis.append(v)

        elif len(basis) == 1:
            # Independent of the first if the cross product isn't zero
            # (cross product is zero exactly when vectors are parallel).
            c = _cross(basis[0], v)
            if _dot(c, c) > EPSILON:
                basis.append(v)

        elif len(basis) == 2:
            # Independent of both if the triple product (determinant) isn't zero,
            # i.e. v is not in the plane of the first two.
            triple = _dot(_cross(basis[0], basis[1]), v)
            if abs(triple) > EPSILON:
                basis.append(v)

    return basis

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = dash.Dash(__name__, assets_folder="../assets")
app.title = "Vector Space Visualizer"

initial_vector = build_vector(1, 1, 1)

app.layout = html.Div(
    style={"height": "100vh", "display": "flex", "flex-direction": "column"},
    children=[
        html.Div(
            style={"display": "flex", "gap": "20px", "flex": "1", "min-height": "0"},
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
                                html.Div(
                                    style={"display": "flex", "gap": "10px"},
                                    children=[
                                        dcc.Input(id="input-x", type="number", placeholder="x", value=0, style={"width": "60px"}),
                                        dcc.Input(id="input-y", type="number", placeholder="y", value=0, style={"width": "60px"}),
                                        dcc.Input(id="input-z", type="number", placeholder="z", value=0, style={"width": "60px"}),
                                    ],
                                ),
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
                    style={"flex-grow": "1", "min-width": "0", "min-height": "0"},
                    children=[
                        dcc.Graph(id="vector-plot", figure=make_scene_figure([initial_vector]), style={"height": "100%"}),
                    ],
                ),
            ],
        ),
        html.Div(
            id="cards-panel",
            style={"display": "grid", "grid-template-columns": "repeat(auto-fill, minmax(220px, 1fr))",
                "gap": "16px", "padding": "16px", "box-shadow": "60px 0 12px rgba(0, 0, 0, 0.3)",
                "background-color": "#f5f5f7", "position": "relative", "z-index": "1",
                "flex-shrink": "0", "max-height": "30vh", "overflow-y": "auto",},
            children=[
                html.Div(
                    id="sliders-container",
                    children=build_slider_cards([initial_vector]),
                    style={"display": "contents"},
                ),
                html.Div(
                    id="span-cards-container",
                    children=[],
                    style={"display": "contents"},
                ),
            ],
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
        "flex-direction": "column", "gap": "10px", "margin-top": "10px",
    }
    span_style = {
        "display": "flex" if state["span_open"] else "none",
        "flex-direction": "column", "gap": "10px", "margin-top": "10px",
    }

    return sidebar_style, add_vector_style, span_style, state

def _row_index(row: dict) -> int:
    """State comes back from the browser as plain dicts, not components;
    a row's index lives in the id of the row Div."""
    return row["props"]["id"]["index"]

def _handle_show_span(x_values, y_values, z_values, spans):
    new_span = {
        "vectors": [{"x": x_values[i], "y": y_values[i], "z": z_values[i]}
                    for i in range(len(x_values))],
        "color": _next_span_color(spans),
    }
    # Append the new span, and reset the input area to a single blank row.
    return [span_input_row(0)], spans + [new_span]


def _handle_remove_span(index, spans):
    return dash.no_update, [span for i, span in enumerate(spans) if i != index]


@app.callback(
    dash.Output("span-input-rows", "children"),
    dash.Output("span-vectors-store", "data"),
    dash.Input("add-span-row-button", "n_clicks"),
    dash.Input({"type": "remove-span-row-button", "index": dash.ALL}, "n_clicks"),
    dash.Input("show-span-button", "n_clicks"),
    dash.Input({"type": "remove-span-card-button", "index": dash.ALL}, "n_clicks"),
    dash.State("span-input-rows", "children"),
    dash.State({"type": "span-row-input", "axis": "x", "index": dash.ALL}, "value"),
    dash.State({"type": "span-row-input", "axis": "y", "index": dash.ALL}, "value"),
    dash.State({"type": "span-row-input", "axis": "z", "index": dash.ALL}, "value"),
    dash.State("span-vectors-store", "data"),
    prevent_initial_call=True,
)
def handle_span_rows(add_clicks, remove_row_clicks, show_clicks, remove_card_clicks,
                     rows, x_values, y_values, z_values, spans):
    triggered = dash.ctx.triggered_id

    if triggered == "add-span-row-button":
        if len(rows) >= MAX_SPAN_VECTORS:
            return dash.no_update, dash.no_update
        new_index = max(_row_index(row) for row in rows) + 1
        return rows + [span_input_row(new_index)], dash.no_update

    if triggered == "show-span-button":
        return _handle_show_span(x_values, y_values, z_values, spans)

    if isinstance(triggered, dict):
        # Both remove buttons are created dynamically, and a fresh button can
        # fire this callback with n_clicks=0 — only react to a real click.
        if not dash.ctx.triggered[0]["value"]:
            return dash.no_update, dash.no_update

        if triggered["type"] == "remove-span-row-button":
            remaining = [row for row in rows if _row_index(row) != triggered["index"]]
            return remaining, dash.no_update

        if triggered["type"] == "remove-span-card-button":
            return _handle_remove_span(triggered["index"], spans)

    return dash.no_update, dash.no_update

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
    dash.Output("input-x", "value"),
    dash.Output("input-y", "value"),
    dash.Output("input-z", "value"),
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
    NO_FIELD_CHANGE = (dash.no_update,) * 3   # leave input-x/y/z alone

    if triggered == "add-vector-button":
        vectors, sliders = _handle_add(input_x or 0, input_y or 0, input_z or 0,
                                       current_vectors, current_sliders)
        return vectors, sliders, 0, 0, 0   # reset the fields

    if isinstance(triggered, dict) and triggered.get("type") == "remove-vector-button":
        vectors, sliders = _handle_remove(triggered["index"], current_vectors)
        return vectors, sliders, *NO_FIELD_CHANGE

    vectors, sliders = _handle_slider_move(x_values, y_values, z_values, current_vectors)
    return vectors, sliders, *NO_FIELD_CHANGE

# ---------------------------------------------------------------------------
# Callback: redraw plot whenever the store changes
# ---------------------------------------------------------------------------
@app.callback(
    dash.Output("vector-plot", "figure"),
    dash.Input("vectors-store", "data"),
    dash.Input("span-vectors-store", "data"),
)
def update_plot_from_store(vectors: list, spans: list) -> go.Figure:
    return make_scene_figure(vectors, spans)

@app.callback(
    dash.Output("span-cards-container", "children"),
    dash.Input("span-vectors-store", "data"),
)
def update_span_cards(spans: list) -> list:
    return build_span_cards(spans)

if __name__ == "__main__":
    app.run(debug=True)