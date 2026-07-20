"""OpenStreetMap scraper — geocoding, reverse geocoding, routing, and place search.

Uses operator-configured Nominatim (geocoding/search) and OSRM (routing)
services. No browser is needed.
"""

from __future__ import annotations

import asyncio
import os
import re
from time import monotonic
from typing import Any
from urllib.parse import urlencode

import httpx
from playwright.async_api import Page
from web2api.network_security import validate_httpx_request
from web2api.scraper import BaseScraper, ScrapeResult

NOMINATIM_BASE_ENV = "NOMINATIM_BASE_URL"
OSRM_BASE_ENV = "OSRM_BASE_URL"
USER_AGENT = os.environ.get(
    "OPENSTREETMAP_USER_AGENT",
    "web2api/1.0 (+https://github.com/Endogen/web2api)",
)
HTTP_TIMEOUT = 15
_NOMINATIM_LOCK = asyncio.Lock()
_LAST_NOMINATIM_REQUEST = 0.0


def _configured_base(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip().rstrip("/")
    if not value:
        raise RuntimeError(
            f"{env_name} is required; configure a self-hosted or contracted provider endpoint"
        )
    return value


async def _get_json(url: str, *, nominatim: bool = False) -> Any:
    """GET JSON with outbound validation and a one-request-per-second limiter."""
    global _LAST_NOMINATIM_REQUEST
    if nominatim:
        async with _NOMINATIM_LOCK:
            delay = 1.0 - (monotonic() - _LAST_NOMINATIM_REQUEST)
            if delay > 0:
                await asyncio.sleep(delay)
            _LAST_NOMINATIM_REQUEST = monotonic()

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=HTTP_TIMEOUT,
        event_hooks={"request": [validate_httpx_request]},
    ) as client:
        response = await client.get(
            url,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        return response.json()


async def _geocode(query: str) -> list[dict[str, Any]]:
    """Forward geocode: address/place → coordinates."""
    base = _configured_base(NOMINATIM_BASE_ENV)
    query_params = {"q": query, "format": "jsonv2", "addressdetails": 1, "limit": 5}
    url = f"{base}/search?{urlencode(query_params)}"
    results = await _get_json(url, nominatim=True)

    items = []
    for r in results:
        address = r.get("address", {})
        items.append({
            "title": r.get("display_name", ""),
            "url": (
                f"https://www.openstreetmap.org/{r.get('osm_type', 'node')}"
                f"/{r.get('osm_id', '')}"
            ),
            "latitude": r.get("lat", ""),
            "longitude": r.get("lon", ""),
            "type": r.get("type", ""),
            "category": r.get("category", ""),
            "importance": str(round(r.get("importance", 0), 4)),
            "country": address.get("country", ""),
            "city": address.get("city", address.get("town", address.get("village", ""))),
            "postcode": address.get("postcode", ""),
        })
    return items


async def _reverse_geocode(lat: str, lon: str) -> list[dict[str, Any]]:
    """Reverse geocode: coordinates → address."""
    base = _configured_base(NOMINATIM_BASE_ENV)
    query_params = {"lat": lat, "lon": lon, "format": "jsonv2", "addressdetails": 1}
    url = f"{base}/reverse?{urlencode(query_params)}"
    r = await _get_json(url, nominatim=True)

    if "error" in r:
        raise RuntimeError(f"Reverse geocode failed: {r['error']}")

    address = r.get("address", {})
    return [{
        "title": r.get("display_name", ""),
        "url": f"https://www.openstreetmap.org/{r.get('osm_type', 'node')}/{r.get('osm_id', '')}",
        "latitude": r.get("lat", ""),
        "longitude": r.get("lon", ""),
        "type": r.get("type", ""),
        "category": r.get("category", ""),
        "road": address.get("road", ""),
        "house_number": address.get("house_number", ""),
        "city": address.get("city", address.get("town", address.get("village", ""))),
        "state": address.get("state", ""),
        "country": address.get("country", ""),
        "postcode": address.get("postcode", ""),
    }]


async def _route(
    waypoints: list[tuple[str, str]],
    profile: str = "driving",
) -> list[dict[str, Any]]:
    """Calculate route between waypoints using OSRM.

    waypoints: list of (lat, lon) tuples
    profile: driving, walking, cycling
    """
    # OSRM uses lon,lat order
    coords = ";".join(f"{lon},{lat}" for lat, lon in waypoints)
    base = _configured_base(OSRM_BASE_ENV)
    url = f"{base}/route/v1/{profile}/{coords}?overview=full&geometries=geojson&steps=true"
    data = await _get_json(url)

    if data.get("code") != "Ok":
        raise RuntimeError(f"Routing failed: {data.get('message', data.get('code', 'unknown'))}")

    items = []
    for route in data.get("routes", []):
        distance_km = round(route["distance"] / 1000, 2)
        duration_min = round(route["duration"] / 60, 1)
        duration_h = round(route["duration"] / 3600, 2)

        # Extract turn-by-turn steps
        steps = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                if step.get("maneuver", {}).get("type") == "depart" and not steps:
                    steps.append(f"Depart on {step.get('name', 'unknown road')}")
                elif step.get("name"):
                    modifier = step.get("maneuver", {}).get("modifier", "")
                    stype = step.get("maneuver", {}).get("type", "")
                    dist = round(step["distance"] / 1000, 1) if step.get("distance") else 0
                    if stype == "arrive":
                        steps.append("Arrive at destination")
                    else:
                        direction = f"{stype} {modifier}".strip()
                        steps.append(f"{direction} onto {step['name']} ({dist} km)")

        items.append({
            "title": f"Route: {distance_km} km, {duration_min} min",
            "distance_km": str(distance_km),
            "distance_m": str(round(route["distance"])),
            "duration_min": str(duration_min),
            "duration_hours": str(duration_h),
            "waypoints": str(len(waypoints)),
            "steps": " → ".join(steps[:15]) if steps else "Direct route",
            "summary": f"{distance_km} km in {duration_h} hours ({duration_min} min) via {profile}",
        })
    return items


async def _search_places(
    query: str,
    lat: float | str = "",
    lon: float | str = "",
    radius: float | str = "",
) -> list[dict[str, Any]]:
    """Search for places/POIs, optionally near a location."""
    params: dict[str, str] = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": "1",
        "limit": "10",
    }
    if lat and lon:
        params["lat"] = lat
        params["lon"] = lon
        # viewbox for nearby search
        r_deg = float(radius) / 111000 if radius else 0.05  # ~5km default
        params["viewbox"] = (
            f"{float(lon) - r_deg},{float(lat) + r_deg},"
            f"{float(lon) + r_deg},{float(lat) - r_deg}"
        )
        params["bounded"] = "1"

    base = _configured_base(NOMINATIM_BASE_ENV)
    url = f"{base}/search?{urlencode(params)}"
    results = await _get_json(url, nominatim=True)

    items = []
    for r in results:
        address = r.get("address", {})
        items.append({
            "title": r.get("display_name", ""),
            "url": (
                f"https://www.openstreetmap.org/{r.get('osm_type', 'node')}"
                f"/{r.get('osm_id', '')}"
            ),
            "latitude": r.get("lat", ""),
            "longitude": r.get("lon", ""),
            "type": r.get("type", ""),
            "category": r.get("category", ""),
            "city": address.get("city", address.get("town", address.get("village", ""))),
            "country": address.get("country", ""),
        })
    return items


