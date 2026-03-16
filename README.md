# Event Plots Plugin for RotorHazard
This plugin to produces a statistical plot of the race event lap times per pilot

 
### Install
Install from RH Settings -> Plugins -> Browse Community Plugins -> Utilities -> Event Plots : Install

### Settings
On the Results page in RotorHazard you will see new sections
![image](https://github.com/jrwrodgers/event_plots/blob/main/assets/settings.png)

The Stats row height changes the height of each pilot row - for fewer pilots you may wish to increase this. For more pilots reduce this.
The Max Lap time(s) sets the width of the plot to trim any large lap times

If you have multiple classes the link will lead to a webpage to select the class you wish to plot:
![image](https://github.com/jrwrodgers/event_plots/blob/main/assets/plot_selection.png)

If you want to go straight to the link then use /event_plots/1 or /event_plots/2 etc..

The Event Results Plot:
The colours are linked to the pilot colours. The plot will look something like this:

![image](https://github.com/jrwrodgers/event_plots/blob/main/assets/event_plot.png)

- Each pilot has a row ordered by fastest at the top
- The box and whisker is coloured accordingly to the pilot colour
- All lap times are shown
- Yellow lap times are the hole shots
- Pink lap times are the 3 fastest consecutive laps for each pilot
- If it is a race format then lap times are linked if they are from the same race
- Pilots can be hidden and shown by clicking on their name in the legend. This allows for close rival comparisons

The plots show the distribution of laptimes for any given pilot. The Box represents the interquartile range with a median line. More information on the what this style of plot can be seen here:
[https://en.wikipedia.org/wiki/Box_plot](https://en.wikipedia.org/wiki/Box_plot)


Happy flying and keep those lap times consistent! :)
