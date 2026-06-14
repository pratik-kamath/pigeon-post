import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app import models
from app.auth_routes import get_current_user
from app.cities import distance_between
from app.db import get_db
from app.delivery import flight_duration, utcnow
from app.schemas import MessageCreate, MessageOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_model=MessageOut, status_code=201)
def send_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    recipient = db.execute(
        select(models.User).where(
            func.lower(models.User.username) == payload.recipient.lower()
        )
    ).scalar_one_or_none()
    if recipient is None:
        raise HTTPException(status_code=404, detail="recipient not found")
    if recipient.id == current_user.id:
        raise HTTPException(
            status_code=422, detail="can't send a pigeon to yourself"
        )

    distance_km = distance_between(payload.origin, payload.destination)
    sent_at = utcnow()
    try:
        arrival_at = sent_at + flight_duration(distance_km)
    except ValueError as exc:
        # Misconfigured FAST_FORWARD — fail clearly at send time, per spec.
        logger.error("rejecting send: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    message = models.Message(
        sender_id=current_user.id,
        recipient_id=recipient.id,
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


# Static paths MUST be declared before "/{message_id}" so they aren't captured
# by the dynamic route.
@router.get("/inbox", response_model=list[MessageOut])
def inbox(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Inbox semantics: only delivered messages addressed to me.
    query = (
        select(models.Message)
        .options(
            joinedload(models.Message.sender_user),
            joinedload(models.Message.recipient_user),
        )
        .where(
            models.Message.recipient_id == current_user.id,
            models.Message.status == models.DELIVERED,
        )
        .order_by(models.Message.sent_at.desc(), models.Message.id.desc())
    )
    return db.execute(query).scalars().all()


@router.get("/sent", response_model=list[MessageOut])
def sent(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = (
        select(models.Message)
        .options(
            joinedload(models.Message.sender_user),
            joinedload(models.Message.recipient_user),
        )
        .where(models.Message.sender_id == current_user.id)
        .order_by(models.Message.sent_at.desc(), models.Message.id.desc())
    )
    return db.execute(query).scalars().all()


@router.get("/{message_id}", response_model=MessageOut)
def get_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    message = db.get(
        models.Message,
        message_id,
        # Eager-load both parties so MessageOut resolves usernames without a
        # lazy load, consistent with the inbox/sent endpoints.
        options=[
            joinedload(models.Message.sender_user),
            joinedload(models.Message.recipient_user),
        ],
    )
    if message is None or current_user.id not in (
        message.sender_id,
        message.recipient_id,
    ):
        # 404 (not 403) so non-parties can't probe which ids exist.
        raise HTTPException(status_code=404, detail="message not found")
    return message
