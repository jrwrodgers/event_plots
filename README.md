# RotorHazardEvent Plots
This plugin to produces a statistical plot of the race event lap times per pilot

 
 ### Install

Log in via SSH and then execute the following commands : (NB check for official release or master branch)

```
cd ~
wget https://github.com/jrwrodgers/rh_rplots/archive/refs/heads/main.zip
unzip ./main.zip
cp -r ~/rh_rplots-main ~/RotorHazard/src/server/plugins/rh_rplots
rm -R ~/rh_rplots-main
rm ./main.zip
pip install -r ./RotorHazard/src/server/plugins/rh_rplots/requirements.txt
sudo systemctl restart rotorhazard.service
```

On the Format page in RotorHazard you will see a Lap Time Stats section
![image](https://github.com/jrwrodgers/event_plots/....)

Everytime results are saved or resaved the results plot is updated and can be viewed on the link. The colours are linked to the pilot colours. The plot will look something like this:

![image](https://github.com/jrwrodgers/event_plots/....)

The plots show the distribution of laptimes for any given pilot. The Box represents the interquartile range with a median line. More information on the what this style of plot can be seen here:
[https://en.wikipedia.org/wiki/Box_plot](https://en.wikipedia.org/wiki/Box_plot)

Happy flying and keep those lap times consistent! :)
