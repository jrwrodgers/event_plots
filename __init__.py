from typing import Union
from collections import defaultdict
import logging

from flask import Blueprint
import plotly.graph_objects as graph_objects

from RHAPI import RHAPI
from Database import Pilot, SavedRaceLap
from eventmanager import Evt

import pandas as pd

PLOTLY_JS = "/event_plots/static/plotly-3.0.0.min.js"

results_df = pd.DataFrame(columns=["Pilot id",
                                                "Pilot Name",
                                                "Lap Time",
                                                "Round",
                                                "Lap",
                                                "Best Q"])
table_df = pd.DataFrame(columns=["Pilot id",
                                              "Best 3 Consecutive Lap Time",
                                              "Best 3 Consecutive Round",
                                              "Best 3 Consecutive Lap",
                                              "Best 3 Consecutive nLaps"])
pilot_df = pd.DataFrame(columns=["Pilot id",
                                                "Pilot Name",
                                                "Colour"])
event_name="NA"
logger = logging.getLogger(__name__)


def init_plugin(args: dict) -> None:
    logger.info("Event Plot Plugin initialised")

def update_events_data(args: dict) -> None:
    logger.info("Updating events results data")
    rhapi: Union[RHAPI, None] = args.get("rhapi", None)
    raceclass = rhapi.db.raceclasses
    raceclass_results = rhapi.db.raceclass_results(raceclass[0])
    event_name = rhapi.db.raceclass_by_id(raceclass[0].id).name
    logging.info(f"Event name {event_name}")

    if raceclass_results is not None:

        table_df["Pilot id"] = [int(i['pilot_id']) for i in raceclass_results['by_consecutives']]
        table_df["Best 3 Consecutive Lap Time"] = [i['consecutives'] for i in raceclass_results['by_consecutives']]
        table_df["Best 3 Consecutive Lap Round"] = [i['consecutives_source']['heat'] for i in raceclass_results['by_consecutives']]
        table_df["Best 3 Consecutive Lap"] = [i['consecutive_lap_start'] for i in raceclass_results['by_consecutives']]
        table_df["Best 3 Consecutive nLaps"] = [i['consecutives_base'] for i in raceclass_results['by_consecutives']]

        pilots = rhapi.db.pilots
        pilot_ids = []
        pilot_names = []
        pilot_colours = []
        for i in range(len(pilots)):
            pilot_ids.append(pilots[i].id)
            pilot_names.append(pilots[i].callsign)
            pilot_colours.append(pilots[i].color)
        pilot_df["Pilot id"] = pilot_ids
        pilot_df["Pilot Name"] = pilot_names
        pilot_df["Colour"] = pilot_colours

        races = rhapi.db.pilotruns

        pilot_list = []
        for i in range(len(pilots)):
            pilot_list.append([])
        for r in range(len(races)):
            if races[r].pilot_id != 0:
                pilot_list[pilot_ids.index(races[r].pilot_id)].append(races[r].id)


        for i in range(len(pilot_list)):
            for j, jj in enumerate(pilot_list[i]):
                laps = rhapi.db.laps_by_pilotrun(pilot_list[i][j])
                heats = [lap.race_id for lap in laps]
                this_pilot = laps[0].pilot_id
                temp_laps = [lap.lap_time_formatted for lap in laps if lap.deleted == 0]
                for k in range(len(temp_laps)):
                    time_in_seconds = (float(temp_laps[k].split(":")[0] * 60) +
                                       float(temp_laps[k].split(":")[1]))
                    if heats[0] == table_df["Best 3 Consecutive Lap Round"][i]:
                        if k >= table_df["Best 3 Consecutive Lap"][i]:
                            if k < table_df["Best 3 Consecutive nLaps"][i]:
                                qlap = int(1)
                        else:
                            qlap = int(0)
                    else:
                        qlap = int(0)
                    results_df.loc[len(results_df)] = {"Pilot id": int(this_pilot),
                                                       "Pilot Name": pilot_names[pilot_ids.index(this_pilot)],
                                                       "Lap Time": time_in_seconds,
                                                       "Round": int(j) + 1,
                                                       "Lap": int(k),
                                                       "Best Q": qlap}
        #logger.info(results_df)
    else:
        logger.error("No raceclass results found")




