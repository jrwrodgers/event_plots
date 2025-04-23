# Event Plots Plugin for RotorHazard
This plugin to produces a statistical plot of the race event lap times per pilot

 
### Install
Install from RH Settings -> Plugins -> Browse Community Plugins -> Utilities -> Event Plots : Install

### Setup
Please ensure that under "Classes And Types" in the RH settings, the round type is set to "Count races per heat"

![image](https://github.com/jrwrodgers/event_plots/blob/main/assets/Round_type.png)


### Results
On the Results page in RotorHazard you will see new sections

![image](https://github.com/jrwrodgers/event_plots/blob/main/assets/Panels.png)

The Event Results Plot:
The colours are linked to the pilot colours. The plot will look something like this:

![image](https://github.com/jrwrodgers/event_plots/blob/main/assets/event_plot.png)

- Each pilot has a row ordered by fastest at the top
- The box and whisker is coloured accordingly to the pilot colour
- All lap times are shown
- Yellow lap times are the hole shots
- Pink lap times are the 3 fastest consecutive laps for each pilot
- Pilots can be hidden and shown by clicking on their name in the legend. This allows for close rival comparisons

The plots show the distribution of laptimes for any given pilot. The Box represents the interquartile range with a median line. More information on the what this style of plot can be seen here:
[https://en.wikipedia.org/wiki/Box_plot](https://en.wikipedia.org/wiki/Box_plot)

The Race Results Plots:
The colours are linked to the pilot colours. The plot will look something like this, showing the cumulative race time for each pilot. This should give insight into the race pace and position for each pilot.

![image](https://github.com/jrwrodgers/event_plots/blob/main/assets/race_results_plot.png)


Happy flying and keep those lap times consistent! :)
