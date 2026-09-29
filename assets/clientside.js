if (!window.dash_clientside) {
    window.dash_clientside = {};
}

window.dash_clientside.clientside = {
    stepAnimation: function(n_intervals, blend) {
        const ANIMATION_STEP = 0.02;
        let next = blend + ANIMATION_STEP;
        let done = false;
        if (next >= 1) { 
            next = 1; 
            done = true; 
        }
        return [next, done];
    },

    restylePlot: function(blend, transform, vectors, spans) {
        if (!transform) {
            return window.dash_clientside.no_update;
        }
        try {
            const container = document.getElementById("vector-plot");
            const gd = container ? (container.querySelector('.js-plotly-plot') || container) : null;
            if (!gd || !gd.data || !gd._fullData) {
                return window.dash_clientside.no_update;
            }

            const HEAD_FRACTION = 0.3;
            const IDENTITY = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];

            function blendMatrix(m, t) {
                const out = [];
                for (let r = 0; r < 3; r++) {
                    out.push([0, 1, 2].map(c => (1 - t) * IDENTITY[r][c] + t * m[r][c]));
                }
                return out;
            }

            function applyMatrix(m, p) {
                return [0, 1, 2].map(r => m[r][0] * p[0] + m[r][1] * p[1] + m[r][2] * p[2]);
            }

            function asTuple(v) {
                return [v.x || 0, v.y || 0, v.z || 0];
            }

            function cross(a, b) {
                return [
                    a[1] * b[2] - a[2] * b[1],
                    a[2] * b[0] - a[0] * b[2],
                    a[0] * b[1] - a[1] * b[0],
                ];
            }

            function dot(a, b) {
                return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
            }

            function spanTraceCount(vecs) {
                const EPS = 1e-9;
                let basis = [];
                vecs.forEach(raw => {
                    const v = asTuple(raw);
                    if (basis.length === 0) {
                        if (dot(v, v) > EPS) basis.push(v);
                    } else if (basis.length === 1) {
                        const c = cross(basis[0], v);
                        if (dot(c, c) > EPS) basis.push(v);
                    } else if (basis.length === 2) {
                        const triple = dot(cross(basis[0], basis[1]), v);
                        if (Math.abs(triple) > EPS) basis.push(v);
                    }
                });
                return (basis.length === 1 || basis.length === 2) ? 1 : 0;
            }

            let spanCount = 0;
            (spans || []).forEach(s => {
                spanCount += spanTraceCount(s.vectors);
            });

            const TRANSFORM_TRACE_COUNT = 3 + 6 + 2 * vectors.length;
            const expectedTotal = spanCount + 2 * vectors.length + TRANSFORM_TRACE_COUNT;
            if (gd.data.length < expectedTotal) {
                return window.dash_clientside.no_update;
            }

            const m = blendMatrix(transform, blend);
            const cubeVertices = [];
            for (let i = 0; i < 8; i++) {
                cubeVertices.push([i & 1, (i >> 1) & 1, (i >> 2) & 1]);
            }
            const cubeEdges = [];
            for (let i = 0; i < 8; i++) {
                [1, 2, 4].forEach(bit => {
                    if (!(i & bit)) cubeEdges.push([i, i | bit]);
                });
            }
            const moved = cubeVertices.map(v => applyMatrix(m, v));

            let idx = spanCount + 2 * vectors.length + 1;

            const edgeX = [], edgeY = [], edgeZ = [];
            cubeEdges.forEach(([a, b]) => {
                edgeX.push(moved[a][0], moved[b][0], null);
                edgeY.push(moved[a][1], moved[b][1], null);
                edgeZ.push(moved[a][2], moved[b][2], null);
            });
            Plotly.restyle(gd, { x: [edgeX], y: [edgeY], z: [edgeZ] }, [idx]);
            idx++;

            Plotly.restyle(gd, {
                x: [moved.map(p => p[0])],
                y: [moved.map(p => p[1])],
                z: [moved.map(p => p[2])],
            }, [idx]);
            idx++;

            for (let col = 0; col < 3; col++) {
                const tip = [0, 1, 2].map(r => m[r][col]);
                const shaftEnd = tip.map(c => c * (1 - HEAD_FRACTION));
                Plotly.restyle(gd, {
                    x: [[0, shaftEnd[0]]], y: [[0, shaftEnd[1]]], z: [[0, shaftEnd[2]]],
                }, [idx]);
                idx++;
                Plotly.restyle(gd, {
                    x: [[tip[0]]], y: [[tip[1]]], z: [[tip[2]]],
                    u: [[tip[0]]], v: [[tip[1]]], w: [[tip[2]]],
                }, [idx]);
                idx++;
            }

            vectors.forEach(vec => {
                const start = applyMatrix(m, [vec.start.x, vec.start.y, vec.start.z]);
                const end = applyMatrix(m, [vec.end.x, vec.end.y, vec.end.z]);
                const shaftEnd = [0, 1, 2].map(i => start[i] + (end[i] - start[i]) * (1 - HEAD_FRACTION));
                Plotly.restyle(gd, {
                    x: [[start[0], shaftEnd[0]]], y: [[start[1], shaftEnd[1]]], z: [[start[2], shaftEnd[2]]],
                }, [idx]);
                idx++;
                Plotly.restyle(gd, {
                    x: [[end[0]]], y: [[end[1]]], z: [[end[2]]],
                    u: [[end[0] - start[0]]], v: [[end[1] - start[1]]], w: [[end[2] - start[2]]],
                }, [idx]);
                idx++;
            });
        } catch (err) {
            return window.dash_clientside.no_update;
        }
        return window.dash_clientside.no_update;
    }
};