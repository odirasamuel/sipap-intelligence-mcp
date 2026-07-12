"""OpenWeatherMap API client for weather data.

Provides current weather and forecasts for match locations using OpenWeatherMap API.
Free tier: 60 calls/min, 1,000,000 calls/month.
"""

import httpx
from typing import Any
from sipap_intelligence_mcp.exceptions import WeatherAPIException


class OpenWeatherMapClient:
    """Client for OpenWeatherMap API.

    Fetches current weather and forecasts for match venues.

    Attributes:
        api_key: OpenWeatherMap API key
        base_url: API base URL
        timeout: Request timeout in seconds

    Example:
        >>> client = OpenWeatherMapClient(api_key="your_key")
        >>> weather = await client.get_weather_by_coordinates(lat=51.5, lon=-0.1)
        >>> weather['temperature']
        15.2
    """

    def __init__(self, api_key: str, timeout: int = 10):
        """Initialize OpenWeatherMap client.

        Args:
            api_key: OpenWeatherMap API key (required)
            timeout: HTTP request timeout in seconds (default: 10)

        Raises:
            ValueError: If API key is empty
        """
        if not api_key:
            raise ValueError("API key is required")

        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.timeout = timeout

    async def get_weather_by_coordinates(
        self, lat: float, lon: float, units: str = "metric"
    ) -> dict[str, Any]:
        """Get current weather for coordinates.

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)
            units: Units system (metric, imperial, standard)

        Returns:
            Parsed weather data with:
                - temperature: Temperature in Celsius (metric)
                - feels_like: Feels like temperature
                - pressure: Atmospheric pressure (hPa)
                - humidity: Humidity percentage
                - wind_speed: Wind speed (m/s for metric)
                - wind_direction: Wind direction (degrees)
                - visibility: Visibility (meters)
                - cloud_coverage: Cloud coverage percentage
                - weather_main: Main weather condition
                - weather_description: Detailed description
                - precipitation: Precipitation type (rain, snow, drizzle, none)
                - city: City name

        Raises:
            ValueError: If coordinates are invalid
            WeatherAPIException: If API request fails
        """
        # Validate coordinates
        if not (-90 <= lat <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        if not (-180 <= lon <= 180):
            raise ValueError("Longitude must be between -180 and 180")

        url = f"{self.base_url}/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": units
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    return self._parse_weather_data(data)
                elif response.status_code == 401:
                    raise WeatherAPIException(f"Invalid API key: {response.text}")
                elif response.status_code == 404:
                    raise WeatherAPIException(f"Location not found: {response.text}")
                else:
                    raise WeatherAPIException(
                        f"Weather API error {response.status_code}: {response.text}"
                    )

        except TimeoutError as e:
            raise WeatherAPIException(f"Request timeout: {str(e)}")
        except httpx.RequestError as e:
            raise WeatherAPIException(f"Network error: {str(e)}")

    async def get_weather_by_city(
        self, city: str, country_code: str | None = None, units: str = "metric"
    ) -> dict[str, Any]:
        """Get current weather for a city.

        Args:
            city: City name
            country_code: ISO 3166 country code (e.g., "GB", "US")
            units: Units system (metric, imperial, standard)

        Returns:
            Parsed weather data (same format as get_weather_by_coordinates)

        Raises:
            WeatherAPIException: If API request fails
        """
        url = f"{self.base_url}/weather"
        query = f"{city},{country_code}" if country_code else city
        params = {
            "q": query,
            "appid": self.api_key,
            "units": units
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    return self._parse_weather_data(data)
                elif response.status_code == 404:
                    raise WeatherAPIException(f"City not found: {response.text}")
                elif response.status_code == 401:
                    raise WeatherAPIException(f"Invalid API key: {response.text}")
                else:
                    raise WeatherAPIException(
                        f"Weather API error {response.status_code}: {response.text}"
                    )

        except TimeoutError as e:
            raise WeatherAPIException(f"Request timeout: {str(e)}")
        except httpx.RequestError as e:
            raise WeatherAPIException(f"Network error: {str(e)}")

    async def get_forecast_by_coordinates(
        self, lat: float, lon: float, hours: int = 24, units: str = "metric"
    ) -> list[dict[str, Any]]:
        """Get weather forecast for coordinates.

        OpenWeatherMap provides 5-day forecast with 3-hour intervals (40 data points).

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)
            hours: Hours ahead to forecast (max 120 for 5 days)
            units: Units system (metric, imperial, standard)

        Returns:
            List of forecast data points (parsed weather format)

        Raises:
            ValueError: If coordinates are invalid
            WeatherAPIException: If API request fails
        """
        # Validate coordinates
        if not (-90 <= lat <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        if not (-180 <= lon <= 180):
            raise ValueError("Longitude must be between -180 and 180")

        url = f"{self.base_url}/forecast"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": units
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    # Parse forecast list (3-hour intervals)
                    forecasts = []
                    count = min(hours // 3, len(data.get('list', [])))
                    for item in data['list'][:count]:
                        parsed = self._parse_weather_data(item)
                        parsed['timestamp'] = item['dt']
                        parsed['datetime_text'] = item.get('dt_txt', '')
                        forecasts.append(parsed)
                    return forecasts
                elif response.status_code == 401:
                    raise WeatherAPIException(f"Invalid API key: {response.text}")
                elif response.status_code == 404:
                    raise WeatherAPIException(f"Location not found: {response.text}")
                else:
                    raise WeatherAPIException(
                        f"Weather API error {response.status_code}: {response.text}"
                    )

        except TimeoutError as e:
            raise WeatherAPIException(f"Request timeout: {str(e)}")
        except httpx.RequestError as e:
            raise WeatherAPIException(f"Network error: {str(e)}")

    def _parse_weather_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse OpenWeatherMap response into standardized format.

        Args:
            data: Raw API response data

        Returns:
            Parsed weather data with standardized fields
        """
        main = data.get('main', {})
        wind = data.get('wind', {})
        weather = data.get('weather', [{}])[0]
        clouds = data.get('clouds', {})

        return {
            'temperature': main.get('temp', 0.0),
            'feels_like': main.get('feels_like', 0.0),
            'pressure': main.get('pressure', 0),
            'humidity': main.get('humidity', 0),
            'wind_speed': wind.get('speed', 0.0),
            'wind_direction': wind.get('deg', 0),
            'visibility': data.get('visibility', 0),
            'cloud_coverage': clouds.get('all', 0),
            'weather_main': weather.get('main', ''),
            'weather_description': weather.get('description', ''),
            'precipitation': self._classify_precipitation(weather.get('main', '')),
            'city': data.get('name', 'Unknown')
        }

    def _classify_precipitation(self, weather_main: str) -> str:
        """Classify precipitation type from weather main category.

        Args:
            weather_main: Main weather category (e.g., "Rain", "Snow", "Clear")

        Returns:
            Precipitation type: rain, drizzle, snow, heavy_rain, or none
        """
        if weather_main == 'Rain':
            return 'rain'
        elif weather_main == 'Drizzle':
            return 'drizzle'
        elif weather_main == 'Snow':
            return 'snow'
        elif weather_main == 'Thunderstorm':
            return 'heavy_rain'
        else:
            return 'none'
