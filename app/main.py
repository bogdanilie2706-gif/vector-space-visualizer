import dash
from dash import dcc, html
from dash import Patch
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

def make_scene_figure(vectors: list, spans: list | None = None,
                      transform: list | None = None, blend: float = 1.0) -> go.Figure:
    fig = go.Figure()
    extent = _compute_axis_extent(vectors)
    if transform:
        extent = max(extent, _transform_extent(transform, vectors))

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

    if transform:
        for trace in make_transform_traces(transform, blend, vectors):
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

def matrix_input_grid() -> html.Div:
    """3x3 grid of number inputs, identity by default. Row r, column c is entry A[r][c]."""
    return html.Div(
        style={"display": "flex", "flex-direction": "column", "gap": "10px"},
        children=[
            html.Div(
                style={"display": "flex", "gap": "10px"},
                children=[
                    dcc.Input(id=f"matrix-{r}{c}", type="number",
                              value=1 if r == c else 0, style={"width": "60px"})
                    for c in range(3)
                ],
            )
            for r in range(3)
        ],
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

IDENTITY = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
MATRIX_INPUT_IDS = [f"matrix-{r}{c}" for r in range(3) for c in range(3)]  # row-major

BASIS_COLORS = ["#D85A30", "#1D9E75", "#7F77DD"]   # where x, y, z land
CUBE_ORIGINAL_COLOR = "gray"
CUBE_IMAGE_COLOR = "steelblue"
IMAGE_VECTOR_COLOR = "deeppink"                     # your vectors after the matrix

CARD_STYLE = {"padding": "16px", "border-radius": "12px", "background-color": "white",
              "box-shadow": "0 2px 8px rgba(0, 0, 0, 0.08)"}

def blend_matrix(matrix: list, t: float) -> list:
    """(1 - t) * identity + t * matrix — slides smoothly from 'nothing
    happened' at t=0 to the full transformation at t=1."""
    return [[(1 - t) * IDENTITY[r][c] + t * matrix[r][c] for c in range(3)] for r in range(3)]


def apply_matrix(m: list, p: tuple) -> tuple:
    return tuple(sum(m[r][c] * p[c] for c in range(3)) for r in range(3))


def determinant(m: list) -> float:
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def _point(d: dict) -> tuple:
    return (d["x"], d["y"], d["z"])


def _as_point_dict(p: tuple) -> dict:
    return {"x": p[0], "y": p[1], "z": p[2]}

CUBE_VERTICES = [(i & 1, (i >> 1) & 1, (i >> 2) & 1) for i in range(8)]
CUBE_EDGES = [(i, i | bit) for i in range(8) for bit in (1, 2, 4) if not i & bit]
_CUBE_FACES = [(0, 2, 6, 4), (1, 3, 7, 5), (0, 1, 5, 4), (2, 3, 7, 6), (0, 1, 3, 2), (4, 5, 7, 6)]
CUBE_TRIANGLES = [tri for a, b, c, d in _CUBE_FACES for tri in ((a, b, c), (a, c, d))]

def _cube_edges_trace(vertices: list, color: str, width: int, dash: str = "solid") -> go.Scatter3d:
    """All 12 edges in ONE trace; None entries break the line between edges."""
    xs, ys, zs = [], [], []
    for a, b in CUBE_EDGES:
        for idx in (a, b):
            xs.append(vertices[idx][0])
            ys.append(vertices[idx][1])
            zs.append(vertices[idx][2])
        xs.append(None)
        ys.append(None)
        zs.append(None)
    return go.Scatter3d(x=xs, y=ys, z=zs, mode="lines",
                        line=dict(color=color, width=width, dash=dash),
                        showlegend=False, hoverinfo="skip")


def make_transform_traces(matrix: list, t: float, vectors: list) -> list:
    """Everything the transformation adds to the scene, at blend `t`."""
    m = blend_matrix(matrix, t)
    moved = [apply_matrix(m, v) for v in CUBE_VERTICES]

    traces = [
        _cube_edges_trace(CUBE_VERTICES, CUBE_ORIGINAL_COLOR, width=2, dash="dash"),
        _cube_edges_trace(moved, CUBE_IMAGE_COLOR, width=4),
        go.Mesh3d(
            x=[p[0] for p in moved], y=[p[1] for p in moved], z=[p[2] for p in moved],
            i=[tri[0] for tri in CUBE_TRIANGLES],
            j=[tri[1] for tri in CUBE_TRIANGLES],
            k=[tri[2] for tri in CUBE_TRIANGLES],
            color=CUBE_IMAGE_COLOR, opacity=0.15, showlegend=False, hoverinfo="skip",
        ),
    ]

    origin = {"x": 0, "y": 0, "z": 0}
    for column, color in enumerate(BASIS_COLORS):
        tip = tuple(m[r][column] for r in range(3))   # column c of the matrix = image of basis vector c
        traces += make_vector_traces(origin, _as_point_dict(tip), color)

    for vector in vectors:
        start = apply_matrix(m, _point(vector["start"]))
        end = apply_matrix(m, _point(vector["end"]))
        traces += make_vector_traces(_as_point_dict(start), _as_point_dict(end), IMAGE_VECTOR_COLOR)

    return traces


def _transform_extent(matrix: list, vectors: list) -> int:
    """Axis extent needed for the FULL transformation (t=1). Using the final
    matrix, not the blended one, keeps the axes from jumping as you drag the slider."""
    points = [apply_matrix(matrix, v) for v in CUBE_VERTICES]
    for vector in vectors:
        points.append(apply_matrix(matrix, _point(vector["start"])))
        points.append(apply_matrix(matrix, _point(vector["end"])))
    return math.ceil(max(abs(c) for p in points for c in p) * 1.2)

def _transform_patch_values(matrix: list, t: float, vectors: list) -> list:
    """Coordinates for the DYNAMIC transform traces only, in the same order
    make_transform_traces builds them — skipping the dashed original cube,
    which never changes with t."""
    m = blend_matrix(matrix, t)
    moved = [apply_matrix(m, v) for v in CUBE_VERTICES]
    updates = []

    edge_pts = []
    for a, b in CUBE_EDGES:
        edge_pts += [moved[a], moved[b], None]
    updates.append({"x": [p[0] if p else None for p in edge_pts],
                    "y": [p[1] if p else None for p in edge_pts],
                    "z": [p[2] if p else None for p in edge_pts]})

    updates.append({"x": [p[0] for p in moved], "y": [p[1] for p in moved], "z": [p[2] for p in moved]})

    origin = (0, 0, 0)
    for column in range(3):
        tip = tuple(m[r][column] for r in range(3))
        shaft_end = tuple(tip[i] * (1 - HEAD_FRACTION) for i in range(3))
        updates.append({"x": [origin[0], shaft_end[0]], "y": [origin[1], shaft_end[1]], "z": [origin[2], shaft_end[2]]})
        updates.append({"x": [tip[0]], "y": [tip[1]], "z": [tip[2]], "u": [tip[0]], "v": [tip[1]], "w": [tip[2]]})

    for vector in vectors:
        start, end = apply_matrix(m, _point(vector["start"])), apply_matrix(m, _point(vector["end"]))
        shaft_end = tuple(start[i] + (end[i] - start[i]) * (1 - HEAD_FRACTION) for i in range(3))
        updates.append({"x": [start[0], shaft_end[0]], "y": [start[1], shaft_end[1]], "z": [start[2], shaft_end[2]]})
        updates.append({"x": [end[0]], "y": [end[1]], "z": [end[2]],
                        "u": [end[0]-start[0]], "v": [end[1]-start[1]], "w": [end[2]-start[2]]})
    return updates


def _transform_trace_offset(vectors: list, spans: list) -> int:
    """Index of the first DYNAMIC transform trace in the figure's trace list."""
    span_count = sum(len(make_span_traces(independent_basis(s["vectors"]), 1, s["color"])) for s in spans)
    return span_count + 2 * len(vectors) + 1   # +1 skips the static dashed cube trace

SIDEBAR_STYLE = {
    "flex-shrink": "0", "display": "flex", "flex-direction": "column",
    "gap": "10px", "transition": "width 0.2s", "padding-top": "20px",
    "padding-left": "10px", "padding-right": "10px",
    "box-shadow": "2px 0 12px rgba(0, 0, 0, 0.5)", "background-color": "gray",
}

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = dash.Dash(__name__, assets_folder="../assets")
app.title = "Vector Space Visualizer"

initial_vector = build_vector(1, 1, 1)

SIDEBAR_STYLE = {
    "flex-shrink": "0", "display": "flex", "flex-direction": "column",
    "gap": "10px", "transition": "width 0.2s", "padding-top": "20px",
    "padding-left": "10px", "padding-right": "10px",
    "box-shadow": "2px 0 12px rgba(0, 0, 0, 0.5)", "background-color": "gray",
}

app.layout = html.Div(
    style={"height": "100vh", "display": "flex", "flex-direction": "column"},
    children=[
        html.Div(
            style={"display": "flex", "gap": "20px", "flex": "1", "min-height": "0"},
            children=[
                html.Div(
                    id="sidebar",
                    style={**SIDEBAR_STYLE, "width": "60px"},
                    children=[
                        dcc.Store(id="vectors-store", data=[initial_vector]),
                        dcc.Store(id="span-vectors-store", data=[]),
                        dcc.Store(id="transform-store", data=None),
                        dcc.Interval(id="blend-interval", interval=25, n_intervals=0, disabled=True),
                        dcc.Store(id="sidebar-state", data={
                            "add_vector_open": False, "span_open": False, "transform_open": False,
                        }),

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

                        html.Button("+ Transform", id="toggle-transform-button", n_clicks=0),
                        html.Div(
                            id="transform-fields",
                            style={"display": "none", "flex-direction": "column", "gap": "10px", "margin-top": "10px"},
                            children=[
                                matrix_input_grid(),
                                html.Div(
                                    style={"display": "flex", "gap": "10px"},
                                    children=[
                                        html.Button("Apply", id="apply-transform-button", n_clicks=0),
                                        html.Button("Reset", id="reset-transform-button", n_clicks=0),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    style={"flex-grow": "1", "min-width": "0", "min-height": "0"},
                    children=[
                        dcc.Graph(
                            id="vector-plot",
                            figure=make_scene_figure([initial_vector]),
                            style={"height": "100%"},
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            id="cards-panel",
            style={
                "display": "grid", "grid-template-columns": "repeat(auto-fill, minmax(220px, 1fr))",
                "gap": "16px", "padding": "16px", "box-shadow": "60px 0 12px rgba(0, 0, 0, 0.3)",
                "background-color": "#f5f5f7", "position": "relative", "z-index": "1",
                "flex-shrink": "0", "max-height": "40vh", "overflow-y": "auto",
            },
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
                html.Div(
                    id="transform-card",
                    style={"display": "none"},
                    children=[
                        html.Strong("Transformation"),
                        html.Div(id="transform-info", style={"margin": "10px 0", "font-size": "13px"}),
                        html.Label("Blend: identity → matrix", style={"font-size": "13px"}),
                        dcc.Slider(id="blend-slider", min=0, max=1, step=0.01, value=1,
                                  marks={0: "0", 1: "1"}, updatemode="drag"),
                    ],
                ),
            ],
        ),
    ],
)

def _section_style(is_open: bool) -> dict:
    return {"display": "flex" if is_open else "none", "flex-direction": "column",
            "gap": "10px", "margin-top": "10px"}

@app.callback(
    dash.Output("sidebar", "style"),
    dash.Output("add-vector-fields", "style"),
    dash.Output("span-fields", "style"),
    dash.Output("transform-fields", "style"),
    dash.Output("sidebar-state", "data"),
    dash.Input("toggle-add-vector-button", "n_clicks"),
    dash.Input("toggle-span-button", "n_clicks"),
    dash.Input("toggle-transform-button", "n_clicks"),
    dash.State("sidebar-state", "data"),
    prevent_initial_call=True,
)
def toggle_sidebar_sections(add_clicks, span_clicks, transform_clicks, state):
    key = {
        "toggle-add-vector-button": "add_vector_open",
        "toggle-span-button": "span_open",
        "toggle-transform-button": "transform_open",
    }.get(dash.ctx.triggered_id)
    if key:
        state[key] = not state[key]

    any_open = any(state.values())
    sidebar_style = {**SIDEBAR_STYLE, "width": "260px" if any_open else "60px"}
    return (sidebar_style,
            _section_style(state["add_vector_open"]),
            _section_style(state["span_open"]),
            _section_style(state["transform_open"]),
            state)

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

ANIMATION_STEP = 0.02

@app.callback(
    dash.Output("transform-store", "data"),
    dash.Output("blend-slider", "value"),
    dash.Output("blend-interval", "disabled"),
    dash.Output("blend-interval", "n_intervals"),
    *[dash.Output(cid, "value") for cid in MATRIX_INPUT_IDS],
    dash.Input("apply-transform-button", "n_clicks"),
    dash.Input("reset-transform-button", "n_clicks"),
    *[dash.State(cid, "value") for cid in MATRIX_INPUT_IDS],
    prevent_initial_call=True,
)
def handle_transform(apply_clicks, reset_clicks, *values):
    if dash.ctx.triggered_id == "reset-transform-button":
        identity_values = [1 if r == c else 0 for r in range(3) for c in range(3)]
        return (None, 1, True, 0, *identity_values)          # stop the animation

    if dash.ctx.triggered_id == "apply-transform-button":
        flat = [v or 0 for v in values]
        matrix = [flat[0:3], flat[3:6], flat[6:9]]
        return (matrix, 0, False, 0, *[dash.no_update] * 9)  # start at 0, enable interval

    return (dash.no_update,) * 13

@app.callback(
    dash.Output("transform-card", "style"),
    dash.Output("transform-info", "children"),
    dash.Input("transform-store", "data"),
    dash.Input("blend-slider", "value"),
)
def update_transform_card(matrix, blend):
    if not matrix:
        return {"display": "none"}, []

    d = determinant(blend_matrix(matrix, blend))
    lines = [f"Blend: {blend:.2f}", f"Determinant: {d:.2f}"]
    if abs(d) < 0.02:
        lines.append("Volume collapsed")
    elif d < 0:
        lines.append("Orientation flipped")
    return CARD_STYLE, [html.Div(line) for line in lines]

@app.callback(
    dash.Output("blend-slider", "value", allow_duplicate=True),
    dash.Output("blend-interval", "disabled", allow_duplicate=True),
    dash.Input("blend-interval", "n_intervals"),
    dash.State("blend-slider", "value"),
    prevent_initial_call=True,
)
def step_blend_animation(n_intervals, current_blend):
    next_blend = current_blend + ANIMATION_STEP
    if next_blend >= 1:
        return 1, True   # snap to exactly 1, then stop
    return next_blend, False

@app.callback(
    dash.Output("vector-plot", "figure", allow_duplicate=True),
    dash.Input("blend-slider", "value"),
    dash.State("transform-store", "data"),
    dash.State("vectors-store", "data"),
    dash.State("span-vectors-store", "data"),
    dash.State("vector-plot", "figure"),
    prevent_initial_call=True,
)
def patch_blend(blend, transform, vectors, spans, current_figure):
    if not transform:
        return dash.no_update

    offset = _transform_trace_offset(vectors, spans)
    patch_values = _transform_patch_values(transform, blend, vectors)

    # The full rebuild hasn't added the transform traces to the figure yet —
    # skip this tick rather than patch indices that don't exist.
    if offset + len(patch_values) > len(current_figure["data"]):
        return dash.no_update

    patched = Patch()
    for i, fields in enumerate(patch_values):
        for key, value in fields.items():
            patched["data"][offset + i][key] = value
    return patched
    
# ---------------------------------------------------------------------------
# Callback: redraw plot whenever the store changes
# ---------------------------------------------------------------------------
@app.callback(
    dash.Output("vector-plot", "figure"),
    dash.Input("vectors-store", "data"),
    dash.Input("span-vectors-store", "data"),
    dash.Input("transform-store", "data"),
)
def update_plot_from_store(vectors, spans, transform):
    return make_scene_figure(vectors, spans, transform, blend=0)

@app.callback(
    dash.Output("span-cards-container", "children"),
    dash.Input("span-vectors-store", "data"),
)
def update_span_cards(spans: list) -> list:
    return build_span_cards(spans)

if __name__ == "__main__":
    app.run(debug=True)