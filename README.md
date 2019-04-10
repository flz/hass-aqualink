# Aqualink Component for Home Assistant

## Installation

Run the following commands from your homeassistant directory:

```bash
bash$ mkdir -p custom_components
bash$ git clone https://github.com/flz/hass-aqualink custom_components/aqualink
```

## Configuration

Edit configuration.yaml and add a section such as:

```yaml
aqualink:
  username: your@email.com
  password: yourpassword
```

## Known Limitations

- The platform only supports a single pool. It wouldn't be a lot of work to fix but it most likely won't be an issue for most people.
- The platform currently assumes temperatures are Fahrenheit.

## TODO

* Track requests/responses and dump into a debug file upon exception. This is to help troubleshooting and add missing support (e.g. dimmable/color lights, pool cover, ...)
* Use config_flow on the HA side. This currently depends on merging the platform with HA since the platform name needs to be added to homeassistant/helpers/config_flow.py.
* Split API into its own repository, add to pypi. Will do once the code stabilizes.
* Look into merging code into home-assistant.