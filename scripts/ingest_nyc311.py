import json
import time
from datetime import datetime
import asyncio
from pathlib import Path
from civicproof.db.session import async_session, close_database
from civicproof.repositories.incidents import IncidentRepository
from civicproof.services.embedding_classifier import EmbeddingClassifier
from civicproof.services.incident_ingestion import IncidentIngestionService
from civicproof.repositories.ingestion_failures import IngestionFailureRepository

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / 'nyc311_sample.json'

async def ingest_nyc311(records = None):
    print("Source: NYC311 Public API")
    classifier = EmbeddingClassifier()
    classifier.load_model()
    try:
        async with async_session() as session:
            repository = IncidentRepository(session)
            ingestion_failure_repository = IngestionFailureRepository(session)
            service = IncidentIngestionService(repository, classifier, ingestion_failure_repository)
            if records is None:
                with open(DATA_PATH, 'r') as f:
                    records = json.load(f)
            if not isinstance(records, list):
                raise TypeError("NYC 311 input must be a JSON array")
            batch_size = 100
            record_count = 0
            success_count = 0
            failed_count = 0
            upserted_count = 0
            total_records = len(records)
            start_time = time.perf_counter()
            print(f"[{datetime.now().strftime("%d-%m-%Y %H:%M:%S")}] Starting ingestion")
            try:
                for record in records:
                    record_count += 1
                    ingest_status = await service.ingest_record(record)
                    if ingest_status['status'] == 'failed':
                        failed_count += 1
                        continue
                    success_count += 1
                    upserted_count += 1
                    if record_count % batch_size == 0:
                        await session.commit()
                        print(f"Processing records...({record_count}/{total_records})")
                await session.commit()
                ingestion_time = time.perf_counter() - start_time
                print(f"[{datetime.now().strftime("%d-%m-%Y %H:%M:%S")}] {record_count} records processed in {ingestion_time}s :")
                print("Success:", success_count)
                print("Upserted:", upserted_count)
                print("Failed:", failed_count)
            except Exception:
                await session.rollback()
                raise
    finally:
        await close_database()

if __name__ == '__main__':
    asyncio.run(ingest_nyc311())
        
