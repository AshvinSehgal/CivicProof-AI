import httpx
from civicproof.services.weather import NWSWeatherClient
from civicproof.domain.incidents import WeatherStatus

def test_active_alert_is_normalized() -> None:
    def handler(request):
        assert request.url.params["point"] == "40.7128,-74.006"
        assert request.headers["user-agent"] == "CivicProof-Test"
        assert request.headers["accept"] == "application/geo+json"
        return httpx.Response(200,
            json={
                "features": [
                    {
                        "id": "alert-001",
                        "properties": {
                            "event": "Flood Warning",
                            "severity": "Severe",
                            "urgency": "Immediate",
                            "certainty": "Likely",
                            "headline": "Flood Warning issued",
                            "effective": "2026-08-04T12:00:00Z",
                            "expires": "2026-08-04T18:00:00Z",
                        },
                    }
                ]
            },
        )
    transport = httpx.MockTransport(handler)
    client = NWSWeatherClient(
        base_url="https://api.weather.gov",
        user_agent="CivicProof-Test",
        timeout_seconds=5.0,
        transport=transport,
    )
    evidence = client.get_active_alerts(latitude=40.7128, longitude=-74.006)
    client.close()
    assert evidence.status is WeatherStatus.AVAILABLE
    assert len(evidence.alerts) == 1
    assert evidence.alerts[0].event == "Flood Warning"
    assert evidence.alerts[0].severity == "Severe"
    assert evidence.error_type is None

def test_no_alerts_returns_available() -> None:
    def handler(request):
            assert request.url.params["point"] == "40.7128,-74.006"
            return httpx.Response(200, json={"features": []})
    transport = httpx.MockTransport(handler)
    client = NWSWeatherClient(
        base_url="https://api.weather.gov",
        user_agent="CivicProof-Test",
        timeout_seconds=5.0,
        transport=transport,
    )
    evidence = client.get_active_alerts(latitude=40.7128, longitude=-74.006)
    client.close()
    assert evidence.status is WeatherStatus.AVAILABLE
    assert evidence.alerts == []

def test_http_error_returns_unavailable() -> None:
    def handler(request):
            assert request.url.params["point"] == "40.7128,-74.006"
            return httpx.Response(500, json={"detail": "Internal server error"})
    transport = httpx.MockTransport(handler)
    client = NWSWeatherClient(
        base_url="https://api.weather.gov",
        user_agent="CivicProof-Test",
        timeout_seconds=5.0,
        transport=transport,
    )
    evidence = client.get_active_alerts(latitude=40.7128, longitude=-74.006)
    client.close()
    assert evidence.status is WeatherStatus.UNAVAILABLE
    assert evidence.alerts == []
    assert evidence.error_type == "http_error"

def test_malformed_response_returns_unavailable() -> None:
    def handler(request):
            assert request.url.params["point"] == "40.7128,-74.006"
            return httpx.Response(200, json={"unexpected": "value"})
    transport = httpx.MockTransport(handler)
    client = NWSWeatherClient(
        base_url="https://api.weather.gov",
        user_agent="CivicProof-Test",
        timeout_seconds=5.0,
        transport=transport,
    )
    evidence = client.get_active_alerts(latitude=40.7128, longitude=-74.006)
    client.close()
    assert evidence.status is WeatherStatus.UNAVAILABLE
    assert evidence.error_type == "malformed_response"

def test_timeout_returns_unavailable() -> None:
    def handler(request):
            raise httpx.ReadTimeout("NWS timed out", request=request)
    transport = httpx.MockTransport(handler)
    client = NWSWeatherClient(
        base_url="https://api.weather.gov",
        user_agent="CivicProof-Test",
        timeout_seconds=5.0,
        transport=transport,
    )
    evidence = client.get_active_alerts(latitude=40.7128, longitude=-74.006)
    client.close()
    assert evidence.status is WeatherStatus.UNAVAILABLE
    assert evidence.error_type == "timeout"

def test_invalid_json_returns_unavailable() -> None:
    def handler(request):
            assert request.url.params["point"] == "40.7128,-74.006"
            return httpx.Response(200, text="not-json")
    transport = httpx.MockTransport(handler)
    client = NWSWeatherClient(
        base_url="https://api.weather.gov",
        user_agent="CivicProof-Test",
        timeout_seconds=5.0,
        transport=transport,
    )
    evidence = client.get_active_alerts(latitude=40.7128, longitude=-74.006)
    client.close()
    assert evidence.status is WeatherStatus.UNAVAILABLE
    assert evidence.error_type == "invalid_json"

def test_request_error_returns_unavailable() -> None:
    def handler(request):
        raise httpx.ConnectError("Unable to connect to NWS", request=request)
    transport = httpx.MockTransport(handler)
    client = NWSWeatherClient(
        base_url="https://api.weather.gov",
        user_agent="CivicProof-Test",
        timeout_seconds=5.0,
        transport=transport,
    )
    evidence = client.get_active_alerts(latitude=40.7128, longitude=-74.006)
    client.close()
    assert evidence.status is WeatherStatus.UNAVAILABLE
    assert evidence.alerts == []
    assert evidence.error_type == "request_error"