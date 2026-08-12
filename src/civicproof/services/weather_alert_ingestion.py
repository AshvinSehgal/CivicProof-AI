from datetime import datetime
from civicproof.repositories.weather_alerts import WeatherAlertRepository
from civicproof.repositories.ingestion_failures import IngestionFailureRepository

class WeatherAlertIngestionService:
    def __init__(self, repository: WeatherAlertRepository, ingestion_failure_repository: IngestionFailureRepository):
        self.repository = repository
        self.ingestion_failure_repository = ingestion_failure_repository
        
    def required_text(self, record: dict, field_name: str) -> str:
        value = record.get(field_name)
        if not isinstance(value, str) or value.strip() == "":
            raise ValueError(field_name + " must be a non-empty string")
        return value.strip()
    
    def optional_text(self, record: dict, field_name: str) -> str | None:
        value = record.get(field_name)
        if not isinstance(value, str) or value.strip() == "":
            return None
        return value.strip()
    
    def parse_datetime(self, datetime_value, field_name: str) -> datetime | None:
        if datetime_value is None or datetime_value == "":
            return None
        if not isinstance(datetime_value, str):
            raise ValueError(field_name + " must be a valid ISO-8601 datetime")
        try:
            parsed_datetime = datetime.fromisoformat(datetime_value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(field_name + " must be a valid ISO-8601 datetime")
        if parsed_datetime.tzinfo is None:
            raise ValueError(field_name + " must include a timezone")
        return parsed_datetime
    
    def normalize_record(self, raw_record: dict) -> dict:
        if not isinstance(raw_record, dict):
            raise TypeError("weather alert must be a dictionary")
        properties = raw_record.get("properties")
        if not isinstance(properties, dict):
            raise ValueError("weather alert properties must be a dictionary")
        alert_id_value = properties.get("id") or raw_record.get("id")
        if not isinstance(alert_id_value, str) or alert_id_value.strip() == "":
            raise ValueError("alert id is required")
        alert_id = alert_id_value.strip()
        event = self.required_text(properties, "event")
        geometry = raw_record.get("geometry")
        if geometry is not None and not isinstance(geometry, dict):
            raise ValueError("geometry must be a dictionary or null")
        return {
            "alert_id": alert_id,
            "event": event,
            "severity": self.optional_text(properties, "severity"),
            "urgency": self.optional_text(properties, "urgency"),
            "certainty": self.optional_text(properties, "certainty"),
            "headline": self.optional_text(properties, "headline"),
            "description": self.optional_text(properties, "description"),
            "instruction": self.optional_text(properties, "instruction"),
            "area_description": self.optional_text(properties, "areaDesc"),
            "status": self.optional_text(properties, "status"),
            "message_type": self.optional_text(properties, "messageType"),
            "category": self.optional_text(properties, "category"),
            "response": self.optional_text(properties, "response"),
            "effective_at": self.parse_datetime(properties.get("effective"), "effective"),
            "onset_at": self.parse_datetime(properties.get("onset"), "onset"),
            "expires_at": self.parse_datetime(properties.get("expires"), "expires"),
            "ends_at": self.parse_datetime(properties.get("ends"), "ends"),
            "sent_at": self.parse_datetime(properties.get("sent"), "sent"),
            "geometry": geometry,
            "raw_payload": dict(raw_record)
        }
        
    async def ingest_record(self, raw_record: dict) -> dict:
        try:
            weather_alert_data = self.normalize_record(raw_record)
        except (TypeError, ValueError) as error:
            alert_id = None
            if isinstance(raw_record, dict):
                properties = raw_record.get("properties", {})
                if isinstance(properties, dict):
                    alert_id = properties.get("id") or raw_record.get("id")
            await self.ingestion_failure_repository.create_ingestion_failure(
                {
                    "source": "nws",
                    "external_id": alert_id,
                    "stage": "normalization",
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "raw_payload": raw_record if isinstance(raw_record, dict) else None
                }
            )
            return {
                "status": "failed",
                "alert_id": alert_id,
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
        weather_alert = await self.repository.upsert_weather_alert(weather_alert_data)
        return {
            "status": "upserted",
            "alert_id": weather_alert.alert_id,
            "weather_alert_id": weather_alert.id
        }
