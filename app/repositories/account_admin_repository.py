from sqlalchemy.orm import Session
from models.models import AccountAdmin
from schemas.schemas import AccountAdminCreate
from uuid import UUID

class AccountAdminRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, account_id: UUID):
        return self.db.query(AccountAdmin).filter(AccountAdmin.account_id == account_id).all()

    def create(self, data: AccountAdminCreate):
        db_obj = AccountAdmin(**data.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, admin_id: UUID, account_id: UUID):
        obj = self.db.query(AccountAdmin).filter(AccountAdmin.id == admin_id, AccountAdmin.account_id == account_id).first()
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False
