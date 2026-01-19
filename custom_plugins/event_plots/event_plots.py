"""
Event Plots Generator Module

This module contains the EventPlotsGenerator class that handles data extraction
and plot generation for race event lap times.
"""

import logging
from typing import Optional, Dict, List, Tuple, Any
from collections import OrderedDict
import pandas as pd
import plotly.graph_objects as graph_objects

from RHAPI import RHAPI

# Import DEBUG flag from __init__
try:
    from . import DEBUG
except ImportError:
    DEBUG = False

PLOTLY_JS = "/event_plots/static/plotly-3.0.0.min.js"
logger = logging.getLogger(__name__)


class EventPlotsGenerator:
    """Generates event plots for race classes with on-demand data extraction."""
    
    def __init__(self, rhapi: RHAPI):
        """Initialize the generator with RHAPI reference.
        
        Args:
            rhapi: RotorHazard API instance
        """
        self.rhapi = rhapi
        # Use OrderedDict for LRU cache behavior - limit size to prevent memory leak
        self._race_cache: OrderedDict[int, int] = OrderedDict()
        self._max_cache_size = 1000  # Maximum cache size
    
    def _wrap_plot_html(self, plot_html: str) -> str:
        """Wrap Plotly HTML in RotorHazard page structure with CSS.
        
        Args:
            plot_html: Plotly HTML content (body content)
            
        Returns:
            Complete HTML page with RotorHazard CSS
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Event Results Plot</title>
    <link rel="stylesheet" href="/static/rotorhazard.css">
</head>
<body>
    <div class="container-fluid">
        {plot_html}
    </div>
</body>
</html>"""
    
    def _get_win_condition(self, raceclass) -> int:
        """Get the win condition from the raceformat.
        
        Args:
            raceclass: Race class object
            
        Returns:
            Win condition integer (0-5):
            0 - Just count laps
            1 - Standard Race, fastest to pass finish post after n laps
            2 - Head to head race, first pass the finish post after n laps
            3 - Fastest single lap
            4 - Fastest consecutive laps
            5 - Most laps in a given time
        """
        try:
            # Log raceclass info (only in debug mode)
            class_id = getattr(raceclass, 'id', 'unknown')
            class_name = getattr(raceclass, 'name', 'unknown')
            if DEBUG:
                logger.info(f"Getting win condition for class ID: {class_id}, Name: {class_name}")
            
            # Get raceformat from raceclass
            raceformat = None
            try:
                # Try accessing raceformat_id and then getting the format
                if hasattr(raceclass, 'format_id'):
                    format_id = raceclass.format_id
                    raceformat = self.rhapi.db.raceformat_by_id(format_id)
                elif hasattr(raceclass, 'raceformat'):
                    raceformat = raceclass.raceformat
                elif hasattr(raceclass, 'format'):
                    raceformat = raceclass.format
            except Exception as e:
                logger.warning(f"Error accessing raceformat: {e}")
            
            # Get win_condition from raceformat
            if raceformat:
                if hasattr(raceformat, 'win_condition'):
                    win_condition = int(raceformat.win_condition)
                    if DEBUG:
                        logger.info(f"Found win_condition: {win_condition} for class {class_id}")
                    return win_condition
                else:
                    logger.warning(f"Raceformat does not have 'win_condition' attribute")
            else:
                logger.warning("Could not retrieve raceformat from raceclass")
            
            # Fallback: Check raceclass_results structure
            raceclass_results = self.rhapi.db.raceclass_results(raceclass)
            if raceclass_results and 'by_consecutives' in raceclass_results:
                if DEBUG:
                    logger.info("Found 'by_consecutives' in raceclass_results (fallback), assuming win_condition 4")
                return 4
        except Exception as e:
            logger.warning(f"Error getting win condition: {e}, defaulting to 0", exc_info=True)
        
        if DEBUG:
            logger.info(f"Defaulting to win_condition: 0")
        return 0
    
    def _parse_lap_time(self, lap_time_formatted: str) -> float:
        """Parse lap time from formatted string to seconds.
        
        Args:
            lap_time_formatted: Formatted time string (e.g., "MM:SS.sss")
            
        Returns:
            Time in seconds as float
        """
        try:
            parts = lap_time_formatted.split(":")
            if len(parts) == 2:
                minutes = float(parts[0])
                seconds = float(parts[1])
                return minutes * 60 + seconds
            else:
                # Try parsing as seconds directly
                return float(lap_time_formatted)
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error parsing lap time '{lap_time_formatted}': {e}")
            return 0.0
    
    def _get_race_heat_id(self, lap) -> int:
        """Get heat_id from lap, using cache to avoid repeated API calls.
        
        Args:
            lap: Lap object
            
        Returns:
            Heat ID
        """
        race_id = lap.race_id
        if race_id not in self._race_cache:
            try:
                race = self.rhapi.db.race_by_id(race_id)
                heat_id = race.heat_id if race else 0
                # Add to cache with LRU eviction if cache is full
                if len(self._race_cache) >= self._max_cache_size:
                    self._race_cache.popitem(last=False)  # Remove oldest entry
                self._race_cache[race_id] = heat_id
                # Move to end (most recently used)
                self._race_cache.move_to_end(race_id)
            except Exception as e:
                logger.warning(f"Error getting heat_id for race {race_id}: {e}")
                heat_id = 0
                if len(self._race_cache) >= self._max_cache_size:
                    self._race_cache.popitem(last=False)
                self._race_cache[race_id] = heat_id
                self._race_cache.move_to_end(race_id)
        else:
            # Move to end (most recently used)
            self._race_cache.move_to_end(race_id)
        return self._race_cache[race_id]
    
    def _get_class_heat_ids(self, raceclass) -> set:
        """Get all heat IDs that belong to a raceclass.
        
        Args:
            raceclass: Race class object
            
        Returns:
            Set of heat IDs belonging to the class
        """
        class_heat_ids = set()
        class_id = getattr(raceclass, 'id', None)
        if class_id is None:
            return class_heat_ids
        
        try:
            heats = self.rhapi.db.heats
            for heat in heats:
                heat_class = None
                # Check class_id first (most common attribute name)
                if hasattr(heat, 'class_id'):
                    try:
                        heat_class = heat.class_id
                    except Exception:
                        pass
                # Fallback to other possible attribute names
                if heat_class is None and hasattr(heat, 'raceclass_id'):
                    try:
                        heat_class = heat.raceclass_id
                    except Exception:
                        pass
                if heat_class is None and hasattr(heat, 'race_class_id'):
                    try:
                        heat_class = heat.race_class_id
                    except Exception:
                        pass
                
                if heat_class == class_id:
                    class_heat_ids.add(heat.id)
            
            if DEBUG:
                logger.info(f"Found {len(class_heat_ids)} heats for class {class_id}: {class_heat_ids}")
        except Exception as e:
            logger.warning(f"Error getting heats for class: {e}", exc_info=True)
        
        return class_heat_ids
    
    def _build_pilotrun_heat_map(self, class_heat_ids: set) -> Tuple[Dict[int, int], Dict[int, Any]]:
        """Build a mapping of pilotrun_id -> heat_id for efficient lookups.
        
        Args:
            class_heat_ids: Set of heat IDs to filter by (empty set means all heats)
            
        Returns:
            Tuple of (pilotrun_id -> heat_id mapping, pilotrun_id -> pilotrun object mapping)
        """
        pilotrun_heat_map = {}
        pilotrun_dict = {}
        try:
            pilotruns = self.rhapi.db.pilotruns
            for pilotrun in pilotruns:
                if pilotrun.pilot_id == 0:
                    continue
                pilotrun_dict[pilotrun.id] = pilotrun  # Cache pilotrun object
                try:
                    # Get laps to find the heat_id
                    laps = self.rhapi.db.laps_by_pilotrun(pilotrun.id)
                    if laps:
                        heat_id = self._get_race_heat_id(laps[0])
                        # Only include if filtering by class heats, or if no filter
                        if not class_heat_ids or heat_id in class_heat_ids:
                            pilotrun_heat_map[pilotrun.id] = heat_id
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error building pilotrun heat map: {e}")
        
        return pilotrun_heat_map, pilotrun_dict
    
    def _extract_pilot_data(self, raceclass) -> pd.DataFrame:
        """Extract pilot information for the race class.
        
        Args:
            raceclass: Race class object
            
        Returns:
            DataFrame with columns: Pilot id, Pilot Name, Colour
        """
        pilot_ids = []
        pilot_names = []
        pilot_colours = []
        
        try:
            # Get heats that belong to this raceclass (using shared helper)
            class_heat_ids = self._get_class_heat_ids(raceclass)
            
            # Build pilotrun -> heat_id mapping for efficient lookups
            pilotrun_heat_map, pilotrun_dict = self._build_pilotrun_heat_map(class_heat_ids)
            
            # Get pilots that have runs in this class's heats
            pilot_set = set()
            if len(class_heat_ids) > 0:
                # Use the mapping to find pilots efficiently
                for pilotrun_id, heat_id in pilotrun_heat_map.items():
                    if heat_id in class_heat_ids:
                        pilotrun = pilotrun_dict.get(pilotrun_id)
                        if pilotrun and pilotrun.pilot_id != 0:
                            pilot_set.add(pilotrun.pilot_id)
            
            # Get pilot details
            pilots = self.rhapi.db.pilots
            pilot_dict = {pilot.id: pilot for pilot in pilots}
            
            # Only include pilots that are in this class
            if len(class_heat_ids) > 0:
                for pilot_id in pilot_set:
                    if pilot_id in pilot_dict:
                        pilot = pilot_dict[pilot_id]
                        pilot_ids.append(pilot.id)
                        pilot_names.append(pilot.callsign)
                        pilot_colours.append(pilot.color)
            else:
                # Fallback: if no heats found, include all pilots
                for pilot in pilots:
                    pilot_ids.append(pilot.id)
                    pilot_names.append(pilot.callsign)
                    pilot_colours.append(pilot.color)
        except Exception as e:
            logger.error(f"Error extracting pilot data: {e}", exc_info=True)
        
        # Ensure we always return a DataFrame with the correct structure, even if empty
        if len(pilot_ids) == 0:
            logger.warning("No pilots found, returning empty DataFrame")
            return pd.DataFrame(columns=["Pilot id", "Pilot Name", "Colour"])
        
        return pd.DataFrame({
            "Pilot id": pilot_ids,
            "Pilot Name": pilot_names,
            "Colour": pilot_colours
        })
    
    def _extract_consecutive_data(self, raceclass_results: Dict, consecutive_laps_base: int = 3) -> pd.DataFrame:
        """Extract best consecutive lap data for fastest consecutive class type.
        
        Args:
            raceclass_results: Race class results dictionary
            consecutive_laps_base: Number of consecutive laps (for column naming)
            
        Returns:
            DataFrame with columns: Pilot id, Best N Consecutive Lap Time, 
            Best N Consecutive Lap Round, Best N Consecutive Lap, Best N Consecutive nLaps
            (where N is consecutive_laps_base)
        """
        consecutive_data = []
        # Dynamic column names based on consecutive_laps_base
        time_col = f"Best {consecutive_laps_base} Consecutive Lap Time"
        round_col = f"Best {consecutive_laps_base} Consecutive Lap Round"
        lap_col = f"Best {consecutive_laps_base} Consecutive Lap"
        nlaps_col = f"Best {consecutive_laps_base} Consecutive nLaps"
        
        try:
            if raceclass_results and 'by_consecutives' in raceclass_results:
                for pilot in raceclass_results['by_consecutives']:
                    pilot_id = int(pilot['pilot_id'])
                    if pilot['laps'] > 0:
                        # Extract round number with improved error handling
                        roundn = 0
                        try:
                            if pilot.get('consecutives_source', {}).get('heat'):
                                roundn = int(pilot['consecutives_source']['round'])
                            
                            # Fallback parsing from displayname if round is 0 or missing
                            if roundn == 0:
                                displayname = pilot.get('consecutives_source', {}).get('displayname', '')
                                if displayname:
                                    # Try multiple parsing strategies
                                    parts = str(displayname).split("/")
                                    if len(parts) > 0:
                                        first_part = parts[0].strip()
                                        # Try to find a number in the first part
                                        words = first_part.split()
                                        for word in words:
                                            try:
                                                roundn = int(word)
                                                break
                                            except ValueError:
                                                continue
                            
                            if roundn == 0:
                                if DEBUG:
                                    logger.warning(f"Could not determine round number for pilot {pilot_id}, using 0")
                        except (ValueError, IndexError, KeyError, AttributeError) as e:
                            if DEBUG:
                                logger.warning(f"Error parsing round from displayname for pilot {pilot_id}: {e}")
                            roundn = 0
                        
                        # Convert consecutive time to float - handle both numeric and formatted string
                        consecutive_value = pilot['consecutives']
                        if isinstance(consecutive_value, str):
                            # Parse formatted time string (e.g., '0:56.676')
                            consecutive_time = self._parse_lap_time(consecutive_value)
                        else:
                            # Already numeric
                            consecutive_time = float(consecutive_value) if consecutive_value else 0.0
                        
                        # Handle None values for lap_start and nLaps
                        consecutive_lap_start = pilot.get('consecutive_lap_start')
                        consecutive_lap_start = int(consecutive_lap_start) if consecutive_lap_start is not None else 0
                        
                        consecutives_base = pilot.get('consecutives_base')
                        consecutives_base = int(consecutives_base) if consecutives_base is not None else 0
                        
                        consecutive_data.append({
                            "Pilot id": pilot_id,
                            time_col: consecutive_time,
                            round_col: roundn,
                            lap_col: consecutive_lap_start,
                            nlaps_col: consecutives_base
                        })
                    else:
                        # Pilot with no laps
                        consecutive_data.append({
                            "Pilot id": pilot_id,
                            time_col: 0,
                            round_col: 0,
                            lap_col: 0,
                            nlaps_col: 0
                        })
        except Exception as e:
            logger.error(f"Error extracting consecutive data: {e}", exc_info=True)
        
        df = pd.DataFrame(consecutive_data)
        
        # Ensure numeric columns are properly typed
        if len(df) > 0:
            df[time_col] = pd.to_numeric(df[time_col], errors='coerce').fillna(0.0)
            df[round_col] = pd.to_numeric(df[round_col], errors='coerce').fillna(0)
            df[lap_col] = pd.to_numeric(df[lap_col], errors='coerce').fillna(0)
            df[nlaps_col] = pd.to_numeric(df[nlaps_col], errors='coerce').fillna(0)
        
        return df
    
    def _get_round_number(self, lap, pilotrun_id: int) -> int:
        """Get actual round number from race or pilotrun.
        
        Args:
            lap: Lap object
            pilotrun_id: Pilotrun ID
            
        Returns:
            Round number (1-indexed), or 0 if not found
        """
        try:
            # Try to get round from race object
            race = self.rhapi.db.race_by_id(lap.race_id)
            if race:
                # Check for round attribute
                if hasattr(race, 'round_id'):
                    round_id = race.round_id
                    if round_id:
                        # Try to get round number from round object (if API method exists)
                        try:
                            if hasattr(self.rhapi.db, 'round_by_id'):
                                round_obj = self.rhapi.db.round_by_id(round_id)
                                if round_obj and hasattr(round_obj, 'round_number'):
                                    return int(round_obj.round_number)
                        except (AttributeError, TypeError):
                            pass
                # Fallback: check if race has round number directly
                if hasattr(race, 'round'):
                    try:
                        round_val = race.round
                        if round_val is not None:
                            return int(round_val)
                    except (ValueError, TypeError):
                        pass
                if hasattr(race, 'round_number'):
                    try:
                        round_val = race.round_number
                        if round_val is not None:
                            return int(round_val)
                    except (ValueError, TypeError):
                        pass
            
            # Try to get from pilotrun (if API method exists)
            try:
                if hasattr(self.rhapi.db, 'pilotrun_by_id'):
                    pilotrun = self.rhapi.db.pilotrun_by_id(pilotrun_id)
                    if pilotrun:
                        if hasattr(pilotrun, 'round_id'):
                            round_id = pilotrun.round_id
                            if round_id:
                                try:
                                    if hasattr(self.rhapi.db, 'round_by_id'):
                                        round_obj = self.rhapi.db.round_by_id(round_id)
                                        if round_obj and hasattr(round_obj, 'round_number'):
                                            return int(round_obj.round_number)
                                except (AttributeError, TypeError):
                                    pass
                        if hasattr(pilotrun, 'round'):
                            try:
                                round_val = pilotrun.round
                                if round_val is not None:
                                    return int(round_val)
                            except (ValueError, TypeError):
                                pass
                        if hasattr(pilotrun, 'round_number'):
                            try:
                                round_val = pilotrun.round_number
                                if round_val is not None:
                                    return int(round_val)
                            except (ValueError, TypeError):
                                pass
            except (AttributeError, TypeError):
                pass
        except Exception as e:
            if DEBUG:
                logger.warning(f"Error getting round number: {e}")
        return 0  # Return 0 if not found (will use index-based fallback)
    
    def _extract_lap_data(self, raceclass, win_condition: int, pilot_df: pd.DataFrame, 
                         consecutive_df: Optional[pd.DataFrame] = None, consecutive_laps_base: int = 3) -> pd.DataFrame:
        """Extract all lap time data for the race class.
        
        Args:
            raceclass: Race class object
            win_condition: Win condition integer
            pilot_df: DataFrame with pilot information
            consecutive_df: DataFrame with consecutive data (for win_condition 4)
            consecutive_laps_base: Number of consecutive laps (for column name lookup)
            
        Returns:
            DataFrame with columns: Pilot id, Pilot Name, Heat, Lap Time, Round, Lap, Best Q, Fastest Lap, Heat Color
        """
        lap_data = []
        
        try:
            # Validate pilot_df has required columns
            if len(pilot_df) == 0:
                logger.warning("pilot_df is empty, cannot extract lap data")
                return pd.DataFrame(columns=["Pilot id", "Pilot Name", "Heat", "Lap Time", "Round", "Lap", "Best Q", "Fastest Lap", "Heat Color"])
            
            if "Pilot id" not in pilot_df.columns or "Pilot Name" not in pilot_df.columns:
                logger.error(f"pilot_df missing required columns. Available: {pilot_df.columns.tolist()}")
                return pd.DataFrame(columns=["Pilot id", "Pilot Name", "Heat", "Lap Time", "Round", "Lap", "Best Q", "Fastest Lap", "Heat Color"])
            
            # Build pilot_id to index mapping
            pilot_id_to_index = {pid: idx for idx, pid in enumerate(pilot_df["Pilot id"])}
            pilot_names = pilot_df["Pilot Name"].tolist()
            
            # Get heats that belong to this raceclass (using shared helper)
            class_heat_ids = self._get_class_heat_ids(raceclass)
            
            # Build pilotrun -> heat_id mapping for efficient lookups
            pilotrun_heat_map, pilotrun_dict = self._build_pilotrun_heat_map(class_heat_ids)
            
            # Group pilot runs by pilot_id, but only include runs from heats in this class
            pilot_runs: Dict[int, List[int]] = {}
            for pilotrun_id, heat_id in pilotrun_heat_map.items():
                if heat_id in class_heat_ids:
                    pilotrun = pilotrun_dict.get(pilotrun_id)
                    if pilotrun and pilotrun.pilot_id != 0:
                        if pilotrun.pilot_id not in pilot_runs:
                            pilot_runs[pilotrun.pilot_id] = []
                        pilot_runs[pilotrun.pilot_id].append(pilotrun.id)
            
            # Get column names for consecutive data if available
            round_col = f"Best {consecutive_laps_base} Consecutive Lap Round"
            lap_col = f"Best {consecutive_laps_base} Consecutive Lap"
            nlaps_col = f"Best {consecutive_laps_base} Consecutive nLaps"
            
            # Verify consecutive_df has the expected columns (if provided)
            if win_condition == 4 and consecutive_df is not None and len(consecutive_df) > 0:
                if round_col not in consecutive_df.columns or lap_col not in consecutive_df.columns or nlaps_col not in consecutive_df.columns:
                    logger.warning(f"consecutive_df columns don't match consecutive_laps_base={consecutive_laps_base}. Available columns: {consecutive_df.columns.tolist()}")
                    # Try to infer the actual base from column names
                    for col in consecutive_df.columns:
                        if "Consecutive nLaps" in col:
                            try:
                                # Extract number from column name like "Best 5 Consecutive nLaps"
                                inferred_base = int(col.split()[1])
                                if inferred_base != consecutive_laps_base:
                                    logger.warning(f"Inferred consecutive_laps_base={inferred_base} from column name, but was passed {consecutive_laps_base}")
                                    consecutive_laps_base = inferred_base
                                    round_col = f"Best {consecutive_laps_base} Consecutive Lap Round"
                                    lap_col = f"Best {consecutive_laps_base} Consecutive Lap"
                                    nlaps_col = f"Best {consecutive_laps_base} Consecutive nLaps"
                                    break
                            except (ValueError, IndexError):
                                continue
            
            # Extract lap data for each pilot
            for pilot_id, run_ids in pilot_runs.items():
                if pilot_id not in pilot_id_to_index:
                    continue
                
                pilot_name = pilot_names[pilot_id_to_index[pilot_id]]
                
                # Get consecutive data for this pilot if available (win_condition 4)
                best_q_round = None
                best_q_start_lap = None
                best_q_nlaps = None
                if win_condition == 4 and consecutive_df is not None and len(consecutive_df) > 0:
                    if round_col in consecutive_df.columns and lap_col in consecutive_df.columns and nlaps_col in consecutive_df.columns:
                        pilot_consecutive = consecutive_df[consecutive_df["Pilot id"] == pilot_id]
                        if len(pilot_consecutive) > 0:
                            best_q_round = pilot_consecutive[round_col].values[0]
                            best_q_start_lap = pilot_consecutive[lap_col].values[0]
                            best_q_nlaps = pilot_consecutive[nlaps_col].values[0]
                
                # Process each run (round)
                for round_idx, run_id in enumerate(run_ids):
                    laps = self.rhapi.db.laps_by_pilotrun(run_id)
                    if not laps:
                        continue
                    
                    # Get heat_id (cache lookup)
                    heat_id = self._get_race_heat_id(laps[0])
                    
                    # Get actual round number, fallback to index+1 if not found
                    actual_round = self._get_round_number(laps[0], run_id)
                    if actual_round == 0:
                        actual_round = round_idx + 1  # Fallback to 1-indexed position
                    
                    # Process each lap
                    for lap_idx, lap in enumerate(laps):
                        if lap.deleted != 0:
                            continue
                        
                        lap_time_seconds = self._parse_lap_time(lap.lap_time_formatted)
                        
                        # Determine if this is a "Best Q" lap (for win_condition 4 - fastest consecutive)
                        # IMPORTANT: Never include holeshot (lap 0) in consecutive lap calculations
                        best_q = 0
                        if win_condition == 4 and best_q_round is not None:
                            if actual_round == best_q_round:  # Use actual round number
                                if best_q_start_lap is not None and best_q_nlaps is not None:
                                    # Exclude holeshot (lap_idx == 0) from consecutive calculations
                                    if lap_idx > 0:  # Skip holeshot
                                        # Adjust start_lap: if RotorHazard reports start_lap as 0 (holeshot),
                                        # we need to start from lap 1 instead. Otherwise use the reported value.
                                        if best_q_start_lap == 0:
                                            # RotorHazard included holeshot, so we start from lap 1
                                            adjusted_start_lap = 1
                                        else:
                                            # RotorHazard already excluded holeshot, use as-is
                                            adjusted_start_lap = best_q_start_lap
                                        
                                        # Check if this lap is within the consecutive range
                                        if (lap_idx >= adjusted_start_lap and 
                                            lap_idx < adjusted_start_lap + best_q_nlaps):
                                            best_q = 1
                        
                        # Fastest lap flag will be set after all laps are collected (for win_condition 3)
                        lap_data.append({
                            "Pilot id": pilot_id,
                            "Pilot Name": pilot_name,
                            "Heat": heat_id,
                            "Lap Time": lap_time_seconds,
                            "Round": actual_round,
                            "Lap": lap_idx,
                            "Best Q": best_q,
                            "Fastest Lap": 0,  # Will be set below
                            "Heat Color": heat_id
                        })
        
        except Exception as e:
            logger.error(f"Error extracting lap data: {e}", exc_info=True)
            # Return empty DataFrame with correct structure
            return pd.DataFrame(columns=["Pilot id", "Pilot Name", "Heat", "Lap Time", "Round", "Lap", "Best Q", "Fastest Lap", "Heat Color"])
        
        df = pd.DataFrame(lap_data)
        
        # Mark fastest laps for win_condition 3 (excluding holeshot) - vectorized operation
        if win_condition == 3 and len(df) > 0:
            # Find fastest lap for each pilot (excluding holeshot) - vectorized
            regular_laps_mask = df["Lap"] > 0
            if regular_laps_mask.any():
                # Group by pilot and find min time for each (on full df but only for regular laps)
                pilot_fastest_times = df[regular_laps_mask].groupby("Pilot id")["Lap Time"].min()
                # Create a mask for fastest laps
                fastest_mask = regular_laps_mask & df["Pilot id"].map(pilot_fastest_times).eq(df["Lap Time"])
                df.loc[fastest_mask, "Fastest Lap"] = 1
        
        return df
    
    def _generate_plot(self, pilot_df: pd.DataFrame, lap_df: pd.DataFrame, 
                      win_condition: int, event_name: str, raceformat_name: str = "", 
                      raceclass_name: str = "", consecutive_df: Optional[pd.DataFrame] = None,
                      consecutive_laps_base: int = 3) -> str:
        """Generate plot with appropriate extras based on win condition.
        
        Args:
            pilot_df: DataFrame with pilot information
            lap_df: DataFrame with lap data
            win_condition: Win condition integer (0-5)
            event_name: Event name string
            raceformat_name: Race format name
            raceclass_name: Race class name
            consecutive_df: DataFrame with consecutive data (for win_condition 4)
            consecutive_laps_base: Number of consecutive laps (for win_condition 4)
            
        Returns:
            HTML string of the plot
        """
        fig = graph_objects.Figure()
        
        # Calculate pilot best laps for y-axis labels (needed for all win conditions except 4)
        pilot_best_laps = lap_df[lap_df["Lap"] > 0].groupby("Pilot id")["Lap Time"].min()
        
        # Order pilots based on win condition
        if win_condition == 4 and consecutive_df is not None and len(consecutive_df) > 0:
            # For fastest consecutive, order by consecutive laps: full base first, then base-1, etc.
            consecutive_df = consecutive_df.copy()
            nlaps_col = f"Best {consecutive_laps_base} Consecutive nLaps"
            time_col = f"Best {consecutive_laps_base} Consecutive Lap Time"
            def get_priority(n_laps):
                if n_laps == 0:
                    return 999999
                return consecutive_laps_base - n_laps
            consecutive_df['_sort_priority'] = consecutive_df[nlaps_col].apply(get_priority)
            sorted_pilots_df = consecutive_df.sort_values(
                ["_sort_priority", time_col], 
                ascending=[True, True]
            )
            pilot_order = sorted_pilots_df["Pilot id"].tolist()
        else:
            # For other conditions, order by fastest single lap
            sorted_pilots = pilot_best_laps.sort_values(ascending=True)
            pilot_order = sorted_pilots.index.tolist()
        
        # Get unique heats for color mapping (for win_condition 1, 2)
        unique_heats = sorted(lap_df["Heat"].unique())
        # Generate colors for heats (use a color palette)
        heat_colors = {}
        color_palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        for idx, heat_id in enumerate(unique_heats):
            heat_colors[heat_id] = color_palette[idx % len(color_palette)]
        
        # Plot for each pilot
        for pilot_id in reversed(pilot_order):
            pilot_laps = lap_df[lap_df["Pilot id"] == pilot_id]
            if len(pilot_laps) == 0:
                continue
            
            pilot_info = pilot_df[pilot_df["Pilot id"] == pilot_id]
            if len(pilot_info) == 0:
                continue
            
            pilot_name = pilot_info["Pilot Name"].values[0]
            pilot_colour = pilot_info["Colour"].values[0]
            
            # Box plot for lap times (excluding holeshot)
            regular_laps = pilot_laps[pilot_laps["Lap"] > 0]
            if len(regular_laps) > 0:
                fig.add_trace(
                    graph_objects.Box(
                        name=pilot_name,
                        x=list(regular_laps["Lap Time"]),
                        boxpoints="all",
                        jitter=0.5,
                        pointpos=0,
                        marker=dict(symbol="circle-open", color="white", size=8),
                        line=dict(color=pilot_colour),
                        legendgroup=pilot_id,
                        hoverinfo='x',
                        showlegend=True
                    )
                )
            
            # Holeshots (yellow circles)
            holeshots = pilot_laps[pilot_laps["Lap"] == 0]
            if len(holeshots) > 0:
                fig.add_trace(
                    graph_objects.Scatter(
                        x=list(holeshots["Lap Time"]),
                        y=[pilot_name] * len(holeshots),
                        mode="markers",
                        marker=dict(symbol="circle-open", color="yellow", size=6),
                        legendgroup=pilot_id,
                        showlegend=False,
                        hoverinfo='x',
                        name=pilot_name
                    )
                )
            
            # Plot extras based on win condition
            if win_condition == 1 or win_condition == 2:
                # Connect laps in the same heat with a line
                for heat_id in unique_heats:
                    heat_laps = pilot_laps[(pilot_laps["Heat"] == heat_id) & (pilot_laps["Lap"] > 0)]
                    if len(heat_laps) > 1:  # Need at least 2 laps to connect
                        heat_color = heat_colors[heat_id]
                        # Sort by lap number for proper line connection
                        heat_laps_sorted = heat_laps.sort_values("Lap")
                        fig.add_trace(
                            graph_objects.Scatter(
                                x=list(heat_laps_sorted["Lap Time"]),
                                y=[pilot_name] * len(heat_laps_sorted),
                                mode="lines+markers",
                                marker=dict(symbol="circle", color=heat_color, size=8),
                                line=dict(color=heat_color, width=2),
                                legendgroup=pilot_id,
                                showlegend=False,
                                hoverinfo='x',
                                name=f"{pilot_name} - Heat {heat_id}"
                            )
                        )
            elif win_condition == 3:
                # Highlight fastest lap
                fastest_laps = pilot_laps[(pilot_laps["Fastest Lap"] == 1) & (pilot_laps["Lap"] > 0)]
                if len(fastest_laps) > 0:
                    fig.add_trace(
                        graph_objects.Scatter(
                            x=list(fastest_laps["Lap Time"]),
                            y=[pilot_name] * len(fastest_laps),
                            mode="markers",
                            marker=dict(symbol="star", color="gold", size=12, line=dict(width=2, color="darkgoldenrod")),
                            legendgroup=pilot_id,
                            showlegend=False,
                            hoverinfo='x',
                            name=f"{pilot_name} - Fastest Lap"
                        )
                    )
            elif win_condition == 4:
                # Connect the fastest consecutive laps with a line (magenta)
                best_q_laps = pilot_laps[pilot_laps["Best Q"] == 1]
                if len(best_q_laps) > 0:
                    # Sort by lap number to ensure proper line connection
                    best_q_sorted = best_q_laps.sort_values("Lap")
                    fig.add_trace(
                        graph_objects.Scatter(
                            x=list(best_q_sorted["Lap Time"]),
                            y=[pilot_name] * len(best_q_sorted),
                            mode="lines+markers",
                            marker=dict(symbol="circle", color="magenta", size=10, line=dict(width=2)),
                            line=dict(color="magenta", width=2, dash='dot'),
                            legendgroup=pilot_id,
                            showlegend=False,
                            hoverinfo='x',
                            name=pilot_name
                        )
                    )
            # win_condition 0 and 5: Nothing extra (just baseline plot)
        
        # Add legend entries
        fig.add_trace(graph_objects.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(symbol="circle-open", color="white", size=8),
            name="Raw Data Points"
        ))
        fig.add_trace(graph_objects.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(symbol="circle-open", color="yellow", size=6),
            name="Hole Shot"
        ))
        
        # Add win condition specific legend entries
        if win_condition == 3:
            fig.add_trace(graph_objects.Scatter(
                x=[None], y=[None],
                mode="markers",
                marker=dict(symbol="star", color="gold", size=12, line=dict(width=2, color="darkgoldenrod")),
                name="Fastest Lap"
            ))
        elif win_condition == 4:
            fig.add_trace(graph_objects.Scatter(
                x=[None], y=[None],
                mode="markers",
                marker=dict(symbol="circle", color="magenta", size=10),
                name=f"Best Consecutive {consecutive_laps_base} Lap"
            ))
        
        # Custom y-axis labels
        custom_ytics = []
        custom_ylabel = []
        
        for pilot_id in reversed(pilot_order):
            pilot_info = pilot_df[pilot_df["Pilot id"] == pilot_id]
            if len(pilot_info) == 0:
                continue
            
            pilot_name = pilot_info["Pilot Name"].values[0]
            custom_ytics.append(pilot_name)
            
            # Get label based on win condition
            if win_condition == 4 and consecutive_df is not None and len(consecutive_df) > 0:
                # For fastest consecutive, show consecutive lap info
                pilot_consecutive = consecutive_df[consecutive_df["Pilot id"] == pilot_id]
                if len(pilot_consecutive) > 0:
                    time_col = f"Best {consecutive_laps_base} Consecutive Lap Time"
                    nlaps_col = f"Best {consecutive_laps_base} Consecutive nLaps"
                    best_time = pilot_consecutive[time_col].values[0]
                    n_laps = pilot_consecutive[nlaps_col].values[0]
                    custom_ylabel.append(f"{pilot_name}<br>{n_laps}/{consecutive_laps_base} {best_time:.2f}s")
                else:
                    custom_ylabel.append(pilot_name)
            else:
                # For other conditions, show best lap time
                pilot_best_lap = pilot_best_laps.get(pilot_id, 0)
                if pilot_best_lap > 0:
                    custom_ylabel.append(f"{pilot_name}<br>Best: {pilot_best_lap:.2f}s")
                else:
                    custom_ylabel.append(pilot_name)
        
        # Get row height setting
        try:
            row_height = int(self.rhapi.db.option("event_plots_row_height", 100))
        except (ValueError, TypeError):
            row_height = 100
        
        # Set title based on win condition
        if win_condition == 4:
            # For fastest consecutive: "{raceformat_name} - {raceclass_name} - {consecutive_laps_base} Consecutive Laps - Lap Times"
            if raceformat_name and raceclass_name:
                plot_title = f"{raceformat_name} - {raceclass_name} - {consecutive_laps_base} Consecutive Laps - Lap Times"
            elif raceclass_name:
                plot_title = f"{raceclass_name} - {consecutive_laps_base} Consecutive Laps - Lap Times"
            else:
                plot_title = f"{consecutive_laps_base} Consecutive Laps - Lap Times"
        else:
            # Standard format: "{raceformat_name} - {raceclass_name} - Lap Times"
            if raceformat_name and raceclass_name:
                plot_title = f"{raceformat_name} - {raceclass_name} - Lap Times"
            elif raceclass_name:
                plot_title = f"{raceclass_name} - Lap Times"
            elif raceformat_name:
                plot_title = f"{raceformat_name} - Lap Times"
            else:
                plot_title = f"{event_name} - Lap Times"
        
        # Update layout
        fig.update_layout(
            template="plotly_dark",
            height=int(len(pilot_order) * row_height),
            xaxis=dict(
                tickmode="linear",
                dtick=2,
                title="Lap Time (s)",
                rangemode='tozero',
                showgrid=True,
                gridcolor='rgba(211,211,211,0.2)',
                gridwidth=0.5
            ),
            yaxis=dict(
                tickmode="array",
                tickvals=custom_ytics,
                ticktext=custom_ylabel
            ),
            title=plot_title,
            legend=dict(
                itemclick="toggle",
                itemdoubleclick="toggleothers"
            )
        )
        
        # Generate Plotly HTML (body content only)
        plot_html = fig.to_html(include_plotlyjs=PLOTLY_JS, full_html=False)
        
        # Wrap in HTML structure with RotorHazard CSS
        return self._wrap_plot_html(plot_html)
    
    def _validate_raceclass(self, raceclass) -> Tuple[bool, str]:
        """Validate raceclass object has required attributes.
        
        Args:
            raceclass: Race class object to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if raceclass is None:
            return False, "Race class is None"
        
        if not hasattr(raceclass, 'id'):
            return False, "Race class missing 'id' attribute"
        
        try:
            class_id = raceclass.id
            if class_id is None:
                return False, "Race class ID is None"
        except Exception as e:
            return False, f"Error accessing race class ID: {e}"
        
        return True, ""
    
    def generate_plot(self, raceclass) -> str:
        """Main method to generate plot for a race class.
        
        Args:
            raceclass: Race class object
            
        Returns:
            HTML string of the plot or error message
        """
        try:
            # Validate raceclass
            is_valid, error_msg = self._validate_raceclass(raceclass)
            if not is_valid:
                logger.error(f"Invalid raceclass: {error_msg}")
                return f"<html><body><h2>Error: Invalid race class</h2><p>{error_msg}</p><p><a href='/event_result'>Back to class list</a></p></body></html>"
            
            # Check if we have any races
            if len(self.rhapi.db.races) == 0:
                raceclass_name = getattr(raceclass, 'name', 'Unknown')
                return f"<html><body><h2>No race data available</h2><p>No races have been completed yet for class '{raceclass_name}'.</p><p><a href='/event_result'>Back to class list</a></p></body></html>"
            
            # Get event name
            try:
                event_name = self.rhapi.db.option("eventName", "Event")
            except:
                event_name = "Event"
            
            # Get raceclass name
            try:
                raceclass_name = raceclass.name if hasattr(raceclass, 'name') else ""
            except:
                raceclass_name = ""
            
            # Get raceformat name (class name) and consecutive_laps_base
            raceformat_name = ""
            raceformat = None
            consecutive_laps_base = 3  # Default fallback
            try:
                # Get raceformat from raceclass
                if hasattr(raceclass, 'format_id'):
                    format_id = raceclass.format_id
                    raceformat = self.rhapi.db.raceformat_by_id(format_id)
                    if raceformat and hasattr(raceformat, 'name'):
                        raceformat_name = raceformat.name
                elif hasattr(raceclass, 'raceformat'):
                    raceformat = raceclass.raceformat
                    if raceformat and hasattr(raceformat, 'name'):
                        raceformat_name = raceformat.name
                elif hasattr(raceclass, 'format'):
                    raceformat = raceclass.format
                    if raceformat and hasattr(raceformat, 'name'):
                        raceformat_name = raceformat.name
                
                # Get consecutive_laps_base from raceformat
                if raceformat:
                    # Try multiple possible attribute names
                    # Note: number_laps_win is for "first to X laps" races, not consecutive laps base
                    if hasattr(raceformat, 'consecutive_laps_base'):
                        consecutive_laps_base = int(raceformat.consecutive_laps_base)
                        if DEBUG:
                            logger.info(f"Got consecutive_laps_base from raceformat: {consecutive_laps_base}")
                    elif hasattr(raceformat, 'consecutives_base'):
                        consecutive_laps_base = int(raceformat.consecutives_base)
                        if DEBUG:
                            logger.info(f"Got consecutives_base from raceformat: {consecutive_laps_base}")
                    else:
                        # Don't use number_laps_win for consecutive laps - that's for "first to X laps" races
                        if DEBUG:
                            logger.info("Could not find consecutive_laps_base or consecutives_base in raceformat")
                        # Will try to get from raceclass_results later when we extract consecutive data
            except Exception as e:
                logger.warning(f"Error getting raceformat name or consecutive_laps_base: {e}")
            
            # Get win condition
            win_condition = self._get_win_condition(raceclass)
            if DEBUG:
                logger.info(f"Detected win_condition: {win_condition}")
            
            # Extract pilot data
            pilot_df = self._extract_pilot_data(raceclass)
            if len(pilot_df) == 0:
                raceclass_name = getattr(raceclass, 'name', 'Unknown')
                return f"<html><body><h2>No pilots found</h2><p>No pilots have completed races in class '{raceclass_name}'. Ensure pilots have completed races in this class.</p><p><a href='/event_result'>Back to class list</a></p></body></html>"
            
            # Extract consecutive data if needed (win_condition 4)
            consecutive_df = None
            if win_condition == 4:
                raceclass_results = self.rhapi.db.raceclass_results(raceclass)
                if raceclass_results:
                    consecutive_df = self._extract_consecutive_data(raceclass_results, consecutive_laps_base)
                    # If we couldn't get consecutive_laps_base from raceformat, try to get it from raceclass_results
                    if consecutive_laps_base == 3:  # Still using default
                        # Try to get from raceclass_results
                        if 'by_consecutives' in raceclass_results:
                            for pilot in raceclass_results['by_consecutives']:
                                if pilot.get('consecutives_base'):
                                    consecutive_laps_base = int(pilot['consecutives_base'])
                                    if DEBUG:
                                        logger.info(f"Got consecutives_base from raceclass_results: {consecutive_laps_base}")
                                    break
                        # If still not found, try to get from consecutive_df max nLaps
                        if consecutive_laps_base == 3 and len(consecutive_df) > 0:
                            # Get the maximum nLaps value, which should be the base
                            nlaps_col = f"Best {consecutive_laps_base} Consecutive nLaps"
                            max_nlaps = consecutive_df[nlaps_col].max()
                            if max_nlaps > 0:
                                consecutive_laps_base = int(max_nlaps)
                                # Re-extract with correct base
                                consecutive_df = self._extract_consecutive_data(raceclass_results, consecutive_laps_base)
                                if DEBUG:
                                    logger.info(f"Got consecutive_laps_base from consecutive_df max nLaps: {consecutive_laps_base}")
            
            # Validate consecutive_laps_base
            if win_condition == 4:
                if consecutive_laps_base <= 0 or consecutive_laps_base > 100:
                    logger.warning(f"Invalid consecutive_laps_base: {consecutive_laps_base}, using default 3")
                    consecutive_laps_base = 3
                    # Re-extract with corrected base if we have data
                    if consecutive_df is not None and len(consecutive_df) > 0:
                        raceclass_results = self.rhapi.db.raceclass_results(raceclass)
                        if raceclass_results:
                            consecutive_df = self._extract_consecutive_data(raceclass_results, consecutive_laps_base)
            
            # Extract lap data
            lap_df = self._extract_lap_data(raceclass, win_condition, pilot_df, consecutive_df, consecutive_laps_base)
            if len(lap_df) == 0:
                raceclass_name = getattr(raceclass, 'name', 'Unknown')
                return f"<html><body><h2>No lap data available</h2><p>No lap data found for class '{raceclass_name}'. Ensure races have been completed with lap times recorded.</p><p><a href='/event_result'>Back to class list</a></p></body></html>"
            
            # Generate plot based on win condition
            return self._generate_plot(pilot_df, lap_df, win_condition, event_name, raceformat_name, raceclass_name, consecutive_df, consecutive_laps_base)
        
        except Exception as e:
            logger.error(f"Error generating plot: {e}", exc_info=True)
            return f"<html><body><h2>Error generating plot</h2><p>{str(e)}</p></body></html>"
