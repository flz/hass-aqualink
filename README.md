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

The component supports a single pool. Most likely won't be an issue for most people.

## TODO

* Track requests/responses and dump into a debug file upon exception.
* Make the code async.
* Use config_flow on the HA side.
* Split API into its own repository, add to pypi.
* Look into merging code into home-assistant.