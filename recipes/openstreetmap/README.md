# OpenStreetMap

Geocoding, reverse geocoding, routing, and place search via [OpenStreetMap](https://www.openstreetmap.org) services ([Nominatim](https://nominatim.org/) + [OSRM](http://project-osrm.org/)).

## Endpoints

| Endpoint | Tool Name | Description |
|---|---|---|
| `geocode` | `geocode` | Address/place name → coordinates |
| `reverse` | `reverse_geocode` | Coordinates → address |
| `route` | `calculate_route` | Route between waypoints with distance, duration, and turn-by-turn steps |
| `search` | `search_places` | Search for places/POIs, optionally within a radius of a location |

## Usage

### Geocode

```
GET /openstreetmap/geocode?q=Brandenburger Tor, Berlin
```

Returns up to 5 results with lat/lon, address details, and OSM links.

### Reverse Geocode

```
GET /openstreetmap/reverse?q=52.5163,13.3777
```

Format: `q=latitude,longitude`

Latitude must be between -90 and 90, longitude between -180 and 180, and
reverse geocoding accepts exactly one coordinate pair.

### Route

```
GET /openstreetmap/route?q=52.52,13.405;48.8566,2.3522
GET /openstreetmap/route?q=52.52,13.405;50.1109,8.6821;48.8566,2.3522&profile=driving
```

Format: `q=lat1,lon1;lat2,lon2[;lat3,lon3;...]`

- Supports multiple waypoints (separated by `;`)
- `profile` parameter: `driving` (default), `walking`, `cycling`
- Returns distance (km), duration (minutes/hours), and turn-by-turn directions

### Search Places

```
GET /openstreetmap/search?q=restaurant
GET /openstreetmap/search?q=pharmacy&lat=52.52&lon=13.405&radius=2000
```

- `lat`, `lon` — center point for nearby search
- `radius` — search radius in meters (default: ~5km)

`lat` and `lon` must be provided together; zero-valued coordinates are valid.

## Requirements

Configure provider endpoints before enabling the recipe:

```bash
export NOMINATIM_BASE_URL="https://nominatim.your-provider.example"
export OSRM_BASE_URL="https://osrm.your-provider.example"
export OPENSTREETMAP_USER_AGENT="your-app/1.0 (ops@example.com)"
```

Use a self-hosted deployment or a provider whose terms permit your workload.
Private-network endpoints are blocked unless the Web2API operator explicitly sets
`WEB2API_ALLOW_PRIVATE_NETWORK=true`.

## Notes

- The recipe enforces at most one Nominatim request per second per process.
- The public Nominatim service's [usage policy](https://operations.osmfoundation.org/policies/nominatim/)
  does not permit generic proxy/no-code access, so it is no longer the default.
- The OSRM demo server is for evaluation and is no longer the default.
