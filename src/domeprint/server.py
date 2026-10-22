"""Small JSON API for the web viewer, standard library only.

    python -m domeprint.server [--host 127.0.0.1] [--port 8000]

POST /api/render  {"ab": 61.8, "bc": 54.7, "ca": 54.7, ...}  -> sheets as SVG + piece info
POST /api/pdf     same body                                   -> application/pdf
GET  /api/meta                                               -> paper sizes and defaults
GET  /api/dome?frequency=3&radius=100&portion=0.625         -> geodesic dome mesh, struts, face types
POST /api/frame   {"frequency": 3, "portion": 0.625, "radius": 3, ...} -> loads, strut forces, checks

If web/dist exists (after `npm run build`), it is served at /.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import mimetypes
from dataclasses import asdict, fields
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .dome import Dome, build_dome
from .frame import MATERIALS, FrameInputs, FrameResult, MechanismError, analyse_dome
from .frame.wind import TERRAIN
from .geometry import InvalidTriangleError
from .job import JobOptions, JobResult, run_job
from .layout import PAPER_SIZES_MM, DoesNotFitError
from .render import RenderStyle, render_pdf, render_svg

STATIC_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"
MAX_BODY = 64 * 1024
MAX_FREQUENCY = 12


class BadRequest(Exception):
    pass


def parse_options(body: dict[str, Any]) -> tuple[JobOptions, RenderStyle]:
    """Turn a JSON body into job options. Unknown keys are rejected so typos show up."""
    known = {f.name: f for f in fields(JobOptions)}
    extra = set(body) - set(known) - {"labels"}
    if extra:
        raise BadRequest(f"unknown option(s): {', '.join(sorted(extra))}")
    values: dict[str, Any] = {}
    for name in known:
        if name not in body or body[name] is None:
            continue
        v = body[name]
        if name in ("bisector", "calibration"):
            if not isinstance(v, bool):
                raise BadRequest(f"{name} must be true or false")
        elif name == "paper":
            if not isinstance(v, str):
                raise BadRequest("paper must be a string")
        elif name == "count":
            if not isinstance(v, int) or isinstance(v, bool):
                raise BadRequest("count must be an integer")
        else:
            if not isinstance(v, int | float) or isinstance(v, bool) or not math.isfinite(v):
                raise BadRequest(f"{name} must be a number")
            v = float(v)
        values[name] = v
    for side in ("ab", "bc", "ca"):
        if side not in values:
            raise BadRequest(f"missing side {side}")
    if values.get("paper", "A4").upper() not in PAPER_SIZES_MM and values.get("paper", "").lower() != "tight":
        raise BadRequest(f"unknown paper {values['paper']!r}")
    labels = body.get("labels", True)
    if not isinstance(labels, bool):
        raise BadRequest("labels must be true or false")
    return JobOptions(**values), RenderStyle(show_labels=labels)


def describe(result: JobResult) -> dict[str, Any]:
    t = result.triangle
    a, b, c = t.angles_deg
    return {
        "triangle": {
            "sides": {"ab": t.ab, "bc": t.bc, "ca": t.ca},
            "angles": {"a": a, "b": b, "c": c},
            "area": t.area,
            "inradius": t.inradius,
            "circumradius": t.circumradius,
        },
        "tabs": [
            {
                "edge": edge.name,
                "startAngle": math.degrees(tab.start_angle),
                "endAngle": math.degrees(tab.end_angle),
                "height": tab.height,
            }
            for tab, edge in zip(result.piece.tabs, t.edges)
        ],
        "warnings": list(result.piece.warnings),
        "pieces": sum(len(s.placements) for s in result.sheets),
        "fill": result.fill,
    }


def dome_json(query: str) -> dict[str, Any]:
    q = {k: v[-1] for k, v in parse_qs(query).items()}
    try:
        frequency = int(q.get("frequency", "2"))
        radius = float(q.get("radius", "100"))
        portion = float(q.get("portion", "0.5"))
    except ValueError as exc:
        raise BadRequest(f"bad dome parameter: {exc}") from exc
    if not 1 <= frequency <= MAX_FREQUENCY:
        raise BadRequest(f"frequency must be between 1 and {MAX_FREQUENCY}")
    try:
        d: Dome = build_dome(frequency, radius, portion)
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    return {
        "frequency": d.frequency,
        "radius": d.radius,
        "portion": d.portion,
        "height": d.height,
        "baseDiameter": d.base_diameter,
        "vertices": [[round(c, 6) for c in v] for v in d.vertices],
        "faces": d.faces,
        "faceTypes": d.face_types,
        "edges": d.edges,
        "edgeStruts": d.edge_struts,
        "struts": [{"label": s.label, "length": s.length, "factor": s.factor, "count": s.count} for s in d.struts],
        "types": [
            {"label": t.label, "sides": list(t.sides), "count": t.count, "mirrorOf": t.mirror_of} for t in d.types
        ],
    }


def frame_inputs(body: dict[str, Any]) -> tuple[int, float, FrameInputs]:
    known = {f.name: f for f in fields(FrameInputs)}
    extra = set(body) - set(known) - {"frequency", "portion"}
    if extra:
        raise BadRequest(f"unknown option(s): {', '.join(sorted(extra))}")
    frequency, portion = body.get("frequency", 3), body.get("portion", 0.625)
    if not isinstance(frequency, int) or isinstance(frequency, bool) or not 1 <= frequency <= MAX_FREQUENCY:
        raise BadRequest(f"frequency must be an integer between 1 and {MAX_FREQUENCY}")
    if not isinstance(portion, int | float) or isinstance(portion, bool):
        raise BadRequest("portion must be a number")
    values: dict[str, Any] = {}
    for name in known:
        if name not in body or body[name] is None:
            continue
        v = body[name]
        if name in ("material_key", "section_shape", "terrain"):
            if not isinstance(v, str):
                raise BadRequest(f"{name} must be a string")
        elif not isinstance(v, int | float) or isinstance(v, bool) or not math.isfinite(v):
            raise BadRequest(f"{name} must be a number")
        else:
            v = float(v)
        values[name] = v
    return frequency, float(portion), FrameInputs(**values)


def _kn(x: float) -> float:
    return round(x / 1e3, 4)


def frame_json(body: dict[str, Any]) -> dict[str, Any]:
    frequency, portion, inputs = frame_inputs(body)
    try:
        r: FrameResult = analyse_dome(frequency, portion, inputs)
    except (ValueError, MechanismError) as exc:
        raise BadRequest(str(exc)) from exc
    w = r.wind
    return {
        "frequency": r.frequency,
        "portion": r.portion,
        "radius": r.inputs.radius,
        "height": r.height,
        "surfaceArea": r.surface_area,
        "planArea": r.plan_area,
        "frameMass": r.frame_mass,
        "combinations": r.combinations,
        "vertices": [[round(c, 6) for c in v] for v in r.vertices],
        "faces": r.faces,
        "edges": r.edges,
        "edgeStruts": r.edge_struts,
        "faceCpe": [round(c, 4) for c in r.face_cpe],
        "faceSnow": {k: [_kn(x) for x in v] for k, v in r.face_snow.items()},  # kN/m² of plan
        "wind": {
            "qp": w.q_p,
            "ze": w.z_e,
            "fd": w.f_d,
            "hd": w.h_d,
            "cpe": list(w.cpe),
            "direction": r.inputs.wind_direction,
        },
        "cases": {
            name: {
                "forces": [_kn(f) for f in c.forces],
                "total": [_kn(sum(p[k] for p in c.loads)) for k in range(3)],
                "reactions": [[n, *(_kn(x) for x in c.reactions[n])] for n in r.supports],
                "maxDisplacement": c.max_displacement * 1e3,
                "loads": [[_kn(x) for x in p] for p in c.loads],
                "displacements": [[round(x * 1e3, 5) for x in u] for u in c.displacements],
            }
            for name, c in r.cases.items()
        },
        "envelope": {
            "tension": [_kn(e.tension) for e in r.envelope],
            "compression": [_kn(e.compression) for e in r.envelope],
            "utilisation": [round(e.utilisation, 5) for e in r.envelope],
            "combination": [e.combination for e in r.envelope],
        },
        "struts": [
            {
                "label": s.label,
                "count": s.count,
                "length": s.length,
                "tension": _kn(s.tension),
                "compression": _kn(s.compression),
                "tensionResistance": _kn(s.tension_resistance),
                "bucklingResistance": _kn(s.buckling_resistance),
                "utilisation": s.utilisation,
                "combination": s.combination,
            }
            for s in r.strut_summary
        ],
        "supports": [
            {"node": s.node, "down": _kn(s.down), "uplift": _kn(s.uplift), "horizontal": _kn(s.horizontal)}
            for s in r.support_envelope
        ],
    }


def run(body: dict[str, Any]) -> tuple[JobResult, RenderStyle]:
    opts, style = parse_options(body)
    try:
        return run_job(opts), style
    except (InvalidTriangleError, DoesNotFitError, ValueError) as exc:
        raise BadRequest(str(exc).replace("--", "")) from exc


class Handler(BaseHTTPRequestHandler):
    server_version = "domeprint"

    def _send(self, status: int, body: bytes, content_type: str, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: Any) -> None:
        self._send(status, json.dumps(data).encode(), "application/json")

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise BadRequest("request too large")
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as exc:
            raise BadRequest(f"invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise BadRequest("expected a JSON object")
        return data

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/api/dome":
            try:
                self._json(200, dome_json(url.query))
            except BadRequest as exc:
                self._json(400, {"error": str(exc)})
            return
        if self.path == "/api/meta":
            defaults = asdict(JobOptions(0, 0, 0))
            for k in ("ab", "bc", "ca"):
                defaults.pop(k)
            frame = {
                "materials": {k: m.name for k, m in MATERIALS.items()},
                "terrains": list(TERRAIN),
                "defaults": asdict(FrameInputs()),
            }
            self._json(
                200,
                {"papers": [*PAPER_SIZES_MM, "tight"], "sizes": PAPER_SIZES_MM, "defaults": defaults, "frame": frame},
            )
            return
        self._static()

    def do_POST(self) -> None:
        try:
            if self.path == "/api/render":
                result, style = run(self._body())
                sheets = [
                    {"svg": render_svg(s, style), "width": s.width, "height": s.height, "pieces": len(s.placements)}
                    for s in result.sheets
                ]
                self._json(200, {"sheets": sheets, **describe(result)})
            elif self.path == "/api/frame":
                self._json(200, frame_json(self._body()))
            elif self.path == "/api/pdf":
                result, style = run(self._body())
                t = result.triangle
                name = f"domeprint-{t.ab:g}-{t.bc:g}-{t.ca:g}.pdf"
                headers = {"Content-Disposition": f'attachment; filename="{name}"'}
                self._send(200, render_pdf(result.sheets, style), "application/pdf", headers)
            else:
                self._json(404, {"error": "not found"})
        except BadRequest as exc:
            self._json(400, {"error": str(exc)})

    def _static(self) -> None:
        if not STATIC_DIR.is_dir():
            self._json(404, {"error": "web UI not built; run `npm run build` in web/ or use ./dev.sh"})
            return
        rel = self.path.split("?", 1)[0].lstrip("/") or "index.html"
        path = (STATIC_DIR / rel).resolve()
        if not path.is_relative_to(STATIC_DIR) or not path.is_file():
            path = STATIC_DIR / "index.html"
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send(200, path.read_bytes(), ctype)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="domeprint-server", description="JSON API and web viewer for domeprint")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args(argv)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"domeprint server on http://{args.host}:{args.port}", flush=True)
    with contextlib.suppress(KeyboardInterrupt):
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
