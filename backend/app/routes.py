import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.cities import distance_between
from app.db import get_db
from app.delivery import flight_duration, utcnow
from app.schemas import MessageCreate, MessageOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_model=MessageOut, status_code=201)
def send_message(payload: MessageCreate, db: Session = Depends(get_db)):
    distance_km = distance_between(payload.origin, payload.destination)
    sent_at = utcnow()
    try:
        arrival_at = sent_at + flight_duration(distance_km)
    except ValueError as exc:
        # Misconfigured FAST_FORWARD — fail clearly at send time, per spec.
        logger.error("rejecting send: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    message = models.Message(
        sender=payload.sender,
        recipient=payload.recipient,
        body=payload.body,
        origin=payload.origin,
        destination=payload.destination,
        distance_km=distance_km,
        status=models.IN_FLIGHT,
        sent_at=sent_at,
        arrival_at=arrival_at,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/{message_id}", response_model=MessageOut)
def get_message(message_id: int, db: Session = Depends(get_db)):
    message = db.get(models.Message, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="message not found")
    return message


@router.get("", response_model=list[MessageOut])
def list_messages(
    recipient: str | None = None,
    sender: str | None = None,
    db: Session = Depends(get_db),
):
    if recipient is None and sender is None:
        raise HTTPException(
            status_code=422, detail="provide recipient and/or sender"
        )
    query = select(models.Message)
    if recipient is not None:
        # Inbox semantics: only delivered messages — no peeking mid-flight.
        query = query.where(
            models.Message.recipient == recipient,
            models.Message.status == models.DELIVERED,
        )
    if sender is not None:
        query = query.where(models.Message.sender == sender)
    query = query.order_by(models.Message.sent_at.desc(), models.Message.id.desc())
    return db.execute(query).scalars().all()
