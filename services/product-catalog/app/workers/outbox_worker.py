import asyncio
import json
from datetime import UTC, datetime

from aiokafka import AIOKafkaProducer
from sqlalchemy import asc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.plan import ProductCatalogOutbox

logger = get_logger(__name__)


class OutboxWorker:
    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None
        self._running = False

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)
        await self._producer.start()
        self._running = True
        asyncio.create_task(self._poll())
        logger.info("outbox_worker_started")

    async def stop(self) -> None:
        self._running = False
        if self._producer:
            await self._producer.stop()
        logger.info("outbox_worker_stopped")

    async def _poll(self) -> None:
        while self._running:
            async with SessionLocal() as session:
                await self._process_batch(session, settings.BATCH_ROWS)
            await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL_SECONDS)

    async def _process_batch(self, session: AsyncSession, limit: int) -> None:
        result = await session.execute(
            select(ProductCatalogOutbox)
            .where(
                ProductCatalogOutbox.published == False,  # noqa: E712
                ProductCatalogOutbox.publish_attempts < settings.OUTBOX_DEAD_LETTER_THRESHOLD,
            )
            .order_by(asc(ProductCatalogOutbox.created_at))
            .limit(limit)
        )
        rows = list(result.scalars().all())

        for row in rows:
            try:
                await self._publish(row)
                await session.execute(
                    update(ProductCatalogOutbox)
                    .where(ProductCatalogOutbox.id == row.id)
                    .values(published=True, published_at=datetime.now(UTC))
                )
            except Exception as e:
                await session.execute(
                    update(ProductCatalogOutbox)
                    .where(ProductCatalogOutbox.id == row.id)
                    .values(
                        publish_attempts=row.publish_attempts + 1,
                        last_attempted_at=datetime.now(UTC),
                        error=str(e),
                    )
                )
                logger.warning(
                    "outbox_publish_failed",
                    event_id=str(row.id),
                    event_type=row.event_type,
                    attempt=row.publish_attempts + 1,
                    error=str(e),
                )
            finally:
                await session.commit()

    async def _publish(self, row: ProductCatalogOutbox) -> None:
        payload_bytes = json.dumps(row.payload).encode("utf-8")
        await self._producer.send_and_wait(row.event_type, payload_bytes)
        logger.info(
            "outbox_event_published",
            event_id=str(row.id),
            event_type=row.event_type,
        )
