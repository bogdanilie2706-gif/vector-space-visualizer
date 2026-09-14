# Vector Space Visualizer

An interactive tool for exploring vectors, spans, and linear transformations in 2D/3D — built with [Dash](https://dash.plotly.com/) and Plotly.

## Status

Work in progress. Milestone 1 (core vector plotting) in progress.

## Planned features

- [ ] Plot 2D/3D vectors interactively, with addition and scalar multiplication
- [ ] Visualize the span of a set of vectors
- [ ] Apply linear transformations (matrices) and watch the space morph in real time
- [ ] Highlight eigenvectors/eigenvalues for a given transformation
- [ ] (Stretch) PCA projection demo

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python app/main.py
```

Then open the local URL Dash prints in your terminal (usually `http://127.0.0.1:8050`).
