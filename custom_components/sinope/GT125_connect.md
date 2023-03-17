# Home Assistant Sinopé Custom Component with direct connection to your GT125

## Supported Devices

Same as Neviweb custom_component.

## Prerequisite

- CRC8-0.0.5 module from PyPI. Now suplied with this custom_component.
  
## Installation
The config folder is different depending if you are on Hassbian or Hass.io:
 - Hassbian: /home/homeassistant/.homeassistant/
 - Hass.io: /config/
### Via HACS:
- install hacs
- install sinope-GT125 via hacs store. It will be installed under «config»/custom_components/sinope

### Manually:
Create a directory named sinope under «config»/custom_components in your HA setup.

Copy the files in the sinope directory to your «config»/custom_components/sinope directory.

Once ready you will need to add entry for sinope in your configuration.yaml like this:

```yaml
# Example configuration.yaml entry
sinope:
  server: '<Ip adress of your GT125>'
  id: '<ID written on the back of your GT125>'
  api_key: '<Api_key received on first manual connection with the GT125>'
  server_2: '<Ip adress of your second GT125>' <Optional>
  id_2: '<ID written on the back of your second GT125>' <Optional> no space.
  api_key_2: '<Api_key received on first manual connection with the second GT125>' <Optional> #run device.py for that.
  my_city: '<the nearest city>' #needed to get sunrise and sunset hours for your location
  scan_interval: 120 #you can go down to 60 if you want depending on how many devices you have to update. default set to 180
```
DK_KEY and MY_WEATHER parameter have been removed.

## First run
To setup this custom_component, login to your Rpi via SSH and cd to the directory config/custom_components/sinope, where you have copied the files. You will need to have the following data handy:
- IP adress of the GT125,
- GT125 device ID, written on the back of the device,
- Port number to connect to the GT125. should be 4550 (default),
if you have to configure two GT125 you need to have both data handy. With device.py you can run it many time to add devices to any of your two GT125. If you have only one GT125 just homit the parameter for the second one.
- For easyer install on Hass.io add the package SSH & Web Terminal. With this you don't need to install SSH and you'll be able to edit your config and run device.py directly in a web console inside of HA.
- To findout if python is installed run: python --version
- For easyer install on Hass.io add the package SSH & Web Terminal. With this you don't need to install SSH and you'll be able to edit your config and run device.py directly in a web console inside of HA.
Execute the command: 'python device.py'. (for Python3.10, 'python3.10 device.py') This is required to get the Api_Key and the deviceID for each Sinopé devices connected to your GT125. For Hass.io you already run as root so you don't need sudo. On first run, device.py will ask you to enter the IP address of the GT125, the API ID written on the back of your GT125 and the port number (default 4550). It will send a ping request to the GT125 and will ask you to push de "WEB" button on the GT125. 
This will give you the Api Key. Then, device.py will create file 'config/.storage/sinope_devices.json' and write two line in it to store the above data.
For the second GT125, if you have two, the data will be written to the file 'config/.storage/sinope_devices_2.json'
- On the next run of device.py, you will start to get the device_id for all devices connected to your GT125.  See devices discovery bellow. Each time you run device.py it will ask for which Gt125, #1 or #2 you want to add devices.

You're ready to setup your Sinopé devices. I've put lots of comment in the code so I think you will understand.

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
Look like the GT125 use a different deviceID then Neviweb. Once you have your Api_key written in sinope_devices.json, you will need to run it to request deviceID for each devices on your network one by one. Device.py will ask for device name, type and connected watt load (for light and switch) for each device discovered. The program will loop to discover each device one by one. When finished, type "q" to leave the program. for each device discovery,the program will wait for you to push on both button of your device to receive the deviceID of that device. All devices id and data will be written in file sinope_devices.json and that file will be moved to config/.storage/sinope_devices.json to insure that any new update won't overwrite it. Once you have all your devices, edit sinope_devices.json and change the name, type and wattage (for light devices), if needed, for each devices. For device type you can get them at the top of each file climate.py, light.py and switch.py. You can also get them by typing "h" when prompted for type in device.py. Light connected watt load is not measured by the light devices but instead written in Neviweb on setup of light devices. We need to write it to devices.json (kind of Neviweb equivalent) to finish the devices setup.

```yaml
["IP", "Api Key", "Api ID", "PORT"] <- do not erase this line
["id", "name", "type", "watt"] <- do not erase or edit this line
["00470100", " ", " ", " "] <- once discovered by device.py, add devices info between the " "
["2e320100", "Office heating", "10", " "] <- thermostat ex.
["5a2c0100", "Office light", "102", "60"] <- light ex.
["6a560100", "Outside timer", "120", " "] <- power switch ex.
["00470100", "Dimmer TV Room", "112", "110"] <- Dimmer ex.
```

Each time you will add a new device to your GT125 you will need to do that setup.

See the file README.md to get more information about different services availables.

## TO DO
- Leave socket open to listen for events from devices state changes and answers from our data request. For now I open, send request, get result then close socket.
- Detect events from light dimer and switch so we can receive state changes from the GT125 without polling the devices (faster).
- Send outside temperature to thermostat at least once per hour to have it displayed on the second display line.
- Improve logging and debug.

Test it and let me know. Any help is welcome. There is still work to do to use it in HA.