def _parse_coords(text: str) -> list[tuple[str, str]]:
    """Parse coordinate pairs from text. Accepts:
    - "52.52,13.405" (single point)
    - "52.52,13.405;48.8566,2.3522" (multiple waypoints)
    """
    pairs = []
    for part in text.split(";"):
        part = part.strip()
        match = re.match(r"^(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)$", part)
        if match:
            pairs.append((match.group(1), match.group(2)))
    return pairs


class Scraper(BaseScraper):
    """OpenStreetMap geocoding, routing, and search."""

    requires_browser = False

    def supports(self, endpoint: str) -> bool:
        return endpoint in {"geocode", "reverse", "route", "search"}

    async def scrape(
        self, endpoint: str, page: Page | None, params: dict[str, Any]
    ) -> ScrapeResult:
        query = (params.get("query") or "").strip()
        if not query:
            raise RuntimeError("Missing query — pass q=<query>")

        if endpoint == "geocode":
            items = await _geocode(query)

        elif endpoint == "reverse":
            coords = _parse_coords(query)
            if not coords:
                raise RuntimeError(
                    "Invalid coordinates. Use format: q=52.52,13.405"
                )
            lat, lon = coords[0]
            items = await _reverse_geocode(lat, lon)

        elif endpoint == "route":
            coords = _parse_coords(query)
            if len(coords) < 2:
                raise RuntimeError(
                    "Need at least 2 waypoints. Use format: q=52.52,13.405;48.8566,2.3522"
                )
            profile = params.get("profile", "driving")
            if profile not in ("driving", "walking", "cycling"):
                profile = "driving"
            items = await _route(coords, profile)

        elif endpoint == "search":
            lat = params.get("lat", "")
            lon = params.get("lon", "")
            radius = params.get("radius", "")
            items = await _search_places(query, lat, lon, radius)

        else:
            raise RuntimeError(f"Unknown endpoint: {endpoint}")

        return ScrapeResult(items=items, current_page=1, has_next=False)
