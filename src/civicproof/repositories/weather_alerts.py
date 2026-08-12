from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from civicproof.db.models.weather_alert import WeatherAlert

class WeatherAlertRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def upsert_weather_alert(self, weather_alert_data: dict) -> WeatherAlert:
        insert_statement = insert(WeatherAlert).values(**weather_alert_data)
        upsert_statement = insert_statement.on_conflict_do_update(
            constraint='uq_weather_alerts_alert_id',
            set_ = {
                'event': insert_statement.excluded.event,
                'severity': insert_statement.excluded.severity,
                'urgency': insert_statement.excluded.urgency,
                'certainty': insert_statement.excluded.certainty,
                'headline': insert_statement.excluded.headline,
                'description': insert_statement.excluded.description,
                'instruction': insert_statement.excluded.instruction,
                'area_description': insert_statement.excluded.area_description,
                'status': insert_statement.excluded.status,
                'message_type': insert_statement.excluded.message_type,
                'category': insert_statement.excluded.category,
                'response': insert_statement.excluded.response,
                'effective_at': insert_statement.excluded.effective_at,
                'onset_at': insert_statement.excluded.onset_at,
                'expires_at': insert_statement.excluded.expires_at,
                'ends_at': insert_statement.excluded.ends_at,
                'sent_at': insert_statement.excluded.sent_at,
                'geometry': insert_statement.excluded.geometry,
                'raw_payload': insert_statement.excluded.raw_payload,
                'last_seen_at': func.now(),
                'updated_at': func.now()
            }
        ).returning(WeatherAlert)
        result = await self.session.execute(
            upsert_statement,
            execution_options={'populate_existing': True}
        )
        weather_alert = result.scalar_one()
        return weather_alert
    
    async def get_weather_alert(self, alert_id: str) -> WeatherAlert | None:
        select_weather_alert_statement = select(WeatherAlert).where(
            WeatherAlert.alert_id == alert_id
        )
        result = await self.session.execute(select_weather_alert_statement)
        weather_alert = result.scalar_one_or_none()
        return weather_alert
        