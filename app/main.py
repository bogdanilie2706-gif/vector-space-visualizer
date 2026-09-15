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

def slider_with_label(label: str, component_id: str) -> html.Div:
    """Build one labeled slider (reused for x, y, z so we don't repeat code)."""
    return html.Div(
        children=[
            html.Label(label),
            dcc.Slider(
                id=component_id,
                min=-5, max=5, step=0.1, value=1,
                marks={i: str(i) for i in range(-5, 6)},
                tooltip=dict(placement="bottom", always_visible= True),
            ),
        ],
        style={"margin-bottom": "20px"},
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
                dcc.Input(id="input-x", type="number", placeholder="x", value=0, style={"width": "60px"}),
                dcc.Input(id="input-y", type="number", placeholder="y", value=0, style={"width": "60px"}),
                dcc.Input(id="input-z", type="number", placeholder="z", value=0, style={"width": "60px"}),
                html.Button("Add Vector", id="add-vector-button", n_clicks=0),
            ],
            style={"margin-bottom": "20px"},
        ),
        dcc.Graph(id="vector-plot", figure=make_scene_figure([initial_vector])),
        slider_with_label("x", "slider-x"),
        slider_with_label("y", "slider-y"),
        slider_with_label("z", "slider-z"),
    ],
)

@app.callback(
    dash.Output("vectors-store", "data"),
    dash.Input("add-vector-button", "n_clicks"),
    dash.State("input-x", "value"),
    dash.State("input-y", "value"),
    dash.State("input-z", "value"),
    dash.State("vectors-store", "data"),
    prevent_initial_call=True,
)
def add_vector(n_clicks, x, y, z, current_vectors):
    """Runs only when the button is clicked. Appends the typed vector to the store."""
    new_vector = dict(start=dict(x=0, y=0, z=0), end=dict(x=x, y=y, z=z))
    return current_vectors + [new_vector]

@app.callback(
    dash.Output("vector-plot", "figure"),
    dash.Input("vectors-store", "data"),
)
def update_plot_from_store(vectors: list) -> go.Figure:
    """Runs whenever the vectors-store data changes; redraws every vector."""
    return make_scene_figure(vectors)


if __name__ == "__main__":
    app.run(debug=True)
