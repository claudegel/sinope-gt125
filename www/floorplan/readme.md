## Steps to add Sinopé devices in your floorplan:

- First you need to create template sensor in configuration.yaml to get access to some of your devices attributes. The main attribute is directly available as state like room temperature for thermostat. For other attribute like heat_level you need to get them via template sensors.

```
sensor:
  - platform: template
    sensors:
      heat_level_bureau:  #Percentage of heat level for thermostat
        friendly_name: "Intensité bureau"
        unit_of_measurement: '%'
        value_template: "{{ state_attr('climate.sinope_climate_bureau', 'heat_level') }}"
      heat_level_spa:
        friendly_name: "Intensité spa"
        unit_of_measurement: '%'
        value_template: "{{ state_attr('climate.sinope_climate_spa', 'heat_level') }}"
      heat_level_plancher_cuisine: #floor thermostat heat level
        friendly_name: "Intensité plancher cuisine"
        unit_of_measurement: '%'
        value_template: "{{ state_attr('climate.neviweb130_climate_plancher_cuisin', 'heat_level') }}"
      temperature_sous_spa:  #temperature from water leak sensor
        friendly_name: "Température sous le spa"
        unit_of_measurement: 'oC'
        value_template: "{{ state_attr('sensor.neviweb130_sensor_spa', 'Temperature') }}"
```
- See ui-lovelace.yaml example in www/floorplan/
- To show room temperature create a text field element in your floorplan and link it to your thermostat entity. To show temperature in different color to reflect too cold or too hot temperature add this in your ui_lovelace.yaml:
```
            - class_template: |2
                   var temp = entity.attributes.current_temperature; if (temp < 18) return "temp-very-low"; else if (temp < 20) return "temp-below-average"; else if (temp < 23) return "temp-medium"; else return "temp-very-high";
              entities:
                - climate.sinope_climate_bureau
                - climate.sinope_climate_garage
                - climate.sinope_climate_salle_a_diner
                - climate.sinope_climate_salle_lavage
                - climate.sinope_climate_salon
                - climate.sinope_climate_solarium
                - climate.sinope_climate_spa
              name: climate
              text_template: >-
                ${entity.state ? entity.attributes.current_temperature + "°" :
                "undefined"}
```
- to get thermostat heat_level in your floorplan.svg add a square element in your floorplan and link the ID to your sensor previously created for heat_level.
```
            - entities:
                - climate.sinope_climate_bureau
                - climate.sinope_climate_garage
                - climate.sinope_climate_salle_a_diner
                - climate.sinope_climate_salle_lavage
                - climate.sinope_climate_salon
                - climate.sinope_climate_solarium
                - climate.sinope_climate_spa
              image_template: |2-
                 var imageName = ""; 
                 switch (entity.state) {
                   case "0": imageName = "heat-0"; break; 
                   case "1": imageName = "heat-1"; break; 
                   case "2": imageName = "heat-1"; break; 
                   case "3": imageName = "heat-1"; break; 
                   case "4": imageName = "heat-1"; break; 
                   case "5": imageName = "heat-1"; break; 
                   case "6": imageName = "heat-1"; break; 
                   case "7": imageName = "heat-1"; break; 
                   case "8": imageName = "heat-1"; break; 
                   case "9": imageName = "heat-1"; break; 
                   case "10": imageName = "heat-1"; break;
                   case "11": imageName = "heat-1"; break; 
                   case "12": imageName = "heat-1"; break; 
                   case "13": imageName = "heat-1"; break; 
                   case "14": imageName = "heat-1"; break; 
                   case "15": imageName = "heat-1"; break; 
                   case "16": imageName = "heat-1"; break; 
                   case "17": imageName = "heat-1"; break; 
                   case "18": imageName = "heat-1"; break; 
                   case "19": imageName = "heat-1"; break; 
                   case "20": imageName = "heat-1"; break; 
                   case "21": imageName = "heat-2"; break; 
                   case "22": imageName = "heat-2"; break; 
                   case "23": imageName = "heat-2"; break; 
                   case "24": imageName = "heat-2"; break; 
                   case "25": imageName = "heat-2"; break; 
                   case "26": imageName = "heat-2"; break; 
                   case "27": imageName = "heat-2"; break; 
                   case "28": imageName = "heat-2"; break; 
                   case "29": imageName = "heat-2"; break; 
                   case "30": imageName = "heat-2"; break; 
                   case "31": imageName = "heat-2"; break; 
                   case "32": imageName = "heat-2"; break; 
                   case "33": imageName = "heat-2"; break; 
                   case "34": imageName = "heat-2"; break; 
                   case "35": imageName = "heat-2"; break; 
                   case "36": imageName = "heat-2"; break; 
                   case "37": imageName = "heat-2"; break; 
                   case "38": imageName = "heat-2"; break; 
                   case "39": imageName = "heat-2"; break; 
                   case "40": imageName = "heat-2"; break; 
                   case "41": imageName = "heat-3"; break; 
                   case "42": imageName = "heat-3"; break; 
                   case "43": imageName = "heat-3"; break; 
                   case "44": imageName = "heat-3"; break; 
                   case "45": imageName = "heat-3"; break; 
                   case "46": imageName = "heat-3"; break; 
                   case "47": imageName = "heat-3"; break; 
                   case "48": imageName = "heat-3"; break; 
                   case "49": imageName = "heat-3"; break; 
                   case "50": imageName = "heat-3"; break; 
                   case "51": imageName = "heat-3"; break; 
                   case "52": imageName = "heat-3"; break; 
                   case "53": imageName = "heat-3"; break; 
                   case "54": imageName = "heat-3"; break; 
                   case "55": imageName = "heat-3"; break; 
                   case "56": imageName = "heat-3"; break; 
                   case "57": imageName = "heat-3"; break; 
                   case "58": imageName = "heat-3"; break; 
                   case "59": imageName = "heat-3"; break; 
                   case "60": imageName = "heat-3"; break; 
                   case "61": imageName = "heat-4"; break; 
                   case "62": imageName = "heat-4"; break; 
                   case "63": imageName = "heat-4"; break; 
                   case "64": imageName = "heat-4"; break; 
                   case "65": imageName = "heat-4"; break; 
                   case "66": imageName = "heat-4"; break; 
                   case "67": imageName = "heat-4"; break; 
                   case "68": imageName = "heat-4"; break; 
                   case "69": imageName = "heat-4"; break; 
                   case "70": imageName = "heat-4"; break; 
                   case "71": imageName = "heat-4"; break; 
                   case "72": imageName = "heat-4"; break; 
                   case "73": imageName = "heat-4"; break; 
                   case "74": imageName = "heat-4"; break; 
                   case "75": imageName = "heat-4"; break; 
                   case "76": imageName = "heat-4"; break; 
                   case "77": imageName = "heat-4"; break; 
                   case "78": imageName = "heat-4"; break; 
                   case "79": imageName = "heat-4"; break; 
                   case "80": imageName = "heat-4"; break; 
                   case "81": imageName = "heat-5"; break; 
                   case "82": imageName = "heat-5"; break; 
                   case "83": imageName = "heat-5"; break; 
                   case "84": imageName = "heat-5"; break; 
                   case "85": imageName = "heat-5"; break; 
                   case "86": imageName = "heat-5"; break; 
                   case "87": imageName = "heat-5"; break; 
                   case "88": imageName = "heat-5"; break; 
                   case "89": imageName = "heat-5"; break; 
                   case "90": imageName = "heat-5"; break; 
                   case "91": imageName = "heat-5"; break; 
                   case "92": imageName = "heat-5"; break; 
                   case "93": imageName = "heat-5"; break; 
                   case "94": imageName = "heat-5"; break; 
                   case "95": imageName = "heat-5"; break;
                   case "96": imageName = "heat-5"; break; 
                   case "97": imageName = "heat-5"; break; 
                   case "98": imageName = "heat-5"; break; 
                   case "99": imageName = "heat-5"; break; 
                   case "100": imageName = "heat-5"; break;
                 }       
                 return "/local/floorplan/" + imageName + ".svg";
```

