from typing import Union
import logging

from flask import Blueprint
import plotly.graph_objects as graph_objects

from RHAPI import RHAPI
from Database import Pilot, SavedRaceLap
from eventmanager import Evt

import pandas as pd

PLOTLY_JS = "/event_plots/static/plotly-3.0.0.min.js"
# results_df (dataframe)= table of each lap time recorded and associated pilot, round,
# lap number and whether it is one of the fastest 3 consecutive
results_df = pd.DataFrame(columns=["Pilot id",
                                    "Pilot Name",
                                    "Lap Time",
                                    "Round",
                                    "Lap",
                                    "Best Q"])
# table_df (dataframe) = table in order of fastest 3 consecutive, plus derived data used to calculate order
table_df = pd.DataFrame(columns=["Pilot id",
                                    "Best 3 Consecutive Lap Time",
                                    "Best 3 Consecutive Round",
                                    "Best 3 Consecutive Lap",
                                    "Best 3 Consecutive nLaps"])
# pilot_df (dataframe) = pilots: callsigns, ids and colour
pilot_df = pd.DataFrame(columns=["Pilot id",
                                                "Pilot Name",
                                                "Colour"])
event_name=""
logger = logging.getLogger(__name__)


def init_plugin(args: dict) -> None:
    logger.info("Event Plot Plugin initialised")

def update_event_data(args: dict) -> None:

    # reset dataframes to empty
    # results_df = pd.DataFrame(columns=results_df.columns)
    # table_df = pd.DataFrame(columns=table_df.columns)
    # pilot_df = pd.DataFrame(columns=pilot_df.columns)

    logger.info("Updating event results data")
    rhapi: Union[RHAPI, None] = args.get("rhapi", None)

    if len(rhapi.db.races)> 0:
        raceclass = rhapi.db.raceclasses

        raceclass_results = rhapi.db.raceclass_results(raceclass[0])



        if raceclass_results is not None:
            # This dataframe is redundant as all these calls to get data from the db could be done on the fly.
            # Future development to remove this dataframe and reduce overhead
            table_df["Pilot id"] = [int(i['pilot_id']) for i in raceclass_results['by_consecutives']]
            table_df["Best 3 Consecutive Lap Time"] = [i['consecutives'] for i in raceclass_results['by_consecutives']]
            table_df["Best 3 Consecutive Lap Round"] = [i['consecutives_source']['heat'] for i in raceclass_results['by_consecutives']]
            table_df["Best 3 Consecutive Lap"] = [i['consecutive_lap_start'] for i in raceclass_results['by_consecutives']]
            table_df["Best 3 Consecutive nLaps"] = [i['consecutives_base'] for i in raceclass_results['by_consecutives']]
            #logger.info(f"{table_df.head(3)}")

            # popoulate pilot_df from rhapi.db.pilots, this could be done on the fly
            # so look to remove this intermediate repeated data in future version
            pilots = rhapi.db.pilots
            pilot_ids = []
            pilot_names = []
            pilot_colours = []
            if len(pilots)>0:
                for i in range(len(pilots)):
                    pilot_ids.append(pilots[i].id)
                    pilot_names.append(pilots[i].callsign)
                    pilot_colours.append(pilots[i].color)
                pilot_df["Pilot id"] = pilot_ids
                pilot_df["Pilot Name"] = pilot_names
                pilot_df["Colour"] = pilot_colours

            races = rhapi.db.pilotruns

            # Get all the race ids for each pilot.
            pilot_list = []
            for i in range(len(pilots)):
                pilot_list.append([])
            for r in range(len(races)):
                if races[r].pilot_id != 0:
                    pilot_list[pilot_ids.index(races[r].pilot_id)].append(races[r].id)

            # Loop through the race ids for each pilot and populate table_df
            # This dataframe allows efficient plotting of fastest laps, holeshots and during the graph object calling
            for i in range(len(pilot_list)):
                for j, jj in enumerate(pilot_list[i]):
                    laps = rhapi.db.laps_by_pilotrun(pilot_list[i][j])
                    heats = [lap.race_id for lap in laps]
                    this_pilot = laps[0].pilot_id
                    temp_laps = [lap.lap_time_formatted for lap in laps if lap.deleted == 0]
                    for k in range(len(temp_laps)):
                        time_in_seconds = (float(temp_laps[k].split(":")[0] * 60) +
                                           float(temp_laps[k].split(":")[1]))
                        # If this is fastest round and one of the 3 fastest consecutive then set qlap to 1. Boolean might be better future update
                        if heats[0] == table_df["Best 3 Consecutive Lap Round"][i]:
                            if (k >= table_df["Best 3 Consecutive Lap"][i] and
                                    k <  (table_df["Best 3 Consecutive Lap"][i]+table_df["Best 3 Consecutive nLaps"][i])) :
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
            # no race/lap time data
            logger.info("No raceclass results found")
    else:
        logger.info("No race data present")



