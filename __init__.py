"""
_summary_
"""

from typing import Union
from collections import defaultdict

from flask import Blueprint
import plotly.graph_objects as graph_objects

from RHAPI import RHAPI
from Database import Pilot, SavedRaceLap
from eventmanager import Evt

PLOTLY_JS = "/event_plots/static/plotly-3.0.0.min.js"

pilot_mapping: dict[int, str] = {}


def _generate_pilot_mapping(rhapi: RHAPI) -> None:
    for pilot in rhapi.db.pilots:
        pilot_mapping[pilot.id] = pilot.display_callsign


def _alter_pilot_mapping(args: dict) -> None:

    rhapi: Union[RHAPI, None] = args.get("rhapi", None)
    pilot_id: Union[int, None] = args.get("pilot_id", None)
    pilot: Union[Pilot, None] = None

    if rhapi is None or pilot_id is None:
        return

    pilot = rhapi.db.pilot_by_id(pilot_id)

    if pilot is not None:
        pilot_mapping[pilot_id] = pilot.display_callsign


def _remove_pilot_mapping(args: dict) -> None:

    pilot_id: Union[int, None] = args.get("pilot_id", None)

    if pilot_id is not None:
        del pilot_mapping[pilot_id]


def generate_event_totals(rhapi: RHAPI) -> str:

    laps: list[SavedRaceLap] = rhapi.db.laps
    mapping: dict[int, list] = defaultdict(list)

    for lap in laps:
        if not lap.deleted:
            mapping[lap.pilot_id].append(lap.lap_time / 1000)

    fig = graph_objects.Figure()

    for pilot_id, laps in mapping.items():
        fig.add_trace(graph_objects.Box(name=pilot_mapping[pilot_id], x=laps))

    return fig.to_html(include_plotlyjs=PLOTLY_JS)


def initialize(rhapi: RHAPI) -> None:

    rhapi.events.on(Evt.PILOT_ADD, _alter_pilot_mapping, default_args={"rhapi": rhapi})
    rhapi.events.on(
        Evt.PILOT_ALTER, _alter_pilot_mapping, default_args={"rhapi": rhapi}
    )
    rhapi.events.on(Evt.PILOT_DELETE, _remove_pilot_mapping)

    bp = Blueprint(
        "event_plots",
        __name__,
        static_folder="static",
        static_url_path="/event_plots/static",
    )

    @bp.route("/event_results")
    def results_plot_homePage():
        return generate_event_totals(rhapi)

    rhapi.ui.blueprint_add(bp)

    _generate_pilot_mapping(rhapi)
