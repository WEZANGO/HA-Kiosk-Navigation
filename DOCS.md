# HERE Traffic Dashboards

This Home Assistant app (formerly called an add-on) stores one shared HERE API key in its Supervisor configuration and lets you create multiple named route displays through its Web UI. Route settings are stored persistently in the add-on data volume and included in Home Assistant backups. The Dark setting uses HERE Maps JavaScript API v3.2's native HARP `mapnight` base layer and matching traffic overlay. Choose **Automatic (device setting)** to follow the browser/device light-or-dark preference, including changes while the display is open. Full-screen and Compact displays have independent visual and congestion-threshold settings.

## Install locally

1. Copy this entire `here-traffic-addon` folder to Home Assistant's `addons` directory, for example `/addons/here_traffic_dashboards`.
2. In Home Assistant, go to **Settings → Add-ons → Add-on store**, select the overflow menu, then **Check for updates**.
3. Find **HERE Traffic Dashboards**, install it, and open its **Configuration** tab.
4. Enter the shared HERE API key and start the app.
5. Open the app's Web UI from the sidebar. Create one or more named dashboards.

## Add route displays to a Home Assistant dashboard

The app prints a Full and Compact URL for every named dashboard. If the Web UI was opened through Home Assistant, those URLs are ingress URLs and can be pasted directly into an Iframe card.

```yaml
type: iframe
url: /api/hassio_ingress/YOUR-APP-PATH/display/morning-commute
aspect_ratio: 75%
```

Use the Compact URL in a smaller dashboard card:

```yaml
type: iframe
url: /api/hassio_ingress/YOUR-APP-PATH/card/morning-commute
aspect_ratio: 55%
```

Do not type `YOUR-APP-PATH` manually: copy the exact URL from the app UI. The direct LAN alternatives are `http://YOUR-HOME-ASSISTANT:8099/display/ID` and `/card/ID`. Use ingress where possible because it uses Home Assistant authentication.

## Security

The API key is stored in Home Assistant's app configuration, rather than browser local storage. The display still has to receive a browser-compatible HERE API key to render an interactive map, so restrict that key to your Home Assistant hostname(s) and the required HERE products. Do not use a privileged server secret as the browser key.

## Development note

This is a local app package, not a published add-on repository. Before publishing it, replace the placeholder URL in `config.yaml`, host the package in a repository, and add icons/translations.
