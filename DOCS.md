# HERE Traffic Dashboards

This Home Assistant app (formerly called an add-on) stores one shared HERE API key in its Supervisor configuration and lets you create multiple named route displays through its Web UI. Route settings are stored persistently in the add-on data volume and included in Home Assistant backups. The Dark setting uses HERE Maps JavaScript API v3.2's native HARP `mapnight` base layer and matching traffic overlay. Choose **Automatic (device setting)** to follow the browser/device light-or-dark preference, including changes while the display is open. Full-screen and Compact displays have independent visual and congestion-threshold settings.

Each display also has its own **Refresh interval**. It re-runs the traffic-aware HERE route request, updating the route colouring, travel time, and delay. The default is every five minutes; choose Off to disable automatic refresh.

Full-screen and Compact settings each include a **Route outline colour**. The outline is independent of the green-to-red live traffic colours drawn along the route, so it keeps the route legible over any map style.

Each display has separate presentation settings: optional centered title (top or bottom), title size, font, and background; plus corner-card size and either rounded cards or a vignette treatment that fades into the corresponding map corner.

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

## Route images in notifications

Every display also has an **Image** URL: `…/image/ID.png`. It is a live PNG of the route: the map with the traffic-coloured route line and the start/end markers, and nothing else — a notification's own text carries the numbers, so the image stays a clean map. If the display has a **Title** set, that is drawn too; otherwise the image is purely map and route. Home Assistant consumes it like any other image, so it can be attached to a notification or exposed as a camera.

The PNG is rendered by the app itself from HERE Raster Tiles plus the HERE routing API: no browser, no screenshot service, and nothing extra to install. The route colouring, markers and title use the same styling as the display, so the image matches the kiosk in either map appearance.

| Parameter | Effect |
| --- | --- |
| `?theme=dark` / `?theme=light` | Chooses the basemap. Without it, the display's own **Map appearance** applies — and **Automatic** renders dark, because the image is fetched by Home Assistant or the phone, neither of which tells the renderer what the device's appearance is. Use `?theme=light` for a light map (daytime, or a phone in light mode). |
| `?w=` and `?h=` | Image size, default 1080×540 and maximum 2048 each. A wide banner (`?w=1200&h=400`) suits a notification; a square (`?w=800&h=800`) suits a dashboard picture card. |

The URL shown in the app carries the shared access token (`?auth=…`) because Home Assistant and the phone fetch the image outside the ingress session.

### Attach the map to a notification

```yaml
actions:
  - service: notify.mobile_app_your_phone
    data:
      title: Morning commute
      message: "Leave now — 28 min, +7 min delay"
      data:
        image: http://local-here-traffic-dashboards:8099/image/morning-commute.png?auth=YOUR-TOKEN
```

Android downloads that image and shows it in the notification. Add `&theme=light` (or `dark`) to control the map appearance for that recipient. The iOS companion app instead takes `data.attachment`:

```yaml
      data:
        attachment:
          url: http://local-here-traffic-dashboards:8099/image/morning-commute.png?auth=YOUR-TOKEN
          content-type: png
```

### Expose it as a camera

A camera entity means Home Assistant fetches the image, so it also works when you are away from home and can be used in dashboards, `camera.snapshot`, and notifications of any kind:

```yaml
camera:
  - platform: generic
    name: Commute map
    still_image_url: http://local-here-traffic-dashboards:8099/image/morning-commute.png?auth=YOUR-TOKEN
    scan_interval: 60
```

Use a host Home Assistant can reach: `local-here-traffic-dashboards` (an app installed from a local folder is reachable inside Home Assistant as `local_<slug>` → `local-here-traffic-dashboards`; an app from a GitHub repository uses its hashed repository id instead), or the Home Assistant host's LAN address such as `http://192.168.1.10:8099`. The image is reused for 60 seconds at a time, so even a camera polling every few seconds does not re-render on every request.

## Security

The API key is stored in Home Assistant's app configuration, rather than browser local storage. The display still has to receive a browser-compatible HERE API key to render an interactive map, so restrict that key to your Home Assistant hostname(s) and the required HERE products. Do not use a privileged server secret as the browser key.

## Development note

This is a local app package, not a published add-on repository. Before publishing it, replace the placeholder URL in `config.yaml`, host the package in a repository, and add icons/translations.
