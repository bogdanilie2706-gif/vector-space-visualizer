window.dash_clientside = Object.assign({}, window.dash_clientside, {
  clientside: {
    stepAnimation: function(n_intervals, current_blend) {
      const STEP = 0.08;
      let next_blend = current_blend + STEP;
      if (next_blend >= 1.0) {
        return [1.0, true]; // blend = 1.0, interval disabled = true
      }
      return [next_blend, false];
    },

    restylePlot: function(blend, transformData, vectors, spans) {
        if (!transformData || !transformData.matrix) return window.dash_clientside.no_update;

        const matrix = transformData.matrix;
        const eigen_data = transformData.eigen_data || [];
        const HEAD_FRACTION = 0.3;
        const CUBE_VERTICES = [[0,0,0], [1,0,0], [0,1,0], [1,1,0], [0,0,1], [1,0,1], [0,1,1], [1,1,1]];
        const CUBE_EDGES = [[0,1],[0,2],[0,4],[1,3],[1,5],[2,3], [2,6],[3,7],[4,5],[4,6],[5,7],[6,7]];

        const m = [
            [(1 - blend) + blend * matrix[0][0], blend * matrix[0][1], blend * matrix[0][2]],
            [blend * matrix[1][0], (1 - blend) + blend * matrix[1][1], blend * matrix[1][2]],
            [blend * matrix[2][0], blend * matrix[2][1], (1 - blend) + blend * matrix[2][2]]
        ];

        function applyM(p) {
            return [
            m[0][0]*p[0] + m[0][1]*p[1] + m[0][2]*p[2],
            m[1][0]*p[0] + m[1][1]*p[1] + m[1][2]*p[2],
            m[2][0]*p[0] + m[2][1]*p[1] + m[2][2]*p[2]
            ];
        }

        let spanTraceCount = 0;
        if (spans) {
            spans.forEach(s => {
            const dim = s.dim !== undefined ? s.dim : (s.vectors ? s.vectors.length : 0);
            if (dim === 1 || dim === 2) spanTraceCount += 1;
            });
        }
        
        const vectorTraceCount = (vectors ? vectors.length : 0) * 2;
        let traceIdx = spanTraceCount + vectorTraceCount + 1;

        const graphDiv = document.querySelector('.js-plotly-plot');
        if (!graphDiv) return window.dash_clientside.no_update;

        const moved = CUBE_VERTICES.map(applyM);
        const edgeXs = [], edgeYs = [], edgeZs = [];
        CUBE_EDGES.forEach(e => {
            edgeXs.push(moved[e[0]][0], moved[e[1]][0], null);
            edgeYs.push(moved[e[0]][1], moved[e[1]][1], null);
            edgeZs.push(moved[e[0]][2], moved[e[1]][2], null);
        });

        // --- BATCHING ARRAYS ---
        const scatterIdx = [], sX = [], sY = [], sZ = [];
        const coneIdx = [], cX = [], cY = [], cZ = [], cU = [], cV = [], cW = [];

        function addScatter(idx, x, y, z) {
            scatterIdx.push(idx); sX.push(x); sY.push(y); sZ.push(z);
        }
        function addCone(idx, x, y, z, u, v, w) {
        // Plotly bug prevention: zero-length Cone traces break the layout and reset zoom
        if (Math.abs(u[0]) < 1e-5 && Math.abs(v[0]) < 1e-5 && Math.abs(w[0]) < 1e-5) {
          u[0] = 1e-5; 
        }
        coneIdx.push(idx); cX.push(x); cY.push(y); cZ.push(z); cU.push(u); cV.push(v); cW.push(w);
      }

        // 1. Cube edges & Mesh
        addScatter(traceIdx++, edgeXs, edgeYs, edgeZs);
        addScatter(traceIdx++, moved.map(p => p[0]), moved.map(p => p[1]), moved.map(p => p[2]));

        // 2. Basis Vectors
        for (let col = 0; col < 3; col++) {
            const tip = [m[0][col], m[1][col], m[2][col]];
            const shaftEnd = [tip[0]*(1-HEAD_FRACTION), tip[1]*(1-HEAD_FRACTION), tip[2]*(1-HEAD_FRACTION)];
            addScatter(traceIdx++, [0, shaftEnd[0]], [0, shaftEnd[1]], [0, shaftEnd[2]]);
            addCone(traceIdx++, [tip[0]], [tip[1]], [tip[2]], [tip[0]], [tip[1]], [tip[2]]);
        }

        // 3. User Vectors
        if (vectors) {
            vectors.forEach(v => {
            const s = applyM([v.start.x, v.start.y, v.start.z]);
            const e = applyM([v.end.x, v.end.y, v.end.z]);
            const shaftEnd = [
                s[0] + (e[0]-s[0])*(1-HEAD_FRACTION),
                s[1] + (e[1]-s[1])*(1-HEAD_FRACTION),
                s[2] + (e[2]-s[2])*(1-HEAD_FRACTION)
            ];
            addScatter(traceIdx++, [s[0], shaftEnd[0]], [s[1], shaftEnd[1]], [s[2], shaftEnd[2]]);
            addCone(traceIdx++, [e[0]], [e[1]], [e[2]], [e[0]-s[0]], [e[1]-s[1]], [e[2]-s[2]]);
            });
        }

        // 4. Eigenvectors
        if (eigen_data && eigen_data.length > 0) {
            let extent = 5;
            if (graphDiv.layout && graphDiv.layout.scene && graphDiv.layout.scene.xaxis && graphDiv.layout.scene.xaxis.range) {
            extent = Math.max(Math.abs(graphDiv.layout.scene.xaxis.range[0]), Math.abs(graphDiv.layout.scene.xaxis.range[1]));
            }

            eigen_data.forEach(item => {
            const v = item.vec;
            const v_trans = applyM(v);
            
            // Draw the static line based on the original vector 'v'
            let max_c = Math.max(Math.abs(v[0]), Math.abs(v[1]), Math.abs(v[2]));
            let t = max_c > 1e-9 ? (extent * 0.99) / max_c : 0;
            
            addScatter(traceIdx++, [-t*v[0], t*v[0]], [-t*v[1], t*v[1]], [-t*v[2], t*v[2]]);
            
            // Draw the dynamic arrow based on the transformed vector 'v_trans'
            const shaftEnd = [v_trans[0]*(1-HEAD_FRACTION), v_trans[1]*(1-HEAD_FRACTION), v_trans[2]*(1-HEAD_FRACTION)];
            addScatter(traceIdx++, [0, shaftEnd[0]], [0, shaftEnd[1]], [0, shaftEnd[2]]);
            
            addCone(traceIdx++, [v_trans[0]], [v_trans[1]], [v_trans[2]], [v_trans[0]], [v_trans[1]], [v_trans[2]]);
            });
        }

        // --- EXECUTE BATCH CALLS ---
        if (scatterIdx.length > 0) {
            Plotly.restyle(graphDiv, {x: sX, y: sY, z: sZ}, scatterIdx);
        }
        if (coneIdx.length > 0) {
            Plotly.restyle(graphDiv, {x: cX, y: cY, z: cZ, u: cU, v: cV, w: cW}, coneIdx);
        }

        return window.dash_clientside.no_update;
    }
  }
});