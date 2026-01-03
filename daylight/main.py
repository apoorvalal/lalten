# app.py
# pip install fasthtml numpy
# run: python app.py
# (then open http://127.0.0.1:8000)

from fasthtml.common import *
import numpy as np
import os

# Configuration for deployment
BASE_PATH = "/daylight"
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8752"))

app = FastHTML()

# -----------------------------
# Daylight model (simple, fast)
# -----------------------------
EPS_DEG = 23.439281  # obliquity
H0_DEG = -0.833  # "standard" sunrise altitude (refraction + solar radius)


def declination_rad(day_of_year: float) -> float:
    # crude but good: declination as sine wave; phase ~ March equinox around day 80
    eps = np.deg2rad(EPS_DEG)
    return eps * np.sin(2 * np.pi * (day_of_year - 80.0) / 365.0)


def daylight_hours(lat_deg: float, day_of_year: float, h0_deg: float = H0_DEG) -> float:
    phi = np.deg2rad(lat_deg)
    delta = declination_rad(day_of_year)
    h0 = np.deg2rad(h0_deg)

    # cos(H0) formula for arbitrary altitude h0
    sin_phi, cos_phi = np.sin(phi), np.cos(phi)
    sin_del, cos_del = np.sin(delta), np.cos(delta)

    denom = cos_phi * cos_del
    # handle poles / numerical degeneracy
    if abs(denom) < 1e-12:
        # at exact poles: either 0 or 24 depending on sign(sin_phi*sin_del - sin(h0))
        alt_noon = sin_phi * sin_del
        return 24.0 if alt_noon >= np.sin(h0) else 0.0

    cosH = (np.sin(h0) - sin_phi * sin_del) / denom

    # clamp & polar day/night
    if cosH <= -1.0:
        return 24.0
    if cosH >= 1.0:
        return 0.0

    H = np.arccos(cosH)  # radians
    return (24.0 / np.pi) * H


def daylight_curve_and_derivative(lat_deg: float, n_days: int = 366):
    days = np.linspace(0.0, 365.0, n_days)
    D = np.array([daylight_hours(lat_deg, d) for d in days], dtype=float)

    # derivative wrt day-of-year (hours/day), using numpy gradient on uniform grid
    dD = np.gradient(D, days)
    return days, D, dD


# -----------------------------
# API endpoints
# -----------------------------
@app.get(f"{BASE_PATH}/api/daylight")
def api_daylight(lat: float, lon: float, day: float):
    # lon currently unused (day length depends only on latitude in this model)
    days, D, dD = daylight_curve_and_derivative(lat)
    sel = float(daylight_hours(lat, day))
    return {
        "lat": lat,
        "lon": lon,
        "day": day,
        "selected_daylight_hours": sel,
        "days": days.tolist(),
        "daylight_hours": D.tolist(),
        "derivative_hours_per_day": dD.tolist(),
    }


# -----------------------------
# UI
# -----------------------------
MONTH_TICKS = [
    ("Jan", 0),
    ("Feb", 31),
    ("Mar", 59),
    ("Apr", 90),
    ("May", 120),
    ("Jun", 151),
    ("Jul", 181),
    ("Aug", 212),
    ("Sep", 243),
    ("Oct", 273),
    ("Nov", 304),
    ("Dec", 334),
]


