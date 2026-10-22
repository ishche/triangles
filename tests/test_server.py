import json
import threading
import urllib.error
import urllib.request

import pytest

from domeprint.server import Handler, ThreadingHTTPServer


@pytest.fixture(scope="module")
def base_url():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def post(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()


def test_meta(base_url):
    with urllib.request.urlopen(base_url + "/api/meta") as r:
        data = json.load(r)
    assert "A4" in data["papers"] and "tight" in data["papers"]
    assert data["defaults"]["tab"] == 5.0


def test_render_fills_one_sheet(base_url):
    status, _, body = post(base_url + "/api/render", {"ab": 61.8, "bc": 54.7, "ca": 54.7})
    assert status == 200
    data = json.loads(body)
    assert len(data["sheets"]) == 1 and data["pieces"] == 18
    assert data["sheets"][0]["svg"].startswith("<?xml")
    assert [t["edge"] for t in data["tabs"]] == ["AB", "BC", "CA"]


def test_render_multiple_sheets(base_url):
    status, _, body = post(base_url + "/api/render", {"ab": 61.8, "bc": 54.7, "ca": 54.7, "count": 30})
    data = json.loads(body)
    assert status == 200 and len(data["sheets"]) == 2 and data["pieces"] == 30 and data["fill"] > 0


def test_pdf(base_url):
    status, ctype, body = post(base_url + "/api/pdf", {"ab": 50, "bc": 50, "ca": 50, "count": 1})
    assert status == 200 and ctype == "application/pdf" and body.startswith(b"%PDF")


@pytest.mark.parametrize(
    "body",
    [
        {"ab": 10, "bc": 10, "ca": 30},  # impossible triangle
        {"ab": 10, "bc": 10},  # missing side
        {"ab": "x", "bc": 10, "ca": 10},
        {"ab": 10, "bc": 10, "ca": 10, "papr": "A4"},
        {"ab": 10, "bc": 10, "ca": 10, "paper": "B9"},
        {"ab": 500, "bc": 500, "ca": 500},  # does not fit
    ],
)
def test_bad_requests(base_url, body):
    status, _, raw = post(base_url + "/api/render", body)
    assert status == 400 and json.loads(raw)["error"]


def test_dome(base_url):
    with urllib.request.urlopen(base_url + "/api/dome?frequency=2&radius=100&portion=0.5") as r:
        data = json.load(r)
    assert len(data["faces"]) == len(data["faceTypes"]) == 40
    assert [t["label"] for t in data["types"]] == ["AAB", "BBB"]
    assert len(data["edges"]) == len(data["edgeStruts"]) == 65


@pytest.mark.parametrize("query", ["frequency=0", "frequency=99", "radius=-1", "portion=x"])
def test_dome_bad_params(base_url, query):
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(f"{base_url}/api/dome?{query}")
    assert e.value.code == 400


def test_meta_lists_frame_options(base_url):
    with urllib.request.urlopen(base_url + "/api/meta") as r:
        frame = json.load(r)["frame"]
    assert "timber_c24" in frame["materials"] and frame["terrains"] == ["0", "I", "II", "III", "IV"]
    assert frame["defaults"]["radius"] == 3.0


def test_frame(base_url):
    body = {"frequency": 2, "portion": 0.5, "radius": 3, "snow_sk": 1.5, "wind_direction": 30}
    status, ctype, body = post(base_url + "/api/frame", body)
    assert status == 200 and ctype == "application/json"
    data = json.loads(body)
    n_edges = len(data["edges"])
    assert n_edges == 65 and len(data["faceCpe"]) == len(data["faces"]) == 40
    assert set(data["cases"]) == {"G", "S", "Sd", "W+", "W-"}
    n_nodes = len(data["vertices"])
    for c in data["cases"].values():
        assert len(c["forces"]) == n_edges
        assert len(c["loads"]) == len(c["displacements"]) == n_nodes  # per hub: kN and mm
        assert sum(p[2] for p in c["loads"]) == pytest.approx(c["total"][2], abs=1e-3)
    g = data["cases"]["G"]
    assert max(abs(u[2]) for u in g["displacements"]) <= g["maxDisplacement"] + 1e-9
    env = data["envelope"]
    assert len(env["utilisation"]) == len(env["tension"]) == len(env["compression"]) == n_edges
    assert [s["label"] for s in data["struts"]] == ["A", "B"]
    assert data["wind"]["cpe"] == pytest.approx([0.8, -1.2, 0.0], abs=0.01)
    assert data["wind"]["direction"] == 30
    assert len(data["faceSnow"]["S"]) == len(data["faceSnow"]["Sd"]) == len(data["faces"])
    assert data["supports"] and {"node", "down", "uplift", "horizontal"} <= set(data["supports"][0])


@pytest.mark.parametrize(
    "body",
    [
        {"frequency": 2, "portion": 1},  # sphere: no base
        {"frequency": 0, "portion": 0.5},
        {"frequency": 2, "portion": 0.5, "radius": -3},
        {"frequency": 2, "portion": 0.5, "terrain": "IX"},
        {"frequency": 2, "portion": 0.5, "material_key": "cheese"},
        {"frequency": 2, "portion": 0.5, "radus": 3},  # typo
        {"frequency": 2, "portion": 0.5, "section_shape": "tube", "section_b": 20, "section_h": 12},
        {"frequency": 2, "portion": 0.5, "snow_sk": "lots"},
    ],
)
def test_frame_bad_requests(base_url, body):
    status, _, raw = post(base_url + "/api/frame", body)
    assert status == 400 and json.loads(raw)["error"]
