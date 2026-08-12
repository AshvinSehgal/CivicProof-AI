from datetime import datetime
from zoneinfo import ZoneInfo
from civicproof.repositories.incidents import IncidentRepository
from civicproof.repositories.ingestion_failures import IngestionFailureRepository
from civicproof.services.embedding_classifier import EmbeddingClassifier

class IncidentIngestionService:
    def __init__(self, repository: IncidentRepository, classifier: EmbeddingClassifier, ingestion_failure_repository: IngestionFailureRepository):
        self.repository = repository
        self.classifier = classifier
        self.ingestion_failure_repository = ingestion_failure_repository
    
    def required_text(self, record: dict, field_name: str) -> str:
        value = record.get(field_name)
        if not isinstance(value, str) or value.strip() == "":
            raise ValueError(field_name + " must be a non-empty string")
        return value.strip()
    
    def parse_created_at(self, created_date: str) -> datetime:
        if not isinstance(created_date, str) or created_date.strip() == "":
            raise ValueError("created_date must be a non-empty string")
        parsed_created_at = datetime.fromisoformat(
            created_date.replace("Z", "+00:00")
        )
        if parsed_created_at.tzinfo is None:
            parsed_created_at = parsed_created_at.replace(
                tzinfo=ZoneInfo("America/New_York")
            )
        return parsed_created_at
    
    def parse_coordinates(self, record: dict) -> tuple[float, float]:
        try:
            latitude = float(record["latitude"])
            longitude = float(record["longitude"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("latitude and longitude must be valid numbers")
        if not -90 <= latitude <= 90:
            raise ValueError("latitude is outside the valid range")
        if not -180 <= longitude <= 180:
            raise ValueError("longitude is outside the valid range")
        return latitude, longitude
    
    def normalize_record(self, raw_record: dict) -> dict:
        if not isinstance(raw_record, dict):
            raise TypeError("incident must be a dictionary")
        external_id_value = raw_record.get("unique_key")
        if external_id_value is None or str(external_id_value).strip() == "":
            raise ValueError("unique_key is required")
        external_id = str(external_id_value).strip()
        complaint_type = self.required_text(raw_record, "complaint_type")
        descriptor = self.required_text(raw_record, "descriptor")
        source_created_at = self.parse_created_at(raw_record.get("created_date"))
        latitude, longitude = self.parse_coordinates(raw_record)
        description = raw_record.get("description")
        if not isinstance(description, str) or description.strip() == "":
            description = descriptor
        else:
            description = description.strip()
        prediction = self.classifier.predict(complaint_type, descriptor)
        category = prediction["category"]
        return {
            "source": "open311",
            "external_id": external_id,
            "complaint_type": complaint_type,
            "descriptor": descriptor,
            "description": description,
            "latitude": latitude,
            "longitude": longitude,
            "category": category,
            "source_created_at": source_created_at,
            "raw_payload": dict(raw_record)
        }
    
    async def ingest_record(self, raw_record: dict) -> dict:
        try:
            incident_data = self.normalize_record(raw_record)
        except (TypeError, ValueError) as error:
            external_id = None
            if isinstance(raw_record, dict):
                external_id = raw_record.get("unique_key")
            await self.ingestion_failure_repository.create_ingestion_failure(
                {
                    "source": "open311",
                    "external_id": external_id,
                    "stage": "normalization",
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "raw_payload": raw_record if isinstance(raw_record, dict) else None
                }
            )
            return {
                "status": "failed",
                "external_id": external_id,
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
        incident = await self.repository.upsert_incident(incident_data)
        return {
            "status": "upserted",
            "external_id": incident.external_id,
            "incident_id": incident.id
        }
