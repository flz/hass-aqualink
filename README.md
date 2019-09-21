# Aqualink Component for Home Assistant

## This component is DEPRECATED!

As of Home Assistant 0.99, iAqualink integration is supported out of the box.

## Installation

Run the following commands from your homeassistant directory:

```bash
bash$ mkdir -p custom_components
bash$ git clone https://github.com/flz/hass-aqualink custom_components/aqualink
```

## Configuration

### Home Assistant

Edit configuration.yaml and add a section such as:

```yaml
aqualink:
  username: your@email.com
  password: yourpassword
```

### Lovelace UI

Here's a simple (no-frills) page:

```yaml
  - badges: []
    cards:
      - entity: climate.pool
        name: Pool
        step_size: 1
        type: thermostat
      - entity: climate.spa
        name: Spa
        step_size: 1
        type: thermostat
      - entities:
          - entity: sensor.air_temp
          - entity: sensor.pool_temp
          - entity: light.pool_light
          - entity: switch.pool_pump
          - entity: switch.cleaner
          - entity: switch.sheer_dscnt
          - entity: switch.pool_heater
          - entity: switch.solar_heater
        show_header_toggle: false
        title: Pool
        type: entities
      - entities:
          - sensor.spa_temp
          - light.spa_light
          - switch.spa_pump
          - switch.air_blower
          - switch.spa_heater
        show_header_toggle: false
        title: Spa
        type: entities
    icon: 'mdi:swim'
    panel: false
    path: pool
    title: Pool
  ```

## Known Limitations

- The platform only supports a single pool. It wouldn't be a lot of work to fix but it most likely won't be an issue for most people.
- Only Pool systems are supported at this time.

## TODO

* Track requests/responses and dump into a debug file upon exception. This is to help troubleshooting and add missing support (e.g. dimmable/color lights, pool cover, ...)
* Use config_flow on the HA side. This currently depends on merging the platform with HA since the platform name needs to be added to homeassistant/helpers/config_flow.py.
* Look into merging code into home-assistant.
