from typing import Union
import logging

from flask import Blueprint

from RHAPI import RHAPI
from RHUI import UIField, UIFieldType, UIFieldSelectOption
from Database import Pilot, SavedRaceLap
from eventmanager import Evt

import pandas as pd
from itertools import product
import plotly.graph_objects as graph_objects
from plotly.subplots import make_subplots

PLOTLY_JS = "/event_plots/static/plotly-3.0.0.min.js"
# results_df (dataframe)= table of each lap time recorded and associated pilot, round,
# lap number and whether it is one of the fastest 3 consecutive
results_df = pd.DataFrame(columns=["Pilot id",
                                    "Pilot Name",
                                    "Heat",
                                    "Lap Time",
                                    "Round",
                                    "Lap",
                                    "Best Q"])
# table_df (dataframe) = table in order of fastest 3 consecutive, plus derived data used to calculate order
table_df = pd.DataFrame(columns=["Pilot id",
                                    "Best 3 Consecutive Lap Time",
                                    "Best 3 Consecutive Lap Round",
                                    "Best 3 Consecutive Lap",
                                    "Best 3 Consecutive nLaps"])
# pilot_df (dataframe) = pilots: callsigns, ids and colour
pilot_df = pd.DataFrame(columns=["Pilot id",
                                 "Pilot Name",
                                 "Colour"])

DEBUG=False
yaxis_max=60
axes_font_size=12
event_name=""
logger = logging.getLogger(__name__)


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
        #reset table_df
        table_df.drop(table_df.index, inplace=True)
        pilot_df.drop(pilot_df.index, inplace=True)
        if DEBUG:
          logger.info(raceclass_results)
        if raceclass_results is not None:
            for pilot in raceclass_results['by_consecutives']:
                if pilot['laps'] > 0:
                    if  pilot['consecutives_source']['heat'] :
                       round=int(pilot['consecutives_source']['round'])
                       if round == 0:
                          round = int(pilot['consecutives_source']['displayname'].split("/")[0].split(" ")[1])
                    else :
                       round=int(str(pilot['consecutives_source']['displayname']).split("/")[0].split(" ")[1])
                    table_df.loc[len(table_df)] = [int(pilot['pilot_id']),pilot['consecutives'],
                                                    round,
                                                    pilot['consecutive_lap_start'],
                                                    pilot['consecutives_base']]
                if pilot['laps'] == 0:
                    table_df.loc[len(table_df)] = [int(pilot['pilot_id']),0,0,0,0]

            if DEBUG:
                pd.set_option('display.max_columns', None)
                pd.set_option('display.max_rows', None)
                logger.info(f"{table_df}")


            # populate pilot_df from rhapi.db.pilots, this could be done on the fly
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

            if DEBUG:
              logger.info(f"{pilot_df}")

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
            results_df.drop(results_df.index, inplace=True)
            #logger.info(f"{pilot_list}")
            for i in range(len(pilot_list)):
                for j, jj in enumerate(pilot_list[i]):
                    laps = rhapi.db.laps_by_pilotrun(pilot_list[i][j])
                    heat_id = [rhapi.db.race_by_id(lap.race_id).heat_id for lap in laps]
                    #logger.info(heat_id)
                    #heatname = rhapi.db.heat_by_id(heat_id[0])
                    #heat_attr = rhapi.db.heat_results(heat_id[0])
                    if laps:
                        this_pilot = laps[0].pilot_id
                        temp_laps = [lap.lap_time_formatted for lap in laps if lap.deleted == 0]
                        for k in range(len(temp_laps)):
                            qlap = int(0)
                            time_in_seconds = ((float(temp_laps[k].split(":")[0]) * 60) +
                                               float(temp_laps[k].split(":")[1]))
                            # If this is fastest round and one of the 3 fastest consecutive then set qlap to 1. Boolean might be better future update
                            if j == table_df[table_df["Pilot id"]==this_pilot]["Best 3 Consecutive Lap Round"].item() -1:
                                if table_df[table_df["Pilot id"]==this_pilot]["Best 3 Consecutive Lap"].item():
                                    if (k >= table_df[table_df["Pilot id"]==this_pilot]["Best 3 Consecutive Lap"].item() and
                                            k <  (table_df[table_df["Pilot id"]==this_pilot]["Best 3 Consecutive Lap"].item()+table_df[table_df["Pilot id"]==this_pilot]["Best 3 Consecutive nLaps"].item())) :
                                        qlap = int(1)
                                        #logger.info("qlap==1")
                                else:
                                    qlap = int(0)
                            else:
                                qlap = int(0)
                            results_df.loc[len(results_df)] = {"Pilot id": int(this_pilot),
                                                               "Pilot Name": pilot_names[pilot_ids.index(this_pilot)],
                                                               "Heat": heat_id[0],
                                                               "Lap Time": time_in_seconds,
                                                               "Round": int(j) + 1,
                                                               "Lap": int(k),
                                                               "Best Q": qlap}
            if DEBUG:
                logger.info(results_df)
        else:
            # no race/lap time data
            logger.info("No raceclass results found")
    else:
        logger.info("No race data present")