def update_events_plot() -> str:
    logger.info("Plotting events results")
    fig = graph_objects.Figure()

    # get min and max rounds
    min_round = min(results_df["Round"])
    max_round = max(results_df["Round"])
    #logger.info(f"Min/Max rounds = {min_round},{max_round}")

    for pilot_id in reversed(list(table_df["Pilot id"])):

        laps = results_df.loc[results_df["Pilot id"] == int(pilot_id)]

        this_pilot_name=pilot_df.loc[pilot_df["Pilot id"] == pilot_id, ["Pilot Name"]].values[0][0]
        this_pilot_colour=pilot_df.loc[pilot_df["Pilot id"] == pilot_id, ["Colour"]].values[0][0]

        fig.add_trace(
            graph_objects.Box(
                name=this_pilot_name, x=list(laps[laps["Lap"]>0]["Lap Time"]), boxpoints="all",
                jitter=0.5,
                pointpos=0,
                marker=dict(
                    symbol="circle-open",  # Open circles (no fill)
                    color="white",  # Black outline
                    size=6), # Adjust size if needed
                line=dict(color=this_pilot_colour),
                legendgroup=pilot_id,
                hoverinfo='x',
                showlegend=True
                ))

        fig.add_trace(
            graph_objects.Scatter(
                x=list(laps[laps["Lap"]==0]["Lap Time"]),  # Invisible x value
                y=list(laps[laps["Lap"]==0]["Pilot Name"]),  # Invisible y value
                mode="markers",
                marker=dict(symbol="circle-open", color="yellow", size=5),
                legendgroup=pilot_id,
                showlegend = False,
                hoverinfo='x',
                name=this_pilot_name
            ))

        fig.add_trace(
            graph_objects.Scatter(
                x=list(laps[laps["Best Q"] == 1]["Lap Time"]),  # Invisible x value
                y=list(laps[laps["Best Q"] == 1]["Pilot Name"]),  # Invisible y value
                mode="lines+markers",
                marker=dict(symbol="circle", color="magenta", size=6,line=dict(color="magenta", width=1)),
                legendgroup=pilot_id,
                showlegend=False,
                hoverinfo='x',
                name = this_pilot_name
            ))

    fig.add_trace(graph_objects.Scatter(
        x=[None],  # Invisible x value
        y=[None],  # Invisible y value
        mode="markers",
        marker=dict(symbol="circle-open", color="white", size=10),
        name="Raw Data Points"  # Custom legend label
    ))
    fig.add_trace(graph_objects.Scatter(
        x=[None],  # Invisible x value
        y=[None],  # Invisible y value
        mode="markers",
        marker=dict(symbol="circle-open", color="yellow", size=5),
        name="Hole Shot"  # Custom legend label
    ))
    fig.add_trace(graph_objects.Scatter(
        x=[None],  # Invisible x value
        y=[None],  # Invisible y value
        mode="markers",
        marker=dict(symbol="circle", color="magenta", size=12),
        name="Best Consecutive 3 Lap"  # Custom legend label
    ))

    # Custom y Labels
    custom_ylabel=[]
    custom_ytics=[]

    for pilot_id in reversed(list(table_df["Pilot id"])):
        this_pilot = pilot_df.loc[pilot_df["Pilot id"] == pilot_id, ["Pilot Name"]].values[0][0]
        custom_ytics.append(this_pilot)
        custom_ylabel.append(f"{this_pilot}<br>"
                             f"{table_df.loc[table_df["Pilot id"] == pilot_id,'Best 3 Consecutive nLaps'].values[0]}/"
                              f"{table_df.loc[table_df["Pilot id"] == pilot_id,'Best 3 Consecutive Lap Time'].values[0]}")

    fig.update_layout(
        template="plotly_dark",  # Dark mode
        xaxis=dict(
            tickmode="linear",  # Ensures regular intervals
            dtick=2,  # Interval of 2
            title="Lap Time (s)"
        ),
        yaxis=dict(tickmode="array",
                   tickvals=custom_ytics,
                   ticktext=custom_ylabel),

        title=f"{event_name} - Lap Times",
        legend = dict(
        itemclick="toggle",  # Click to show/hide a trace
        itemdoubleclick="toggleothers"  # Double-click to isolate a trace
    )
    )
    return fig.to_html(include_plotlyjs=PLOTLY_JS)


def initialize(rhapi: RHAPI) -> None:
    rhapi.events.on(Evt.STARTUP,init_plugin,default_args={"rhapi": rhapi})
    rhapi.events.on(Evt.STARTUP, update_events_data, default_args={"rhapi": rhapi})
    rhapi.events.on(Evt.LAPS_SAVE, update_events_data, default_args={"rhapi": rhapi})
    rhapi.events.on(Evt.LAPS_RESAVE, update_events_data, default_args={"rhapi": rhapi})
    rhapi.events.on(Evt.LAPS_RESAVE, update_events_data, default_args={"rhapi": rhapi})
    rhapi.events.on(Evt.PILOT_ADD, update_events_data, default_args={"rhapi": rhapi})
    rhapi.events.on(Evt.PILOT_ALTER, update_events_data, default_args={"rhapi": rhapi})
    rhapi.events.on(Evt.PILOT_DELETE, update_events_data, default_args={"rhapi": rhapi})

    bp = Blueprint(
            "event_plots",
            __name__,
            static_folder="static",
            static_url_path="/event_plots/static",
        )

    @bp.route("/event_results")
    def results_plot_homePage():
        return update_events_plot()

    rhapi.ui.blueprint_add(bp)