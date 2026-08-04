import httpx
from civicproof.domain.incidents import WeatherAlert, WeatherEvidence, WeatherStatus

class NWSWeatherClient:
    def __init__(self, base_url, user_agent, timeout_seconds, transport=None):
        self.client = httpx.Client(base_url=base_url,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/geo+json",
            },
            timeout=timeout_seconds,transport=transport
        )
    def close(self):
        self.client.close()
        
    def get_active_alerts(self, latitude, longitude):
        point = str(latitude) + "," + str(longitude)
        try:
            response = self.client.get("/alerts/active", params={"point": point})
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            return WeatherEvidence(status=WeatherStatus.UNAVAILABLE, error_type="timeout")
        except httpx.HTTPStatusError:
            return WeatherEvidence(status=WeatherStatus.UNAVAILABLE, error_type="http_error")
        except ValueError:
            return WeatherEvidence(status=WeatherStatus.UNAVAILABLE, error_type="invalid_json")
        except httpx.RequestError:
            return WeatherEvidence(status=WeatherStatus.UNAVAILABLE, error_type="request_error")
        if not isinstance(data, dict):
            return WeatherEvidence(status=WeatherStatus.UNAVAILABLE, error_type="malformed_response")
        features = data.get("features")
        if not isinstance(features, list):
            return WeatherEvidence(status=WeatherStatus.UNAVAILABLE, error_type="malformed_response")
        alerts = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties", {})
            if not isinstance(properties, dict):
                continue
            alert_id = properties.get("id") or feature.get("id")
            if alert_id is None:
                continue
            alerts.append(
                WeatherAlert(
                    alert_id=alert_id,
                    event=properties.get("event"),
                    severity=properties.get("severity"),
                    urgency=properties.get("urgency"),
                    certainty=properties.get("certainty"),
                    headline=properties.get("headline"),
                    effective=properties.get("effective"),
                    expires=properties.get("expires"),
                )
            )
        return WeatherEvidence(status=WeatherStatus.AVAILABLE, alerts=alerts)