def update_event_plot(rhapi:RHAPI) -> str:
    logger.info("Plotting events results")
    event_name: str = rhapi.db.option("eventName")
    if len(rhapi.db.races)> 0 or len(results_df) > 0:
        ### Need to check laps and pilots exist before running?
        fig = graph_objects.Figure()

        # get min and max rounds - idea was to use this as a variable to filter with slider. Not trivial with plotly,
        # requires javascript functions to update the source. Possible future development
        #min_round = min(results_df["Round"])
        #max_round = max(results_df["Round"])
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
            custom_ylabel.append(f"{this_pilot}<br>{table_df.loc[table_df['Pilot id'] == pilot_id,'Best 3 Consecutive nLaps'].values[0]}/ {table_df.loc[table_df['Pilot id'] == pilot_id,'Best 3 Consecutive Lap Time'].values[0]}")

        # Set theme and other visual options
        # the itemclick option allows legendgroups to be hidden when clicked
        if DEBUG:
            logger.info(f"{pilot_df.shape[0]} Row Height for plot is :{int(pilot_df.shape[0]*int(rhapi.db.option('event_plots_row_height')))}")
        fig.update_layout(
            template="plotly_dark",  # Dark mode
#            height=int(pilot_df.shape[0]*60),
            height=int(pilot_df.shape[0]*int(rhapi.db.option("event_plots_row_height"))),
            xaxis=dict(
                tickmode="linear",  # Ensures regular intervals
                dtick=2,  # Interval of 2
                title="Lap Time (s)",
                #range=[0,None]
                rangemode='tozero',
                showgrid=True,
                gridcolor='rgba(211,211,211,0.2)',
                gridwidth=0.5
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

        rhapi.ui.register_markdown(
            "event_results_plot",
            "Current Results",
            fig.to_html(include_plotlyjs=PLOTLY_JS, full_html=True),
        )

        return fig.to_html(include_plotlyjs=PLOTLY_JS, default_height=30)
    else:
        logger.info("No data to plot")
        return "No data to plot"

def update_race_plots(rhapi) -> str:

    logger.info(f"Plotting Races")
    if len(rhapi.db.races) > 0 or len(results_df) > 0:
        event_name: str = rhapi.db.option("eventName")

        unique_races = list(dict.fromkeys(list(zip(results_df["Round"], results_df["Heat"]))))
        sorted_unique_races = sorted(unique_races, key=lambda x:(x[0], x[1]))
        if DEBUG:
            logger.info(f"Unique races are {sorted_unique_races}")

        #Get the name of the heats
        #heats=list(set(results_df["Heat"]))
        #rounds=[]
        #for h in heats:
        #    rounds.append(list(set(results_df[results_df["Heat"]==h]["Round"])))
        #nplots = sum(sum(inner_list) for inner_list in rounds)

        subtitles=[]
        #if DEBUG:
        #    logger.info(heats)
        #    logger.info(rounds)
        #    logger.info(f"Total plots ={nplots}")

        #long_rounds_i = max(range(len(rounds)), key = lambda i: len(rounds[i]))
        #long_rounds_i = int(nplots/int(len(rounds))+0.5)
        #if DEBUG:
        #    logger.info(f" Number of rounds = {long_rounds_i}")
        #max_rounds=len(rounds[long_rounds_i])

        for i in range(len(sorted_unique_races)):
            subtitles.append(f"Round {sorted_unique_races[i][0]} - Heat {sorted_unique_races[i][1]}")
        subtitles_str=tuple(subtitles)
        if DEBUG:
            logger.info(subtitles_str)

        fig = make_subplots(rows=len(sorted_unique_races), cols=1, subplot_titles=subtitles_str)
        this_row=0

        for ii in range(len(sorted_unique_races)):
            r=sorted_unique_races[ii][0]
            h=sorted_unique_races[ii][1]
            if DEBUG:
                logger.info(f"round ={r}, heat ={h}")

            this_row+=1
            laps = results_df.loc[(results_df["Heat"] == h) & (results_df["Round"] == r) ]
            pilots_this_heat=list(set(laps["Pilot id"]))
            yd = []
            pilot_legend = []
            pilot_legend_colours = []
            for p in pilots_this_heat:
                this_pilot_name = pilot_df.loc[pilot_df["Pilot id"] == p, ["Pilot Name"]].values[0][0] 
                this_pilot_colour = pilot_df.loc[pilot_df["Pilot id"] == p, ["Colour"]].values[0][0]
                pilot_lap = list(laps[laps["Pilot id"] == p]["Lap Time"])
                if DEBUG:
                    logger.info(f"{p},{pilot_lap}")
                xd = [lapi for lapi in range(len(pilot_lap))]
                ycum = []
                pilot_legend.append(this_pilot_name)
                pilot_legend_colours.append(this_pilot_colour)
                for i in range(len(pilot_lap)):
                    if i > 0:
                        ycum.append(ycum[i - 1] + pilot_lap[i])
                    else:
                        ycum.append(pilot_lap[i])
                yd.append(ycum)

                # specific laptime labels on points
                #hovertemplate = "X: %{x}<br>Y: %{y}<br>Label: %{text}",
                #text = custom_labels  # Define the custom values to show in hover

                fig.add_trace(graph_objects.Scatter(x=xd, y=ycum, mode="lines+markers",
                                                    name=this_pilot_name,
                                                    line=dict(color=this_pilot_colour),
                                                    marker=dict(
                                                        size=15,  # Set marker size
                                                        color=this_pilot_colour,  # Set marker color
                                                        symbol='circle',  # Set marker shape
                                                        opacity=0.8  # Set marker transparency
                                                    )),
                              row=ii+1, col=1,
                              )
            #Plot delta plots
            if DEBUG:
                logger.info(yd)

            delta_laps=[]
            # need to check most laps complete
            if len(yd) > 0:
            	index_of_fastest = min(range(len(yd)), key=lambda i: yd[i][-1])
            else:
                index_of_fastest = 99
            if DEBUG:
                logger.info(f"Fastest pilot index is {index_of_fastest}")

        fig.update_layout(
            template="plotly_dark",  # Dark mode
            height=int(len(sorted_unique_races)*int(rhapi.db.option('race_plots_row_height'))),
            showlegend=False,
            title=f"{event_name} - Lap Times")

        ## create pilot list for each heat and add a legend at the top

        # fig.update_layout(
        #     annotations=[
        #         dict(text="Legend 1:<br>Line 1", x=0.2, y=1, xref="paper", yref="paper",
        #              showarrow=False, font=dict(color="red", size=14)),
        #         dict(text="Legend 2:<br>Line 2", x=0.8, y=1, xref="paper", yref="paper",
        #              showarrow=False, font=dict(color="blue", size=14)),
        #         dict(text="Legend 3:<br>Bar 1", x=0.2, y=0.1, xref="paper", yref="paper",
        #              showarrow=False, font=dict(color="green", size=14)),
        #         dict(text="Legend 4:<br>Bar 2", x=0.8, y=0.1, xref="paper", yref="paper",
        #              showarrow=False, font=dict(color="purple", size=14)),
        #     ]
        # )

        common_xaxis_settings = dict(
            title="Lap",
            showgrid=True,
            dtick=1,
            rangemode='tozero'
        )
        common_yaxis_settings = dict(
            title="Time(s)"
        )

        for i in range(len(sorted_unique_races)):
            fig.update_layout(**{f"xaxis{i+1}": common_xaxis_settings, f"yaxis{i+1}":common_yaxis_settings})


        rhapi.ui.register_markdown(
            "race_results_plot",
            "Race Results",
            fig.to_html(include_plotlyjs=PLOTLY_JS, full_html=False),
        )
        return fig.to_html(include_plotlyjs=PLOTLY_JS)
    else:
        logger.info("No data to plot")
        return "No data to plot"




def update_results(args: dict) -> None:
    rhapi: Union[RHAPI, None] = args.get("rhapi", None)
    if rhapi is not None:
        update_event_data({"rhapi": rhapi})
        update_event_plot(rhapi)
        update_race_plots(rhapi)


def init_plugin(args: dict) -> None:
    logger.info("Event Plot Plugin initialised")


def initialize(rhapi: RHAPI) -> None:
    # Event Startup creates the dataframes
    rhapi.events.on(Evt.STARTUP, init_plugin, default_args={"rhapi": rhapi})
    # Event Startup populates the dataframes if restoring aa db
    rhapi.events.on(Evt.STARTUP, update_results, default_args={"rhapi": rhapi})
    # Event Laps_save and Laps_resave tp update the dataframes with latest results
    rhapi.events.on(Evt.LAPS_SAVE, update_results, default_args={"rhapi": rhapi})
    rhapi.events.on(Evt.LAPS_RESAVE, update_results, default_args={"rhapi": rhapi})
    rhapi.events.on(Evt.DATABASE_RESTORE, update_results, default_args={"rhapi": rhapi})

    rhapi.ui.register_panel("event_plots_set", "Event Plots Settings", "settings")

#    Plot Team laptimes plus stats
#    label the average

    erow_height_field = UIField(
        name="event_plots_row_height",
        label="Row Height",
        field_type=UIFieldType.NUMBER,
        desc=("This is the height of each row in the plots "),
        value=100)
    rhapi.fields.register_option(erow_height_field, "event_plots_set")

    rrow_height_field = UIField(
        name="race_plots_row_height",
        label="Row Height",
        field_type=UIFieldType.NUMBER,
        desc=("This is the height of each row in the plots "),
        value=300)
    rhapi.fields.register_option(rrow_height_field, "event_plots_set")

    # Event Results Plot
    rhapi.ui.register_panel("event_results_plot", "Event Results Plot", "results")
    rhapi.ui.register_quickbutton(
         "event_plots_set",
         "plot_data_update",
         "Manual Plot Update",
         update_results,
         {"rhapi": rhapi},
    )
    # Link to the page
    rhapi.ui.register_markdown(
        "event_results_plot", "Event Results Plot", "Plot available [here](/event_result)"
    )

    # Race Results Plot
    rhapi.ui.register_panel("race_results_plot", "Race Results Plots", "results")
    # rhapi.ui.register_quickbutton(
    #     "race_results_plot",
    #     "plot_race_data_update",
    #     "Manual Plot Update",
    #     update_race_results,
    #     {"rhapi": rhapi},
    # )
    # # Link to the page
    rhapi.ui.register_markdown(
        "race_results_plot", "Race Results Plot", "Plot available [here](/race_results)"
    )

    bp1 = Blueprint(
            "event_plot",
            __name__,
            static_folder="static",
            static_url_path="/event_plots/static",
        )



    #Call the plotly event plot to create html
    @bp1.route("/event_result")
    def results_plot_homePage():
        return update_event_plot(rhapi)

    rhapi.ui.blueprint_add(bp1)

    bp2 = Blueprint(
            "race_plot",
            __name__,
            static_folder="static",
            static_url_path="/event_plots/static",
        )


    @bp2.route("/race_results")
    def race_plots_homePage():
        return update_race_plots(rhapi)

    rhapi.ui.blueprint_add(bp2)