@app.get(BASE_PATH)
@app.get(f"{BASE_PATH}/")
def index():
    # Everything is in one page: Three.js globe + range slider + Plotly charts.
    # Click globe -> fetch /api/daylight -> render plots + vline at selected day.
    return Html(
        Head(
            Title("Daylight Explorer"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Style("""
                html, body { height: 100%; margin: 0; overflow: hidden; }
                #wrap { display: grid; grid-template-columns: 1.2fr 1fr; height: 100vh; }
                #left { position: relative; overflow: hidden; background: #0b1020; }
                #right { overflow: auto; padding: 12px; font-family: ui-sans-serif, system-ui; }
                #globe { width: 100%; height: 100%; display: block; }
                #hud { position: absolute; left: 12px; bottom: 12px; right: 12px;
                       background: rgba(0,0,0,0.55); color: #fff; padding: 10px 12px;
                       border-radius: 10px; backdrop-filter: blur(6px); }
                #row { display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: center; }
                #slider { width: 100%; }
                #meta { font-size: 12px; opacity: 0.9; }
                .card { border: 1px solid rgba(0,0,0,0.12); border-radius: 12px; padding: 10px; margin-bottom: 12px; }
                .title { font-size: 14px; font-weight: 600; margin: 0 0 6px 0; }
                #plot1, #plot2 { height: 320px; }
                #header { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
                #banner { background: linear-gradient(135deg, #e8f4f8 0%, #d4e8f0 100%);
                          border-radius: 12px; padding: 14px; margin-bottom: 12px;
                          font-size: 13px; line-height: 1.5; color: #2c4a5a; }
                .katex-eq { text-align: center; margin: 10px 0; overflow-x: auto; }
            """),
            # JS deps via CDN
            Script(
                src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
            ),
            Script(
                src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.30.0/plotly.min.js"
            ),
            Link(
                rel="stylesheet",
                href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css",
            ),
            Script(src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"),
        ),
        Body(
            Div(
                Div(
                    Canvas(id="globe"),
                    Div(
                        Div(
                            Input(
                                id="slider",
                                type="range",
                                min="0",
                                max="365",
                                value="0",
                                step="1",
                                list="monthticks",
                            ),
                            Button("Reset view", id="resetBtn"),
                            id="row",
                        ),
                        Datalist(
                            *[Option(label=m, value=str(d)) for (m, d) in MONTH_TICKS],
                            id="monthticks",
                        ),
                        Div(
                            id="meta",
                            children="Click the globe to pick a location. Drag slider for day-of-year.",
                        ),
                        id="hud",
                    ),
                    id="left",
                ),
                Div(
                    Div("Daylight Explorer", id="header"),
                    Div(
                        "Visualize how daylight hours vary across the globe throughout the year. "
                        "Click anywhere on the Earth to select a location, then use the slider to "
                        "explore different days. The charts show daylight duration and its rate of change",
                        id="banner",
                    ),
                    Div(
                        P("Daylight length vs day-of-year", className="title"),
                        Div(id="plot1"),
                        className="card",
                    ),
                    Div(
                        P(
                            "Rate of change (hours gained/lost per day)",
                            className="title",
                        ),
                        Div(id="plot2"),
                        className="card",
                    ),
                    Div(id="readout", className="card"),
                    Div(
                        P(Strong("Mathematical Explanation"), className="title"),
                        Div(
                            P(Strong("Solar Declination")),
                            P(
                                "The solar declination δ is the angle between the Sun and the celestial equator. "
                                "It varies throughout the year due to Earth's axial tilt (obliquity ε ≈ 23.44°):"
                            ),
                            Div(id="eq0", className="katex-eq"),
                            P(
                                "where N is the day of year. The phase shift of 80 days places the zero-crossing "
                                "near the March equinox (day ~80)."
                            ),
                            Hr(),
                            P(Strong("Hour Angle at Sunrise/Sunset")),
                            P(
                                "The hour angle H measures time from solar noon in angular units (15°/hour). "
                                "At sunrise and sunset, the Sun is at altitude h₀ = −0.833° "
                                "(accounting for atmospheric refraction and the Sun's radius)."
                            ),
                            P(
                                "From spherical trigonometry, the solar altitude α satisfies:"
                            ),
                            Div(id="eq1a", className="katex-eq"),
                            P("Setting α = h₀ and solving for the hour angle H₀:"),
                            Div(id="eq1", className="katex-eq"),
                            P("The ± solutions give sunrise (−H₀) and sunset (+H₀)."),
                            Hr(),
                            P(Strong("Daylight Duration")),
                            P(
                                "Since the Sun traverses 2H₀ radians from sunrise to sunset, and Earth rotates 2π radians in 24 hours:"
                            ),
                            Div(id="eq2", className="katex-eq"),
                            P(
                                "Polar day (24h) occurs when cos(H₀) ≤ −1; polar night (0h) when cos(H₀) ≥ 1."
                            ),
                            Hr(),
                            P(Strong("Rate of Change")),
                            P(
                                "The derivative dD/dN (hours gained or lost per day) is computed via centered finite difference:"
                            ),
                            Div(id="eq4", className="katex-eq"),
                            P(
                                "This rate peaks near the equinoxes and approaches zero near the solstices."
                            ),
                            id="explain",
                        ),
                        className="card",
                    ),
                    id="right",
                ),
                id="wrap",
            ),
            Script("""
                // ---------- Globe setup (plain Three.js sphere) ----------
                var canvas = document.getElementById('globe');
                var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
                renderer.setPixelRatio(window.devicePixelRatio);

                var scene = new THREE.Scene();
                scene.background = new THREE.Color(0x0b1020);

                var camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
                camera.position.set(0, 0, 3);

                // Lights
                var ambient = new THREE.AmbientLight(0xffffff, 0.6);
                scene.add(ambient);
                var dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
                dirLight.position.set(5, 3, 5);
                scene.add(dirLight);

                // Earth sphere
                var geometry = new THREE.SphereGeometry(1, 64, 64);
                var textureLoader = new THREE.TextureLoader();
                var earthTexture = textureLoader.load('https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg');
                var bumpTexture = textureLoader.load('https://unpkg.com/three-globe/example/img/earth-topology.png');

                var material = new THREE.MeshPhongMaterial({
                    map: earthTexture,
                    bumpMap: bumpTexture,
                    bumpScale: 0.02
                });
                var globe = new THREE.Mesh(geometry, material);
                // Start facing North America (approx -100 deg longitude)
                globe.rotation.y = Math.PI * 0.1;
                scene.add(globe);

                function resize() {
                    var w = canvas.clientWidth;
                    var h = canvas.clientHeight;
                    renderer.setSize(w, h, false);
                    camera.aspect = w / h;
                    camera.updateProjectionMatrix();
                }
                window.addEventListener('resize', resize);
                resize();

                // Drag to rotate
                var isDragging = false;
                var didDrag = false;
                var prevMouse = { x: 0, y: 0 };

                canvas.addEventListener('mousedown', function(evt) {
                    isDragging = true;
                    didDrag = false;
                    prevMouse.x = evt.clientX;
                    prevMouse.y = evt.clientY;
                });

                canvas.addEventListener('mousemove', function(evt) {
                    if (!isDragging) return;
                    var dx = evt.clientX - prevMouse.x;
                    var dy = evt.clientY - prevMouse.y;
                    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) didDrag = true;
                    globe.rotation.y += dx * 0.005;
                    globe.rotation.x += dy * 0.005;
                    // Clamp vertical rotation
                    globe.rotation.x = Math.max(-Math.PI/2, Math.min(Math.PI/2, globe.rotation.x));
                    prevMouse.x = evt.clientX;
                    prevMouse.y = evt.clientY;
                });

                canvas.addEventListener('mouseup', function() { isDragging = false; });
                canvas.addEventListener('mouseleave', function() { isDragging = false; });

                // Render loop (no auto-rotate)
                function animate() {
                    renderer.render(scene, camera);
                    requestAnimationFrame(animate);
                }
                animate();

                document.getElementById('resetBtn').onclick = function() {
                    camera.position.set(0, 0, 3);
                    globe.rotation.set(0, Math.PI * 0.6, 0);
                };

                // ---------- Picking lat/lon ----------
                var raycaster = new THREE.Raycaster();
                var mouse = new THREE.Vector2();
                var selected = { lat: 0, lon: 0, day: 0 };

                function fetchAndPlot() {
                    var url = '/daylight/api/daylight?lat=' + encodeURIComponent(selected.lat) +
                              '&lon=' + encodeURIComponent(selected.lon) +
                              '&day=' + encodeURIComponent(selected.day);

                    fetch(url)
                        .then(function(res) { return res.json(); })
                        .then(function(data) {
                            var days = data.days;
                            var D = data.daylight_hours;
                            var dD = data.derivative_hours_per_day;
                            var x0 = data.day;

                            // Plot 1: daylight (fixed Y: 0-24)
                            var trace1 = { x: days, y: D, type: 'scatter', mode: 'lines', name: 'Daylight (h)' };
                            var layout1 = {
                                margin: { l: 45, r: 10, t: 10, b: 35 },
                                xaxis: { title: 'day of year', range: [0, 365] },
                                yaxis: { title: 'hours', range: [0, 24] },
                                shapes: [{
                                    type: 'line',
                                    x0: x0, x1: x0, y0: 0, y1: 24,
                                    line: { color: 'rgba(0,0,0,0.3)', width: 1, dash: 'dot' }
                                }]
                            };
                            Plotly.newPlot('plot1', [trace1], layout1, { displayModeBar: false, responsive: true });

                            // Plot 2: derivative (fixed Y: -0.2 to 0.2)
                            var trace2 = { x: days, y: dD, type: 'scatter', mode: 'lines', name: 'dD/d(day)' };
                            var layout2 = {
                                margin: { l: 45, r: 10, t: 10, b: 35 },
                                xaxis: { title: 'day of year', range: [0, 365] },
                                yaxis: { title: 'hours/day', range: [-0.2, 0.2] },
                                shapes: [{
                                    type: 'line',
                                    x0: x0, x1: x0, y0: -0.2, y1: 0.2,
                                    line: { color: 'rgba(0,0,0,0.3)', width: 1, dash: 'dot' }
                                }]
                            };
                            Plotly.newPlot('plot2', [trace2], layout2, { displayModeBar: false, responsive: true });

                            // Readout
                            var readout = document.getElementById('readout');
                            readout.innerHTML =
                                '<div style="font-weight:600; margin-bottom:6px;">Current Selection</div>' +
                                '<div>Latitude: ' + data.lat.toFixed(2) + ', Longitude: ' + data.lon.toFixed(2) + '</div>' +
                                '<div>Day of year: ' + data.day.toFixed(0) + '</div>' +
                                '<div>Daylight: ' + data.selected_daylight_hours.toFixed(2) + ' hours</div>';
                        });
                }

                // ---------- Math explanation (KaTeX) ----------
                try {
                    katex.render("\\\\delta(N) = \\\\varepsilon \\\\sin\\\\left(\\\\frac{2\\\\pi}{365}(N-80)\\\\right)", document.getElementById('eq0'), {displayMode: true});
                    katex.render("\\\\sin\\\\alpha = \\\\sin\\\\phi\\\\sin\\\\delta + \\\\cos\\\\phi\\\\cos\\\\delta\\\\cos H", document.getElementById('eq1a'), {displayMode: true});
                    katex.render("\\\\cos H_0 = \\\\frac{\\\\sin h_0 - \\\\sin\\\\phi\\\\sin\\\\delta}{\\\\cos\\\\phi\\\\cos\\\\delta}", document.getElementById('eq1'), {displayMode: true});
                    katex.render("D = \\\\frac{24}{\\\\pi}\\\\, H_0 = \\\\frac{24}{\\\\pi}\\\\arccos\\\\left(\\\\frac{\\\\sin h_0 - \\\\sin\\\\phi\\\\sin\\\\delta}{\\\\cos\\\\phi\\\\cos\\\\delta}\\\\right)", document.getElementById('eq2'), {displayMode: true});
                    katex.render("\\\\frac{dD}{dN} \\\\approx \\\\frac{D(N+1) - D(N-1)}{2}", document.getElementById('eq4'), {displayMode: true});
                } catch(e) {
                    console.error('KaTeX error:', e);
                }

                // slider
                var slider = document.getElementById('slider');
                slider.addEventListener('input', function() {
                    selected.day = parseFloat(slider.value);
                    fetchAndPlot();
                });

                // globe click (only if not dragging)
                canvas.addEventListener('click', function(evt) {
                    if (didDrag) return;

                    var rect = canvas.getBoundingClientRect();
                    mouse.x = ((evt.clientX - rect.left) / rect.width) * 2 - 1;
                    mouse.y = -((evt.clientY - rect.top) / rect.height) * 2 + 1;

                    raycaster.setFromCamera(mouse, camera);
                    var intersects = raycaster.intersectObject(globe);

                    if (intersects.length > 0) {
                        var point = intersects[0].point.clone();
                        globe.worldToLocal(point);

                        // Convert to lat/lon (sphere radius = 1)
                        var lat = Math.asin(point.y) * 180 / Math.PI;
                        var lon = Math.atan2(point.x, point.z) * 180 / Math.PI;

                        selected.lat = lat;
                        selected.lon = lon;
                        selected.day = parseFloat(slider.value);
                        fetchAndPlot();
                    }
                });

                // initial plot at equator, day 0
                fetchAndPlot();
            """),
        ),
    )


if __name__ == "__main__":
    serve(host=HOST, port=PORT)
