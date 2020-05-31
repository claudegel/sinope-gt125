Update:

To support [HACS](https://community.home-assistant.io/t/custom-component-hacs/121727), this repository has been broken up into two.
- sinope-gt125 for devices management via direct conection to the gt125 web gateway
- sinope-1 for devices management via [Neviweb](http://neviweb.com) portal.

As a replacement for Dark Sky api, I've added support for Open Weather Map api

If you already use this custom_component, make a backup of your file devices.json before first update via HACS. Devices.json will be removed. You'll need to copy your devices data to config/.storage/sinope_devices.json after first run of device.py (see below).
# Hassbian vs Hass.io
Those two HA platform use different location for  configuration. Now we have updated Sinope-GT125 so it can detect which platform you are using and adjust config location automatically.

# Home Assistant Sinope Custom Components (sinope-gt125)

Here is a custom component to suport [Sinopé technologies](http://sinopetech.com/) devices in [Home Assistant](http://www.home-assistant.io) via a direct connection to the GT125 router from 
Sinopé Technologies to interact with their smart devices like thermostats, light switches/dimmers and load controllers. It also supports some devices made by [Ouellet](http://www.ouellet.com/en-ca/products/thermostats-and-controls/neviweb%C2%AE-wireless-communication-controls.aspx).

## Supported Devices
Here is a list of currently supported devices. Basically, it's everything that can be added in Neviweb.
- Thermostats
  - Sinopé TH1120RF-3000 Line voltage thermostat
  - Sinopé TH1120RF-4000 Line voltage thermostat
  - Sinopé TH1121RF-3000 Thermostat for public areas
  - Sinopé TH1121RF-4000 Thermostat for public areas
  - Sinopé TH1300RF Floor heating thermostat
  - Sinopé TH1400RF Low voltage thermostat
  - Sinopé TH1500RF Double-pole thermostat
  - *Ouellet OTH2750-GT Line voltage thermostat
  - *Ouellet OTH3600-GA-GT Floor heating thermostat
- Lighting
  - Sinopé SW2500RF Light switch
  - Sinopé DM2500RF Dimmer 
- Specialized Control
  - Sinopé RM3200RF Load controller 40A
  - Sinopé RM3250RF Load controller 50A

*Not tested, but should be working well. Your feedback is appreciated if a device doesn't work.

## Prerequisite
You need to connect your devices to your GT125 web gateway before being able to interact with them within Home Assistant. Please refer to the instructions manual of your device or visit [Neviweb support](https://www.sinopetech.com/blog/support-cat/plateforme-nevi-web/).

There are two custom component giving you the choice to manage your devices via the neviweb portal or directly via your GT125 web gateway:
- [Neviweb](https://github.com/claudegel/sinope-1) custom component to manage your devices via neviweb portal.
- [Sinope](https://github.com/claudegel/sinope-gt125) custom component to manage your devices directly via your GT125 web gateway.

You need to install only one of them but both can be used at the same time on HA.

## Installation (see custom_components/GT125_connect.md for more specific info)
There are two methods to install this custom component:
- via HACS component (prefered method):
  - This repository is compatible with the Home Assistant Community Store ([HACS](https://community.home-assistant.io/t/custom-component-hacs/121727)).
  - After installing HACS, install 'Sinope GT125' from the store, and use the configuration.yaml example below.
- Manually via direct download:
  - Download the zip file of this repository using the top right, green download button.
  - Extract the zip file on your computer, then copy the entire `custom_components` folder inside your Home Assistant «config» directory (where you can find your `configuration.yaml` file).
    - Hassbian: /home/homeassistant/.homeassistant/
    - Hass.io: /config/
  - Your «config» directory should look like this:

    ```
    «config»/
      configuration.yaml
      .storage/
        sinope_devices.json
      custom_components/
        sinope/
          __init__.py
          light.py
          switch.py
          climate.py
          device.py
          crc8.py
      ...
    ```
    on Hass.io it look like it is very hard to add python library so we have added crc8.py to the sinope folder.
    
## Configuration

To enable Sinope management in your installation, add the following to your `configuration.yaml` file, then restart Home Assistant.

```yaml
# Example configuration.yaml entry
sinope:
  server: '<Ip adress of your GT125>'
  id: '<ID written on the back of your GT125>' non space
  api_key: '<Api_key received on first manual connection with the GT125>' #run device.py for that
  dk_key: '<your Dark sky key>' or 'your Open weather map key'
  my_weather: 'dark' for Dark sky api or 'owm' for Open weather map api
  my_city: '<the nearest city>' #needed to get sunrise and sunset hours for your location.
  scan_interval: 120 #you can go down to 60 if you want depending on how many devices you have to update. Default set to 180
  ```
## First run

To setup this custom_component, login via ssh to your Rpi and cd to the directory where you have copied the file. You don't need to edit the file device.py anymore but you will need to have the following data handy:
- IP adress of the GT125,
- GT125 device ID, written on the back of the device,
- Port number to connect to the GT125. should be 4550 (default),
- the required library crc8.py should be installed automatically. if not use this command: sudo pip3 install crc8. For python3.7,  use command: sudo python3.7 -m pip install crc8. For Hass.io you already run as root so you don't need sudo.
- For easyer install on Hass.io add the package SSH & Web Terminal. With this you don't need to install SSH and you'll be able to edit your config and run device.py directly in a web console inside of HA.
- to install HACS via that console run the commande:
`wget https://github.com/custom-components/hacs/archive/0.13.2.tar.gz`. Version number could be different.

Execute the command: 'sudo python3 device.py' in console (for python3.7: 'sudo python3.7 device.py'). Sudo is required for file permission fix. In Hass.io you don't need sudo. This is required to install the data above and to get the Api_Key and later the deviceID for each Sinopé devices connected to your GT125. On first run, device.py ask for IP, Api ID and port number then send a ping request to the GT125. It will then ask you to push de "WEB" button on the GT125. This will give you the Api Key.

- Once you get your Api_Key, all data will be written in the config file '«config»/.storage/sinope_devices.json'.
- On the next run of device.py, you will start to get the device_id for all devices connected to your GT125.  See devices discovery bellow.

You're ready to setup your Sinopé devices.

I've put lots of comment in the code so I think you will understand.

Main difference with Neviweb is that with the GT125 we don't have command to request all data and info 
from one device at once. We need to issue one data read request for each info or data we want. 
ex:
- open a connection
- login to the GT125
- send data read request for room temperature
- send data read request for setpoint temperature
- send data read request for mode (manual, auto, off, away)
- send data read request for heat level
- etc
- close connection and start over for next device.

This is the same for data write request but in that case we normally send one data like changing temperature or mode 
to one device. One exception is when we sent request to change mode to auto. We need to send correct time prior to send write request for auto mode.

For the data report request it is possible to send data to all device at once by using a specific deviceID = FFFFFFFF. 
It is used to send time, date, sunset and sunrise hour, outside temperature, set all device to away mode, etc, broadcasted to all device.

## Devices discovery
Look like the GT125 use a different deviceID then the Neviweb portal. Once you have your Api_key written in sinope_devices.json, you will need to run device.py to request deviceID for each devices on your network one by one. The program will wait for you to push on both button of your device to revceive there deviceID. Then, device.py will ask for device data like name, type and connected watt load. To get the list of devices types just type "h" when asked for device type. This will display all known types and then ask for your device type. If you don't have all information just hit enter to leave those fields blank. It will be possible to add missing data later. All devices ID and data will be written in the file 'config/.storage/sinope_devices.json' to insure that any new update won't overwrite it. Once you have all your devices, hit "q" at the end to quit the program. Edit 'config/.storage/sinope_devices.json' and add the name, type and wattage (for light devices) for each devices if needed. Light connected watt load is not measured by the light devices but instead written in Neviweb devices on setup of light devices. We need to write it to devices.json (kind of Neviweb portal equivalent) to finish the devices setup. ex:

```yaml
["IP", "Api Key", "Api ID", "PORT"] <- do not erase this line
["id", "name", "type", "watt"] <- do not erase or edit this line
["00470100", " ", " ", " "] <- once discovered by device.py, add devices info between the " "
["2e320100", "Office heating", "10", " "] <- thermostat ex.
["5a2c0100", "Office light", "102", "60"] <- light ex.
["6a560100", "Outside timer", "120", " "] <- power control ex.
["00470100", "Dimmer TV Room", "112", "110"] <- Dimmer ex.
```
For power switch devices, RM3250RF and RM3200RF, you need to push on the top blue ligth (with the wifi logo) to get the deviceID.
Each time you will add a new device to your GT125 you will need to run that setup.

## Troubleshooting
If you get a stack trace related to a Sinope component in your `home-assistant.log` file, you can file an issue in this repository.

You can also post in one of those threads to get help:
- https://community.home-assistant.io/t/sinope-line-voltage-thermostats/17157
- https://community.home-assistant.io/t/adding-support-for-sinope-light-switch-and-dimmer/38835

### Turning on Sinope debug messages in `home-assistant.log` file

To have a maximum of information to help you, please provide a snippet of your `home-assistant.log` file. I've added some debug log messages that could help diagnose the problem.

Add thoses lines to your `configuration.yaml` file
   ```yaml
   logger:
     default: warning
     logs:
       custom_components.sinope: debug
   ```
This will set default log level to warning for all your components, except for Sinope which will display more detailed messages.

## Customization
Install Custom UI and add the following in your code:

Icons for heat level: create folder www in the root folder .homeassistant/www
copy the six icons there. You can find them under local/www
feel free to improve my icons and let me know. (See icon_view2.png)

For each thermostat add this code in `customize.yaml`
```yaml
climate.sinope_climate_thermostat_name:
  templates:
    entity_picture: >
      if (attributes.heat_level < 1) return '/local/heat-0.png';
      if (attributes.heat_level < 21) return '/local/heat-1.png';
      if (attributes.heat_level < 41) return '/local/heat-2.png';
      if (attributes.heat_level < 61) return '/local/heat-3.png';
      if (attributes.heat_level < 81) return '/local/heat-4.png';
      return '/local/heat-5.png';
 ```  
 In `configuration.yaml` add this
```yaml
customize: !include customize.yaml
``` 
## Floorplan

Under www/floorplan you will find what can be done to add Sinopé devices in your floorplan with the icons you need in svg format.
My floorplan was created with inkscape and I use the same icon used for thermostat customisation.

## Current Limitations
- Home Assistant doesn't support operation mode selection for light and switch entities. So you won't see any dropdown list in the UI where you can switch between Auto and Manual mode. You can only see the current mode in the attributes. TODO: register a new service to change operation_mode and another one to set away mode.

- If you're looking for the away mode in the Lovelace 'thermostat' card, you need to click on the three dots button on the top right corner of the card. That will pop a window were you'll find the away mode switch at the bottom.

## TO DO
- Document each available services for every platforms + available attributes.
- Explore how to automatically setup sensors in HA that will report the states of a specific device attribute (i.e. the wattage of a switch device)
- Leave socket open to listen for events from devices state changes and answers from our data request. For now I open, send request, get result then close socket.
- Detect events from light dimer and switch so we can receive state changes from the GT125 without polling the devices (faster).
- Send time, date, sunset, sunrise once a day to each devices. Need to find out how to do that once a day at specific time.
- Send outside temperature to thermostat once per hour to have it displayed on the second display line. Maybe could be done from automation but would prefer to do it inside Sinope directly.
- Improve logging and debug.

## Contributing
You see something wrong or something that could be improved? Don't hesitate to fork me and send me pull requests.
