from datetime import date
from sqlalchemy.orm import Session
from app.models.models import SpecialDate
from app.schemas.schemas import SpecialDateBulkEntry
from uuid import UUID


class SpecialDateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, account_id: UUID):
        return (
            self.db.query(SpecialDate)
            .filter(SpecialDate.account_id == account_id)
            .order_by(SpecialDate.date)
            .all()
        )

    def get_by_date(self, account_id: UUID, date: date):
        return self.db.query(SpecialDate).filter(
            SpecialDate.account_id == account_id, SpecialDate.date == date,
        ).first()

    def save_all(
        self,
        upserts: list[SpecialDateBulkEntry],
        delete_dates: list[date],
        account_id: UUID,
        update_user_id: UUID | None,
    ):
        if delete_dates:
            self.db.query(SpecialDate).filter(
                SpecialDate.account_id == account_id, SpecialDate.date.in_(delete_dates),
            ).delete(synchronize_session=False)

        if upserts:
            existing_by_date = {
                obj.date: obj
                for obj in self.db.query(SpecialDate).filter(
                    SpecialDate.account_id == account_id,
                    SpecialDate.date.in_([entry.date for entry in upserts]),
                ).all()
            }
            for entry in upserts:
                obj = existing_by_date.get(entry.date)
                if obj:
                    obj.label = entry.label
                    obj.type = entry.type
                    obj.updated_by = update_user_id
                else:
                    self.db.add(SpecialDate(
                        account_id=account_id,
                        date=entry.date,
                        label=entry.label,
                        type=entry.type,
                        created_by=update_user_id,
                        updated_by=update_user_id,
                    ))

        self.db.commit()
        return self.get_all(account_id)
