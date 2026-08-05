import httpx
from civicproof.services.weather import NWSWeatherClient
from civicproof.domain.incidents import WeatherEvidence, WeatherStatus
import time

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
        cache_ttl_seconds=300.0,
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
        cache_ttl_seconds=300.0,
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
        cache_ttl_seconds=300.0,
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
        cache_ttl_seconds=300.0,
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
        cache_ttl_seconds=300.0,
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
        cache_ttl_seconds=300.0,
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
        cache_ttl_seconds=300.0,
        transport=transport,
    )
    evidence = client.get_active_alerts(latitude=40.7128, longitude=-74.006)
    client.close()
    assert evidence.status is WeatherStatus.UNAVAILABLE
    assert evidence.alerts == []
    assert evidence.error_type == "request_error"

def test_repeated_coordinates_use_cache():
    request_count = {"value": 0}
    def handler(request):
        request_count["value"] += 1
        return httpx.Response(200, json={"features": []})
    client = NWSWeatherClient(
        base_url="https://api.weather.gov",
        user_agent="CivicProof-Test",
        timeout_seconds=5.0,
        cache_ttl_seconds=300.0,
        transport=httpx.MockTransport(handler),
    )
    first_evidence = client.get_active_alerts(40.7128, -74.0060)
    second_evidence = client.get_active_alerts(40.7128, -74.0060)
    client.close()
    assert request_count["value"] == 1
    assert first_evidence.cache_hit is False
    assert second_evidence.cache_hit is True
    assert isinstance(second_evidence, WeatherEvidence)

def test_nearby_coordinates_use_same_cache_entry():
    request_count = {"value": 0}
    def handler(request):
        request_count["value"] += 1
        return httpx.Response(200, json={"features": []})
    client = NWSWeatherClient(
        base_url="https://api.weather.gov",
        user_agent="CivicProof-Test",
        timeout_seconds=5.0,
        cache_ttl_seconds=300.0,
        transport=httpx.MockTransport(handler),
    )
    client.get_active_alerts(40.71281, -74.00601)
    second_evidence = client.get_active_alerts(40.71282, -74.00602)
    client.close()
    assert request_count["value"] == 1
    assert second_evidence.cache_hit is True

def test_different_coordinates_use_different_cache_entries():
    request_count = {"value": 0}
    def handler(request):
        request_count["value"] += 1
        return httpx.Response(200, json={"features": []})
    client = NWSWeatherClient(
        base_url="https://api.weather.gov",
        user_agent="CivicProof-Test",
        timeout_seconds=5.0,
        cache_ttl_seconds=300.0,
        transport=httpx.MockTransport(handler),
    )
    client.get_active_alerts(40.7128, -74.0060)
    client.get_active_alerts(40.7148, -74.0080)
    client.close()
    assert request_count["value"] == 2

def test_expired_cache_entry_fetches_again():
    request_count = {"value": 0}
    def handler(request):
        request_count["value"] += 1
        return httpx.Response(200, json={"features": []})
    client = NWSWeatherClient(
        base_url="https://api.weather.gov",
        user_agent="CivicProof-Test",
        timeout_seconds=5.0,
        cache_ttl_seconds=300.0,
        transport=httpx.MockTransport(handler),
    )
    client.get_active_alerts(40.7128, -74.0060)
    rounded_point = str(round(40.7128, 3)) + ',' + str(round(-74.0060, 3))
    client.cache[rounded_point]['fetched_time'] = time.monotonic() - client.cache_ttl_seconds - 1
    second_evidence = client.get_active_alerts(40.7128, -74.0060)
    client.close()
    assert request_count["value"] == 2
    assert second_evidence.cache_hit is False

def test_unavailable_response_is_not_cached():
    request_count = {"value": 0}
    def handler(request):
        request_count["value"] += 1
        raise httpx.ReadTimeout("NWS timed out", request=request)
    client = NWSWeatherClient(
        base_url="https://api.weather.gov",
        user_agent="CivicProof-Test",
        timeout_seconds=5.0,
        cache_ttl_seconds=300.0,
        transport=httpx.MockTransport(handler),
    )
    first_evidence = client.get_active_alerts(40.7128, -74.0060)
    second_evidence = client.get_active_alerts(40.7128, -74.0060)
    client.close()
    assert request_count["value"] == 2
    assert first_evidence.status is WeatherStatus.UNAVAILABLE
    assert second_evidence.status is WeatherStatus.UNAVAILABLE
    assert first_evidence.cache_hit is False
    assert second_evidence.cache_hit is False
