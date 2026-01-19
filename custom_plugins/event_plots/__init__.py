"""
Event Plots Plugin for RotorHazard

This plugin generates interactive Plotly visualizations of race lap times.
"""

import logging
from flask import Blueprint

from RHAPI import RHAPI
from RHUI import UIField, UIFieldType
from eventmanager import Evt

from .event_plots import EventPlotsGenerator

PLOTLY_JS = "/event_plots/static/plotly-3.0.0.min.js"
logger = logging.getLogger(__name__)

# Debug flag - set to True for verbose logging
DEBUG = False


def init_plugin(args: dict) -> None:
    """Initialize the plugin on startup."""
    logger.info("Event Plot Plugin initialised")


# def manual_update_plot(args: dict) -> None:
#     """Manual plot update handler for quickbutton."""
#     rhapi = args.get("rhapi")
#     if rhapi is not None:
#         logger.info("Manual plot update triggered")
#         # The plot is generated on-demand when the route is accessed
#         # This function exists for compatibility with the quickbutton


def initialize(rhapi: RHAPI) -> None:
    """Initialize the plugin and register event handlers and UI components."""
    # Event Startup
    rhapi.events.on(Evt.STARTUP, init_plugin, default_args={"rhapi": rhapi})
    
    # Register settings panel
    rhapi.ui.register_panel("results_plot_settings", "Results Plots", "settings")
    
    # # Register manual update quickbutton
    # rhapi.ui.register_quickbutton(
    #     "results_plot_settings",
    #     "plot_data_update",
    #     "Manual Plot Update",
    #     manual_update_plot,
    #     {"rhapi": rhapi},
    # )
    
    # Register row height setting
    erow_height_field = UIField(
        name="event_plots_row_height",
        label="Stats Row Height",
        field_type=UIFieldType.NUMBER,
        desc=("This is the height of each row in the plots"),
        value=100
    )
    rhapi.fields.register_option(erow_height_field, "results_plot_settings")
    
    # Register markdown links
    rhapi.ui.register_markdown(
        "results_plot_settings",
        "Event Results Plot",
        "Event Plot available [here](/event_result)"
    )
    
    # Create Blueprint for event results plot
    bp = Blueprint(
        "event_plot",
        __name__,
        static_folder="static",
        static_url_path="/event_plots/static",
    )
    
    @bp.route("/event_result")
    def results_plot_homePage():
        """Route handler for event results plot page - shows list of all classes."""
        try:
            raceclasses = rhapi.db.raceclasses
            if len(raceclasses) == 0:
                return "<html><body><h2>No race classes found</h2></body></html>"
            
            # If only one class, redirect to its plot directly
            if len(raceclasses) == 1:
                generator = EventPlotsGenerator(rhapi)
                return generator.generate_plot(raceclasses[0])
            
            # Multiple classes - show selection page
            html = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Event Results Plots</title>
                <link rel="stylesheet" href="/static/rotorhazard.css">
            </head>
            <body>
                <div class="container-fluid">
                    <h1>Event Results Plots</h1>
                    <p>Select a race class to view its lap time plot:</p>
                    <ul class="class-list" style="list-style: none; padding: 0;">
            """
            
            for raceclass in raceclasses:
                class_id = raceclass.id
                class_name = getattr(raceclass, 'name', f'Class {class_id}')
                html += f'<li style="margin: 10px 0; padding: 15px;"><a href="/event_result/{class_id}">{class_name}</a></li>\n'
            
            html += """
                    </ul>
                </div>
            </body>
            </html>
            """
            
            return html
        
        except Exception as e:
            logger.error(f"Error in results_plot_homePage: {e}", exc_info=True)
            return f"<html><body><h2>Error loading plot</h2><p>{str(e)}</p></body></html>"
    
    @bp.route("/event_result/<int:class_id>")
    def results_plot_by_class(class_id):
        """Route handler for specific race class plot."""
        try:
            raceclasses = rhapi.db.raceclasses
            if len(raceclasses) == 0:
                return "<html><body><h2>No race classes found</h2></body></html>"
            
            # Find the requested class
            raceclass = None
            for rc in raceclasses:
                if rc.id == class_id:
                    raceclass = rc
                    break
            
            if raceclass is None:
                return f"<html><body><h2>Race class {class_id} not found</h2><p><a href='/event_result'>Back to class list</a></p></body></html>"
            
            # Generate plot on-demand
            generator = EventPlotsGenerator(rhapi)
            return generator.generate_plot(raceclass)
        
        except Exception as e:
            logger.error(f"Error in results_plot_by_class: {e}", exc_info=True)
            return f"<html><body><h2>Error loading plot</h2><p>{str(e)}</p><p><a href='/event_result'>Back to class list</a></p></body></html>"
    
    rhapi.ui.blueprint_add(bp)
