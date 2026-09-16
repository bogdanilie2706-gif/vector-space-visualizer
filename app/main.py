import dash
from dash import dcc, html
import plotly.graph_objects as go


def make_vector_traces(start: dict, end: dict, color: str = "royalblue") -> list:
    """Build the traces (shaft + arrowhead) for ONE vector, from `start`
    to `end` — both dicts like {"x": .., "y": .., "z": ..}."""
    head_fraction = 0.3

    dx = end["x"] - start["x"]
    dy = end["y"] - start["y"]
    dz = end["z"] - start["z"]

    # Shaft stops short of the tip (same idea as before, now relative
    # to the start point instead of assuming it's the origin).
    shaft_end_x = start["x"] + dx * (1 - head_fraction)
    shaft_end_y = start["y"] + dy * (1 - head_fraction)
    shaft_end_z = start["z"] + dz * (1 - head_fraction)

    shaft = go.Scatter3d(
        x=[start["x"], shaft_end_x],
        y=[start["y"], shaft_end_y],
        z=[start["z"], shaft_end_z],
        mode="lines",
        line=dict(color=color, width=6),
        showlegend=False,
    )

    arrowhead = go.Cone(
        x=[end["x"]], y=[end["y"]], z=[end["z"]],
        u=[dx], v=[dy], w=[dz],
        sizemode="scaled",
        sizeref=head_fraction,
        anchor="tip",
        colorscale=[[0, color], [1, color]],
        showscale=False,
    )

    return [shaft, arrowhead]


def make_scene_figure(vectors: list) -> go.Figure:
    """Build the full 3D figure from a list of vectors.
    Each vector is a dict like {"start": {...}, "end": {...}}."""
    fig = go.Figure()

    for vector in vectors:
        traces = make_vector_traces(vector["start"], vector["end"])
        for trace in traces:
            fig.add_trace(trace)

    fig.update_layout(
        scene=dict(
            xaxis=dict(range=[-5, 5], title="x"),
            yaxis=dict(range=[-5, 5], title="y"),
            zaxis=dict(range=[-5, 5], title="z"),
            aspectmode="cube",
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        uirevision="constant",  # keeps camera angle/zoom stable across re-renders
    )
    return fig

def vector_slider_group(index: int, x: float, y: float, z: float) -> html.Div:
    """Build one set of x/y/z sliders for the vector at `index` in the
    store. Range is centered on the vector's current value, ±5."""
    def make_slider(axis: str, value: float) -> html.Div:
        return html.Div(
            children=[
                html.Label(f"Vector {index + 1} - {axis}", style={"font-size": "13px"}),
                dcc.Slider(
                    id={"type": "vector-slider", "axis": axis, "index": index},
                    min=value - 5, max=value + 5, step=0.1, value=value,
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ],
            style={"margin-bottom": "10px"},
        )

    return html.Div(
        children=[make_slider("x", x), make_slider("y", y), make_slider("z", z)],
        style={"padding": "10px", "border": "1px solid #ddd"},
    )

app = dash.Dash(__name__)
app.title = "Vector Space Visualizer"
initial_vector = dict(start=dict(x=0, y=0, z=0), end=dict(x=1, y=1, z=1))
app.layout = html.Div(
    className="app-container",
    children=[
        html.H1("Vector Space Visualizer"),
        html.P("Plot, add, and scale vectors in 2D/3D."),
        dcc.Store(id="vectors-store", data=[initial_vector]),
        html.Div(
            children=[
                html.Button("+ Add Vector", id="toggle-add-vector-button", n_clicks=0),
                html.Div(
                    id="add-vector-fields",
                    style={"display": "none", "gap": "10px", "align-items": "center", "margin-top": "10px"},
                    children=[
                        dcc.Input(id="input-x", type="number", placeholder="x", value=0, style={"width": "60px"}),
                        dcc.Input(id="input-y", type="number", placeholder="y", value=0, style={"width": "60px"}),
                        dcc.Input(id="input-z", type="number", placeholder="z", value=0, style={"width": "60px"}),
                        html.Button("Create Vector", id="add-vector-button", n_clicks=0),
                    ],
                ),
            ],
            style={"margin-bottom": "20px"},
        ),
        dcc.Graph(id="vector-plot", figure=make_scene_figure([initial_vector])),
        html.Div(
            id="sliders-container",
            children=[vector_slider_group(0, 1, 1, 1)],
            style={
                "display": "grid",
                "grid-template-columns": "repeat(auto-fill, minmax(220px, 1fr))",
                "gap": "16px",
            },
        ),
    ],
)

@app.callback(
    dash.Output("add-vector-fields", "style"),
    dash.Input("toggle-add-vector-button", "n_clicks"),
    dash.State("add-vector-fields", "style"),
    prevent_initial_call=True,
)
def toggle_add_vector_fields(n_clicks, current_style):
    is_hidden = current_style.get("display") == "none"
    if is_hidden:
        return {"display": "flex", "gap": "10px", "align-items": "center", "margin-top": "10px"}
    return {"display": "none"}

@app.callback(
    dash.Output("vectors-store", "data"),
    dash.Output("sliders-container", "children"),
    dash.Input("add-vector-button", "n_clicks"),
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
def handle_vector_updates(n_clicks, x_values, y_values, z_values,
                           input_x, input_y, input_z,
                           current_vectors, current_sliders):
    # dash.ctx.triggered_id tells us WHICH Input actually fired this
    # callback — the button, or one of the (many) sliders.
    if dash.ctx.triggered_id == "add-vector-button":
        new_vector = dict(start=dict(x=0, y=0, z=0), end=dict(x=input_x, y=input_y, z=input_z))
        updated_vectors = current_vectors + [new_vector]
        new_index = len(current_vectors)
        new_slider_group = vector_slider_group(new_index, input_x, input_y, input_z)
        updated_sliders = current_sliders + [new_slider_group]
        return updated_vectors, updated_sliders

    # Otherwise, a slider moved. x_values/y_values/z_values are LISTS —
    # one entry per existing vector, in order — because dash.ALL
    # collects the value of every matching slider at once.
    updated_vectors = []
    for i, vector in enumerate(current_vectors):
        updated_vectors.append(
            dict(start=vector["start"], end=dict(x=x_values[i], y=y_values[i], z=z_values[i]))
        )
    # dash.no_update tells Dash "leave this output exactly as it is" —
    # we don't want to touch the sliders themselves on a drag.
    return updated_vectors, dash.no_update

@app.callback(
    dash.Output("vector-plot", "figure"),
    dash.Input("vectors-store", "data"),
)
def update_plot_from_store(vectors: list) -> go.Figure:
    """Runs whenever the vectors-store data changes; redraws every vector."""
    return make_scene_figure(vectors)


if __name__ == "__main__":
    app.run(debug=True)
