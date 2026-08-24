from sqlalchemy.orm import Session
from app.schemas.schemas import UserResponse, UserCreate
from app.models.models import User as UserModel
from uuid import UUID

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str):
        user = self.db.query(UserModel).filter(UserModel.email == email).first()
        return UserResponse.model_validate(user) if user else None

    def get_all(self, division_id: UUID):
        users = self.db.query(UserModel).filter(UserModel.division_id == division_id).all()
        return [UserResponse.model_validate(u) for u in users]

    def create(self, data: UserCreate):
        payload = data.model_dump(exclude={"id", "created_at", "updated_at"})
        db_obj = UserModel(**payload)
        self.db.add(db_obj)
        self.db.commit()
        return UserResponse.model_validate(db_obj)

    def delete(self, user_id: UUID, division_id: UUID):
        obj = self.db.query(UserModel).filter(UserModel.id == user_id, UserModel.division_id == division_id).first()
        if not obj:
            return None
        name = obj.name
        self.db.delete(obj)
        self.db.commit()
        return name

    def update_user(self, user_id: UUID, division_id: UUID, user_data: dict):
        obj = self.db.query(UserModel).filter(UserModel.id == user_id, UserModel.division_id == division_id).first()
        if obj:
            for key, value in user_data.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            self.db.commit()
            return UserResponse.model_validate(obj)
        return None

