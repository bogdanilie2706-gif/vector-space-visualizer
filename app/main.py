import dash
from dash import dcc, html
import plotly.graph_objects as go


def make_vector_figure(x: float, y: float, z: float) -> go.Figure:
    """Return a 3D figure with one vector drawn from the origin to (x, y, z)."""
    fig = go.Figure()

    fig.add_trace(
        go.Scatter3d(
            x=[0, x], y=[0, y], z=[0, z],
            mode="lines",
            line=dict(color="royalblue", width=3),
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Cone(
            x=[x], y=[y], z=[z],
            u=[x], v=[y], w=[z],
            sizemode="absolute",
            sizeref=min(abs(x) + abs(y) + abs(z), 0.7),
            anchor="tip",
            colorscale=[[0, "royalblue"], [1, "royalblue"]],
            showscale=False,
        )
    )

    fig.update_layout(
        scene=dict(
            xaxis=dict(range=[-5, 5], title="x"),
            yaxis=dict(range=[-5, 5], title="y"),
            zaxis=dict(range=[-5, 5], title="z"),
            aspectmode="cube",
        ),
        margin=dict(l=0, r=0, t=30, b=0),
    )
    return fig

app = dash.Dash(__name__)
app.title = "Vector Space Visualizer"

def slider_with_label(label: str, component_id: str) -> html.Div:
    """Build one labeled slider (reused for x, y, z so we don't repeat code)."""
    return html.Div(
        children=[
            html.Label(label),
            dcc.Slider(
                id=component_id,
                min=-5, max=5, step=0.1, value=1,
                marks={i: str(i) for i in range(-5, 6)},
                tooltip={"placement": "bottom", "always_visible": True},
            ),
        ],
        style={"margin-bottom": "20px"},
    )


app.layout = html.Div(
    className="app-container",
    children=[
        html.H1("Vector Space Visualizer"),
        html.P("Plot, add, and scale vectors in 2D/3D."),
        dcc.Graph(id="vector-plot", figure=make_vector_figure(1, 1, 1)),
        slider_with_label("x", "slider-x"),
        slider_with_label("y", "slider-y"),
        slider_with_label("z", "slider-z"),
    ],
)


@app.callback(
    dash.Output("vector-plot", "figure"),
    dash.Input("slider-x", "value"),
    dash.Input("slider-y", "value"),
    dash.Input("slider-z", "value"),
)
def update_vector_plot(x: float, y: float, z: float) -> go.Figure:
    """Runs automatically whenever any slider changes; redraws the vector."""
    return make_vector_figure(x, y, z)

if __name__ == "__main__":
    app.run(debug=True)
