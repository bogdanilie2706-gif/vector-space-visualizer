"""
Vector Space Visualizer - Dash app entry point.

Run locally with:
    python app/main.py
"""

import dash
from dash import dcc, html
import plotly.graph_objects as go


def make_empty_figure() -> go.Figure:
    """Return a blank 3D scene with sensible fixed axis ranges."""
    fig = go.Figure()
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

app.layout = html.Div(
    className="app-container",
    children=[
        html.H1("Vector Space Visualizer"),
        html.P("Plot, add, and scale vectors in 2D/3D."),
        dcc.Graph(id="vector-plot", figure=make_empty_figure()),
        # Controls (sliders for vector components) go here in milestone 1.
    ],
)


if __name__ == "__main__":
    app.run(debug=True)
