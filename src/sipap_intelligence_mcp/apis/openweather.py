"""OpenWeatherMap API client for weather forecasts.

Provides weather data for match locations and times.
Free tier: 60 calls/min, 1,000 calls/day
"""

from datetime import UTC, datetime
from typing import Any

import httpx


class OpenWeatherMapClient:
    """
    Client for OpenWeatherMap API.

    Fetches weather forecasts for specific locations and times.
    Used to get weather conditions for match venues.

    API Documentation: https://openweathermap.org/api
    """

    BASE_URL = "https://api.openweathermap.org/data/2.5"

    def __init__(self, api_key: str, timeout: float = 10.0):
        """
        Initialize OpenWeatherMap client.

        Args:
            api_key: OpenWeatherMap API key
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OpenWeatherMapClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def get_forecast_by_coords(
        self,
        lat: float,
        lon: float,
        forecast_time: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Get weather forecast for specific coordinates and time.

        Uses 5-day forecast API and selects the closest forecast to target time.

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)
            forecast_time: Target forecast time (default: now)

        Returns:
            Weather forecast dictionary with:
                - temperature: Temperature in Celsius
                - feels_like: Feels like temperature
                - humidity: Humidity percentage
                - pressure: Atmospheric pressure
                - wind_speed: Wind speed in m/s
                - wind_direction: Wind direction in degrees
                - precipitation: Precipitation type (none, rain, snow)
                - precipitation_probability: Probability 0-1
                - clouds: Cloud coverage percentage
                - visibility: Visibility in meters
                - weather_main: Main weather condition
                - weather_description: Detailed description
                - forecast_time: ISO timestamp of forecast

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If coordinates are invalid
        """
        if not -90 <= lat <= 90:
            raise ValueError(f"Invalid latitude: {lat}. Must be between -90 and 90")
        if not -180 <= lon <= 180:
            raise ValueError(f"Invalid longitude: {lon}. Must be between -180 and 180")

        forecast_time = forecast_time or datetime.now(UTC)

        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        # 5-day forecast API (3-hour intervals)
        url = f"{self.BASE_URL}/forecast"
        params: dict[str, str | int | float] = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",  # Celsius
            "cnt": 40,  # 5 days * 8 forecasts/day
        }

        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # Find forecast closest to target time
        forecasts = data.get("list", [])
        if not forecasts:
            raise ValueError("No forecasts available from API")

        closest_forecast = min(
            forecasts,
            key=lambda f: abs(
                datetime.fromtimestamp(f["dt"], UTC) - forecast_time
            ).total_seconds(),
        )

        # Extract weather data
        main = closest_forecast["main"]
        weather = closest_forecast["weather"][0]
        wind = closest_forecast["wind"]
        clouds = closest_forecast["clouds"]

        # Determine precipitation type and probability
        precipitation = "none"
        precipitation_prob = closest_forecast.get("pop", 0.0)  # Probability of precipitation

        if "rain" in closest_forecast:
            precipitation = "rain"
        elif "snow" in closest_forecast:
            precipitation = "snow"

        return {
            "temperature": main["temp"],
            "feels_like": main["feels_like"],
            "humidity": main["humidity"],
            "pressure": main["pressure"],
            "wind_speed": wind["speed"],
            "wind_direction": wind.get("deg", 0),
            "precipitation": precipitation,
            "precipitation_probability": precipitation_prob,
            "clouds": clouds["all"],
            "visibility": closest_forecast.get("visibility", 10000),
            "weather_main": weather["main"],
            "weather_description": weather["description"],
            "forecast_time": datetime.fromtimestamp(closest_forecast["dt"], UTC).isoformat(),
        }

    async def get_current_weather_by_coords(
        self,
        lat: float,
        lon: float,
    ) -> dict[str, Any]:
        """
        Get current weather for specific coordinates.

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)

        Returns:
            Current weather dictionary (same structure as forecast)

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If coordinates are invalid
        """
        if not -90 <= lat <= 90:
            raise ValueError(f"Invalid latitude: {lat}. Must be between -90 and 90")
        if not -180 <= lon <= 180:
            raise ValueError(f"Invalid longitude: {lon}. Must be between -180 and 180")

        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        url = f"{self.BASE_URL}/weather"
        params: dict[str, str | int | float] = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
        }

        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # Extract weather data
        main = data["main"]
        weather = data["weather"][0]
        wind = data["wind"]
        clouds = data["clouds"]

        # Determine precipitation
        precipitation = "none"
        if "rain" in data:
            precipitation = "rain"
        elif "snow" in data:
            precipitation = "snow"

        return {
            "temperature": main["temp"],
            "feels_like": main["feels_like"],
            "humidity": main["humidity"],
            "pressure": main["pressure"],
            "wind_speed": wind["speed"],
            "wind_direction": wind.get("deg", 0),
            "precipitation": precipitation,
            "precipitation_probability": 1.0 if precipitation != "none" else 0.0,
            "clouds": clouds["all"],
            "visibility": data.get("visibility", 10000),
            "weather_main": weather["main"],
            "weather_description": weather["description"],
            "forecast_time": datetime.now(UTC).isoformat(),
        }

    async def get_weather_by_coordinates(
        self,
        lat: float,
        lon: float,
    ) -> dict[str, Any]:
        """
        Get current weather by coordinates (convenience method).

        Alias for get_current_weather_by_coords() to match weather tools expectations.

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)

        Returns:
            Current weather dictionary

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If coordinates are invalid
        """
        return await self.get_current_weather_by_coords(lat=lat, lon=lon)

    async def get_weather_by_city(
        self,
        city: str,
        country_code: str | None = None,
    ) -> dict[str, Any]:
        """
        Get current weather by city name.

        Uses OpenWeatherMap geocoding API to convert city to coordinates,
        then fetches current weather.

        Args:
            city: City name (e.g., "London", "New York")
            country_code: Optional ISO 3166 country code (e.g., "GB", "US")

        Returns:
            Current weather dictionary

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If city not found
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        # Geocode city to coordinates
        geo_url = "http://api.openweathermap.org/geo/1.0/direct"
        query = f"{city},{country_code}" if country_code else city
        params: dict[str, str | int] = {
            "q": query,
            "limit": 1,
            "appid": self.api_key,
        }

        response = await self._client.get(geo_url, params=params)
        response.raise_for_status()
        geo_data = response.json()

        if not geo_data:
            raise ValueError(f"City not found: {city}")

        location = geo_data[0]
        lat = location["lat"]
        lon = location["lon"]

        # Fetch weather for coordinates
        return await self.get_current_weather_by_coords(lat=lat, lon=lon)
