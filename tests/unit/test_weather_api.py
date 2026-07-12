"""Unit tests for OpenWeatherMap API client.

Following TDD methodology:
1. RED: Write failing tests
2. GREEN: Implement minimal code to pass
3. REFACTOR: Improve implementation
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from sipap_intelligence_mcp.apis.weather import OpenWeatherMapClient
from sipap_intelligence_mcp.exceptions import WeatherAPIException


@pytest.fixture
def weather_client():
    """Create OpenWeatherMap client for testing."""
    return OpenWeatherMapClient(api_key="test_api_key_12345")


@pytest.fixture
def mock_weather_response():
    """Mock weather API response."""
    return {
        "coord": {"lon": -0.1257, "lat": 51.5085},
        "weather": [
            {
                "id": 500,
                "main": "Rain",
                "description": "light rain",
                "icon": "10d"
            }
        ],
        "main": {
            "temp": 15.2,
            "feels_like": 14.8,
            "pressure": 1013,
            "humidity": 82
        },
        "wind": {
            "speed": 12.5,
            "deg": 250
        },
        "visibility": 8000,
        "clouds": {"all": 90},
        "dt": 1699876543,
        "timezone": 0,
        "name": "London"
    }


class TestOpenWeatherMapClient:
    """Test OpenWeatherMap API client."""

    def test_client_initialization(self, weather_client):
        """Test client initializes with API key."""
        assert weather_client.api_key == "test_api_key_12345"
        assert weather_client.base_url == "https://api.openweathermap.org/data/2.5"

    def test_client_initialization_without_api_key(self):
        """Test client raises error without API key."""
        with pytest.raises(ValueError, match="API key is required"):
            OpenWeatherMapClient(api_key="")

    @pytest.mark.asyncio
    async def test_get_weather_by_coordinates_success(
        self, weather_client, mock_weather_response
    ):
        """Test fetching weather by coordinates succeeds."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_weather_response
            mock_get.return_value = mock_response

            result = await weather_client.get_weather_by_coordinates(
                lat=51.5085, lon=-0.1257
            )

            assert result["temperature"] == 15.2
            assert result["precipitation"] == "light_rain"
            assert result["wind_speed"] == 12.5
            assert result["visibility"] == 8000
            assert result["humidity"] == 82
            assert result["weather_main"] == "Rain"

    @pytest.mark.asyncio
    async def test_get_weather_by_coordinates_invalid_coords(self, weather_client):
        """Test invalid coordinates raise ValueError."""
        with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
            await weather_client.get_weather_by_coordinates(lat=95.0, lon=0.0)

        with pytest.raises(ValueError, match="Longitude must be between -180 and 180"):
            await weather_client.get_weather_by_coordinates(lat=0.0, lon=185.0)

    @pytest.mark.asyncio
    async def test_get_weather_by_city_success(self, weather_client, mock_weather_response):
        """Test fetching weather by city name succeeds."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_weather_response
            mock_get.return_value = mock_response

            result = await weather_client.get_weather_by_city(
                city="London", country_code="GB"
            )

            assert result["temperature"] == 15.2
            assert result["city"] == "London"

    @pytest.mark.asyncio
    async def test_get_weather_api_error_404(self, weather_client):
        """Test API returns 404 for city not found."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.text = "City not found"
            mock_get.return_value = mock_response

            with pytest.raises(WeatherAPIException, match="City not found"):
                await weather_client.get_weather_by_city(city="InvalidCity")

    @pytest.mark.asyncio
    async def test_get_weather_api_error_401(self, weather_client):
        """Test API returns 401 for invalid API key."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Invalid API key"
            mock_get.return_value = mock_response

            with pytest.raises(WeatherAPIException, match="Invalid API key"):
                await weather_client.get_weather_by_coordinates(lat=51.5, lon=-0.1)

    @pytest.mark.asyncio
    async def test_get_weather_network_timeout(self, weather_client):
        """Test network timeout raises WeatherAPIException."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = TimeoutError("Request timeout")

            with pytest.raises(WeatherAPIException, match="Request timeout"):
                await weather_client.get_weather_by_coordinates(lat=51.5, lon=-0.1)

    @pytest.mark.asyncio
    async def test_get_forecast_by_coordinates_success(
        self, weather_client
    ):
        """Test fetching 5-day forecast succeeds."""
        mock_forecast = {
            "cod": "200",
            "list": [
                {
                    "dt": 1699876543,
                    "main": {"temp": 15.2, "humidity": 82},
                    "weather": [{"main": "Rain", "description": "light rain"}],
                    "wind": {"speed": 12.5},
                    "visibility": 8000,
                    "dt_txt": "2024-07-12 12:00:00"
                },
                {
                    "dt": 1699887543,
                    "main": {"temp": 16.5, "humidity": 75},
                    "weather": [{"main": "Clouds", "description": "overcast clouds"}],
                    "wind": {"speed": 10.2},
                    "visibility": 10000,
                    "dt_txt": "2024-07-12 15:00:00"
                }
            ]
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_forecast
            mock_get.return_value = mock_response

            result = await weather_client.get_forecast_by_coordinates(
                lat=51.5085, lon=-0.1257, hours=24
            )

            assert len(result) == 2
            assert result[0]["temperature"] == 15.2
            assert result[0]["precipitation"] == "light_rain"
            assert result[1]["temperature"] == 16.5

    @pytest.mark.asyncio
    async def test_parse_weather_data_correctly(self, weather_client, mock_weather_response):
        """Test _parse_weather_data extracts correct fields."""
        parsed = weather_client._parse_weather_data(mock_weather_response)

        assert parsed["temperature"] == 15.2
        assert parsed["feels_like"] == 14.8
        assert parsed["pressure"] == 1013
        assert parsed["humidity"] == 82
        assert parsed["wind_speed"] == 12.5
        assert parsed["wind_direction"] == 250
        assert parsed["visibility"] == 8000
        assert parsed["cloud_coverage"] == 90
        assert parsed["weather_main"] == "Rain"
        assert parsed["weather_description"] == "light rain"
        assert parsed["precipitation"] == "light_rain"
        assert parsed["city"] == "London"

    def test_classify_precipitation_correctly(self, weather_client):
        """Test _classify_precipitation maps weather description correctly."""
        assert weather_client._classify_precipitation("light rain") == "light_rain"
        assert weather_client._classify_precipitation("heavy rain") == "heavy_rain"
        assert weather_client._classify_precipitation("moderate rain") == "moderate_rain"
        assert weather_client._classify_precipitation("light snow") == "light_snow"
        assert weather_client._classify_precipitation("overcast clouds") == "overcast_clouds"
        assert weather_client._classify_precipitation("") == "none"
