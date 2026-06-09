/**
 * shared-charts.js — single source of truth for chart rendering across all PALs catalogues.
 * Both the PRECISE catalogue and the HE2AT catalogue load this file.
 * To fix a chart bug or improve styling, edit only this file.
 *
 * Usage: window.PALsRenderChart(elementId, chartSpec)
 */
(function () {
    const P = [
        '#1A535C', '#4ECDC4', '#E07A5F', '#F2CC8F', '#3D5A73',
        '#6B8E6B', '#B87333', '#6B2737', '#8338ec', '#06d6a0',
    ];

    window.PALsRenderChart = function (elId, spec) {
        const el = document.getElementById(elId);
        if (!el || typeof Plotly === 'undefined') {
            console.warn('PALsRenderChart: Plotly not ready or element missing:', elId);
            return;
        }

        const base = {
            paper_bgcolor: 'white',
            plot_bgcolor:  'rgba(0,0,0,0)',
            font: { family: "'Source Sans 3',sans-serif", size: 11, color: '#3D5A73' },
            title: spec.title
                ? { text: spec.title, font: { size: 13, color: '#2D3436' }, x: 0.05 }
                : undefined,
            margin:     { t: spec.title ? 45 : 20, r: 20, b: 60, l: 65 },
            xaxis:      { title: spec.x_label || '', gridcolor: 'rgba(0,0,0,0.05)', zeroline: false },
            yaxis:      { title: spec.y_label || '', gridcolor: 'rgba(0,0,0,0.05)', zeroline: false },
            showlegend: true,
            legend:     { orientation: 'h', y: -0.25, font: { size: 11 } },
            colorway:   P,
        };

        const isMap = spec.chart_type === 'map';
        const cfg = {
            responsive:             true,
            scrollZoom:             isMap,
            displayModeBar:         isMap,
            modeBarButtonsToRemove: ['toImage', 'sendDataToCloud', 'select2d', 'lasso2d'],
        };

        try {
            let traces = [], layout = { ...base };

            /* ── Box plot ──────────────────────────────────────────────── */
            if (spec.chart_type === 'box') {
                traces = (spec.box_data || []).map((g, i) => ({
                    type: 'box', name: g.name,
                    x:          [g.name],
                    lowerfence: [g.lowerfence ?? g.q1],
                    q1:         [g.q1],
                    median:     [g.median],
                    q3:         [g.q3],
                    upperfence: [g.upperfence ?? g.q3],
                    mean:       g.mean !== undefined ? [g.mean] : undefined,
                    boxmean:    g.mean !== undefined,
                    marker:    { color: P[i % P.length], size: 6 },
                    line:      { color: P[i % P.length] },
                    fillcolor:  P[i % P.length] + '55',
                }));
                layout.boxmode    = 'group';
                layout.showlegend = false;
                layout.xaxis      = { ...layout.xaxis, tickangle: -35 };
                layout.margin     = { t: layout.margin.t, r: 20, b: 90, l: 65 };

            /* ── Heatmap / correlation matrix ──────────────────────────── */
            } else if (spec.chart_type === 'heatmap') {
                const z = spec.z_values || [];
                traces = [{
                    type: 'heatmap', z,
                    x: spec.x_labels, y: spec.y_labels,
                    colorscale: [[0, '#E07A5F'], [0.5, '#f5f5f5'], [1, '#1A535C']],
                    zmid: 0, zmin: -1, zmax: 1,
                    text:         z.map(row => row.map(v => v != null ? v.toFixed(2) : '')),
                    texttemplate: '%{text}',
                    showscale:    true,
                }];
                layout.margin     = { t: 50, r: 100, b: 140, l: 140 };
                layout.xaxis      = { ...layout.xaxis, tickangle: -45 };
                layout.showlegend = false;

            /* ── Geographic map ────────────────────────────────────────── */
            } else if (spec.chart_type === 'map') {
                const validPt = d => d.lat >= -35 && d.lat <= 38 && d.lon >= -20 && d.lon <= 52;
                const raw     = spec.map_data || [];
                const bad     = raw.filter(d => !validPt(d));
                if (bad.length > raw.length * 0.5 && raw.length > 0) {
                    el.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#E07A5F;text-align:center;padding:1rem;font-size:0.85rem;">
                        ⚠️ Map coordinates look incorrect — latitude and longitude may be swapped.<br>
                        Expected: Gambia lat 12–14°N · Kenya lat -5–5° · Mozambique lat -27 to -10°
                    </div>`;
                    return;
                }
                const md       = raw.filter(validPt);
                const hasValue = md.some(d => d.value !== undefined && d.value !== null);
                const hasGroup = md.some(d => d.group);

                if (hasValue && !hasGroup) {
                    traces = [{
                        type: 'scattermapbox', lat: md.map(d => d.lat), lon: md.map(d => d.lon),
                        mode: 'markers',
                        marker: {
                            size:      md.map(d => d.size ? Math.max(6, Math.min(20, Math.sqrt(d.size) * 1.5)) : 8),
                            color:     md.map(d => d.value),
                            colorscale: [[0, '#4ECDC4'], [0.5, '#F2CC8F'], [1, '#E07A5F']],
                            colorbar: {
                                title: { text: spec.color_label || 'Value', side: 'right', font: { size: 11 } },
                                thickness: 12, len: 0.7,
                            },
                            opacity: 0.85,
                        },
                        text: md.map(d => {
                            const v = d.value != null ? d.value.toFixed(2) : '—';
                            const n = d.size ? ` · n=${Math.round(d.size)}` : '';
                            return `<b>${d.label}</b><br>${spec.color_label || 'Value'}: ${v}${n}`;
                        }),
                        hovertemplate: '%{text}<extra></extra>', showlegend: false,
                    }];
                } else {
                    const groups = hasGroup ? [...new Set(md.map(d => d.group))] : ['All'];
                    traces = groups.map((g, i) => {
                        const pts = hasGroup ? md.filter(d => d.group === g) : md;
                        return {
                            type: 'scattermapbox', name: g,
                            lat: pts.map(d => d.lat), lon: pts.map(d => d.lon), mode: 'markers',
                            marker: {
                                size:    pts.map(d => d.size ? Math.max(6, Math.min(20, Math.sqrt(d.size) * 1.5)) : 8),
                                color:   P[i % P.length], opacity: 0.8,
                            },
                            text: pts.map(d => {
                                const v = d.value != null ? ` · ${d.value.toFixed(2)}` : '';
                                const n = d.size ? ` · n=${Math.round(d.size)}` : '';
                                return `<b>${d.label}</b>${v}${n}`;
                            }),
                            hovertemplate: '%{text}<extra></extra>',
                        };
                    });
                }
                const lats = md.map(d => d.lat).filter(Boolean);
                const lons = md.map(d => d.lon).filter(Boolean);
                layout.mapbox     = { style: 'open-street-map',
                    center: { lat: lats.reduce((a,b)=>a+b,0)/(lats.length||1), lon: lons.reduce((a,b)=>a+b,0)/(lons.length||1) },
                    zoom: 4 };
                layout.margin     = { t: spec.title ? 40 : 10, r: 0, b: 0, l: 0 };
                layout.showlegend = hasGroup;
                layout.legend     = { orientation: 'h', y: -0.05, font: { size: 11 } };

            /* ── Forest plot ───────────────────────────────────────────── */
            } else if (spec.chart_type === 'forest') {
                const fd    = spec.forest_data || [];
                const useOR = spec.scale === 'OR';
                const toX   = v => useOR ? Math.exp(v) : v;
                const nullX = useOR ? 1 : 0;
                const sigColor = d => !d.stars ? '#B0BEC5' : d.stars==='*' ? '#4ECDC4' : d.stars==='**' ? '#1A535C' : '#B87333';
                traces = [
                    {
                        type: 'scatter', mode: 'markers',
                        x: fd.map(d => toX(d.coef)), y: fd.map(d => d.variable),
                        error_x: {
                            type: 'data', symmetric: false,
                            array:      fd.map(d => Math.abs(toX(d.ci_upper) - toX(d.coef))),
                            arrayminus: fd.map(d => Math.abs(toX(d.coef) - toX(d.ci_lower))),
                            color: '#1A535C', thickness: 1.5, width: 6,
                        },
                        marker: {
                            symbol: 'square',
                            size:   fd.map(d => d.stars==='***' ? 13 : d.stars ? 11 : 9),
                            color:  fd.map(d => sigColor(d)),
                            line:   { color: fd.map(d => sigColor(d)), width: 1.5 },
                        },
                        text: fd.map(d => {
                            const v  = toX(d.coef).toFixed(3);
                            const lo = toX(d.ci_lower).toFixed(3);
                            const hi = toX(d.ci_upper).toFixed(3);
                            const p  = d.p_value !== undefined ? (d.p_value < 0.001 ? 'p<0.001' : `p=${d.p_value.toFixed(3)}`) : '';
                            return `${v} [${lo}, ${hi}] ${p}`;
                        }),
                        hovertemplate: '<b>%{y}</b><br>%{text}<extra></extra>', showlegend: false,
                    },
                    {   /* null-effect line */
                        type: 'scatter', mode: 'lines',
                        x: [nullX, nullX],
                        y: fd.length ? [fd[0].variable, fd[fd.length-1].variable] : ['',''],
                        line: { color: 'rgba(224,122,95,0.6)', width: 1.5, dash: 'dot' },
                        hoverinfo: 'none', showlegend: false,
                    },
                ];
                layout.xaxis      = { ...layout.xaxis, title: spec.x_label || (useOR ? 'Odds Ratio' : 'Coefficient'), zeroline: false, type: useOR ? 'log' : 'linear' };
                layout.yaxis      = { ...layout.yaxis, title: '', automargin: true };
                layout.margin     = { t: spec.title ? 45 : 20, r: 20, b: 50, l: 180 };
                layout.showlegend = false;

            /* ── Scatter ───────────────────────────────────────────────── */
            } else if (spec.chart_type === 'scatter') {
                traces = (spec.scatter_data || []).map((s, i) => ({
                    type: 'scatter', mode: 'markers', name: s.name,
                    x: s.x, y: s.y,
                    marker: { color: P[i % P.length], size: 5, opacity: 0.6 },
                }));

            /* ── Pie / Doughnut ────────────────────────────────────────── */
            } else if (spec.chart_type === 'pie' || spec.chart_type === 'doughnut') {
                const ds = (spec.datasets || [])[0] || {};
                traces = [{
                    type: 'pie', labels: spec.labels || [], values: ds.data || [],
                    hole: spec.chart_type === 'doughnut' ? 0.42 : 0,
                    marker: { colors: P },
                    textinfo: 'label+percent', hoverinfo: 'label+value+percent',
                }];
                layout.showlegend = true;
                layout.margin     = { t: 45, r: 20, b: 20, l: 20 };

            /* ── Bar / Line ────────────────────────────────────────────── */
            } else {
                const isLine = spec.chart_type === 'line';
                const single = !spec.datasets || spec.datasets.length === 1;
                traces = (spec.datasets || []).map((ds, i) => ({
                    type: isLine ? 'scatter' : 'bar',
                    mode: isLine ? 'lines+markers' : undefined,
                    name: ds.label, x: spec.labels || [], y: ds.data || [],
                    marker: {
                        color: single
                            ? (spec.labels || []).map((_, j) => P[j % P.length])
                            : P[i % P.length],
                    },
                    line: isLine ? { color: P[i % P.length], width: 2.5 } : undefined,
                }));
                if (!isLine) layout.barmode = 'group';
            }

            Plotly.newPlot(el, traces, layout, cfg);

        } catch (e) {
            console.error('PALsRenderChart error:', e, spec);
        }
    };
})();