def update_event_plot(rhapi) -> str:
    logger.info("Plotting events results")
    event_name: str = rhapi.db.option("eventName")
    if len(rhapi.db.races)> 0 or len(results_df) > 0:
        ### Need to check laps and pilots exist before running?
        fig = graph_objects.Figure()

        # get min and max rounds - idea was to use this as a variable to filter with slider. Not trivial with plotly,
        # requires javascript functions to update the source. Possible future development
        min_round = min(results_df["Round"])
        max_round = max(results_df["Round"])
        #logger.info(f"Min/Max rounds = {min_round},{max_round}")

        # Plot box, raw data, fastest 3, holeshots for each pilot in the results order.. slowest first
        for pilot_id in reversed(list(table_df["Pilot id"])):

            laps = results_df.loc[results_df["Pilot id"] == int(pilot_id)]

            this_pilot_name=pilot_df.loc[pilot_df["Pilot id"] == pilot_id, ["Pilot Name"]].values[0][0]
            this_pilot_colour=pilot_df.loc[pilot_df["Pilot id"] == pilot_id, ["Colour"]].values[0][0]

            # Box Plot
            fig.add_trace(
                graph_objects.Box(
                    name=this_pilot_name, x=list(laps[laps["Lap"]>0]["Lap Time"]), boxpoints="all",
                    jitter=0.5,
                    pointpos=0,
                    marker=dict(
                        symbol="circle-open",  # Open circles (no fill)
                        color="white",  # Black outline
                        size=8), # Adjust size if needed
                    line=dict(color=this_pilot_colour),
                    legendgroup=pilot_id,
                    hoverinfo='x',
                    showlegend=True
                    ))

            # Scatter for hole shots
            fig.add_trace(
                graph_objects.Scatter(
                    x=list(laps[laps["Lap"]==0]["Lap Time"]),  # Invisible x value
                    y=list(laps[laps["Lap"]==0]["Pilot Name"]),  # Invisible y value
                    mode="markers",
                    marker=dict(symbol="circle-open", color="yellow", size=6),
                    legendgroup=pilot_id,
                    showlegend = False,
                    hoverinfo='x',
                    name=this_pilot_name
                ))

            # Scatter for fastest 3 consecutive lap times
            fig.add_trace(
                graph_objects.Scatter(
                    x=list(laps[laps["Best Q"] == 1]["Lap Time"]),  # Invisible x value
                    y=list(laps[laps["Best Q"] == 1]["Pilot Name"]),  # Invisible y value
                    mode="lines+markers",
                    marker=dict(symbol="circle", color="magenta", size=10, line=dict(width=2)),
                    line=dict(color="magenta", width=2, dash='dot'),
                    legendgroup=pilot_id,
                    showlegend=False,
                    hoverinfo='x',
                    name = this_pilot_name
                ))

        # These are null Graph Objects to populate the legend key
        fig.add_trace(graph_objects.Scatter(
            x=[None],  # Invisible x value
            y=[None],  # Invisible y value
            mode="markers",
            marker=dict(symbol="circle-open", color="white", size=8),
            name="Raw Data Points"  # Custom legend label
        ))
        fig.add_trace(graph_objects.Scatter(
            x=[None],  # Invisible x value
            y=[None],  # Invisible y value
            mode="markers",
            marker=dict(symbol="circle-open", color="yellow", size=6),
            name="Hole Shot"  # Custom legend label
        ))
        fig.add_trace(graph_objects.Scatter(
            x=[None],  # Invisible x value
            y=[None],  # Invisible y value
            mode="markers",
            marker=dict(symbol="circle", color="magenta", size=10),
            name="Best Consecutive 3 Lap"  # Custom legend label
        ))

        # Custom y Labels to show the fastest 3 consecutive lap time for each pilot
        # This could include the round in which this occurred in a future version
        custom_ylabel=[]
        custom_ytics=[]

        for pilot_id in reversed(list(table_df["Pilot id"])):
            this_pilot = pilot_df.loc[pilot_df["Pilot id"] == pilot_id, ["Pilot Name"]].values[0][0]
            custom_ytics.append(this_pilot)
            custom_ylabel.append(f"{this_pilot}<br>"
                                 f"{table_df.loc[table_df["Pilot id"] == pilot_id,'Best 3 Consecutive nLaps'].values[0]}/ "
                                  f"{table_df.loc[table_df["Pilot id"] == pilot_id,'Best 3 Consecutive Lap Time'].values[0]}")

        # Set theme and other visual options
        # the itemclick option allows legendgroups to be hidden when clicked
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
    else:
        logger.info("No data to plot")
        return "No data to plot"


def initialize(rhapi: RHAPI) -> None:
    # Event Startup creates the dataframes
    rhapi.events.on(Evt.STARTUP,init_plugin,default_args={"rhapi": rhapi})
    # Event Startup populates the dataframes if restoring aa db
    rhapi.events.on(Evt.STARTUP, update_event_data, default_args={"rhapi": rhapi})
    # Event Laps_save and Laps_resave tp update the dataframes with latest results
    rhapi.events.on(Evt.LAPS_SAVE, update_event_data, default_args={"rhapi": rhapi})
    rhapi.events.on(Evt.LAPS_RESAVE, update_event_data, default_args={"rhapi": rhapi})

    # Manual results update plot button
    rhapi.ui.register_panel("Event Results Plot", "Event Results Plot", "format")
    rhapi.ui.register_quickbutton("Event Results Plot", "plot_data_update",
                                  "Manual Plot Update", update_event_data, {"rhapi":rhapi})
    # Link to the page
    rhapi.ui.register_markdown("Event Results Plot", "Results Plot", "Plot available [here](/event_result)")


    bp = Blueprint(
            "event_plot",
            __name__,
            static_folder="static",
            static_url_path="/event_plots/static",
        )

    #Call the plotly event plot to create html
    @bp.route("/event_result")
    def results_plot_homePage():
        return update_event_plot(rhapi)

    rhapi.ui.blueprint_add(bp)