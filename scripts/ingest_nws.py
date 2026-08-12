import json
import time
from datetime import datetime
import asyncio
from pathlib import Path
from civicproof.db.session import async_session, close_database
from civicproof.repositories.weather_alerts import WeatherAlertRepository
from civicproof.services.weather_alert_ingestion import WeatherAlertIngestionService
from civicproof.repositories.ingestion_failures import IngestionFailureRepository

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / 'nws_alerts.json'

async def ingest_nws(records = None):
    print("Source: NWS Weather API")
    try:
        if records is None:
            with open(DATA_PATH, 'r') as f:
                records = json.load(f)
        if isinstance(records, dict):
            records = records.get('features')
        if not isinstance(records, list):
            raise TypeError("NWS input must be a GeoJSON FeatureCollection or an array")
        batch_size = 100
        record_count = 0
        success_count = 0
        failed_count = 0
        upserted_count = 0
        total_records = len(records)
        start_time = time.perf_counter()
        print(f"[{datetime.now().strftime("%d-%m-%Y %H:%M:%S")}] Starting ingestion")
        async with async_session() as session:
            repository = WeatherAlertRepository(session)
            ingestion_failure_repository = IngestionFailureRepository(session)
            service = WeatherAlertIngestionService(repository, ingestion_failure_repository)
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
            except Exception:
                await session.rollback()
                raise
        ingestion_time = time.perf_counter() - start_time
        
        print(f"[{datetime.now().strftime("%d-%m-%Y %H:%M:%S")}] {record_count} weather alerts processed in {ingestion_time}s :")
        print("Success:", success_count)
        print("Upserted:", upserted_count)
        print("Failed:", failed_count)
    finally:
        await close_database()

if __name__ == '__main__':
    asyncio.run(ingest_nws())