- To get light control add a light icon «light.svg» in your floorplan and link the ID to the light entity. To ba able to directly toggle the light on/off add this in your ui_lovelace.yaml for each light and dimmer:

```
        rules:
            - action:
                service: homeassistant.toggle
              element: light.sinope_light_lumiere_solarium
              entity: light.sinope_light_lumiere_solarium
              more_info: true
            - action:
                service: homeassistant.toggle
              element: light.sinope_dimmer_dimmer_arr_garage
              entity: light.sinope_dimmer_dimmer_arr_garage
              more_info: true
              
            - entities:
                - light.sinope_light_lumiere_solarium
              states:
                - state: 'on'
                  class: 'lights-on'
                - state: 'off'
                  class: 'lights-off'
                  
            - entities:
                - light.sinope_dimmer_dimmer_arr_garage
              states:
                - state: 'on'
                  class: 'dimmer-on'
                - state: 'off'
                  class: 'dimmer-off'             
```
- to get water leak alarm from water leak sensor connected to your GT130 add your water icon to your floorplan and link it to the leak sensor entity. Icon will blink if water is detected.
```
            - entities:
                - sensor.neviweb130_sensor_spa
              image_template: |2-
                 var imageDrop = "";
                 switch (entity.state) {
                   case "ok": imageDrop = "drop"; break;
                   case "water": imageDrop = "leak"; break;
                 }       
                 return "/local/floorplan/" + imageDrop + ".svg";
              states:
                - state: 'water'
                  class: 'blinking'
```
- to show temperature from water leak sensor:
```
            - class_template: |2
                   var temp = entity.state; if (temp < 18) return "temp-very-low"; else if (temp < 20) return "temp-below-average"; else if (temp < 23) return "temp-medium"; else return "temp-very-high";
              entities:   
                - sensor.temperature_sous_spa
              name: spa
              text_template: >-
                ${entity.state ? "Sous spa " + entity.state + "°" :
                "undefined"}
```
- Finally create a floorplan.css file to setup your class to have everything working as you which. See example floorplan.css
