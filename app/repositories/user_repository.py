from sqlalchemy import case, func
from sqlalchemy.orm import Session
from app.schemas.schemas import UserResponse, UserCreate
from app.models.models import User as UserModel
from uuid import UUID


def _canonical_email(email: str) -> str:
    """Normalize for comparison against Gmail-family addresses, which Google
    treats as equivalent regardless of dots or a '+tag' in the local part:
    - googlemail.com/gmail.com are the same domain.
    - dots in the local part are ignored ("john.doe" == "johndoe").
    - anything from '+' onward in the local part is ignored ("john+work" == "john").
    Scoped to gmail.com/googlemail.com only - other domains may treat dots/'+'
    as significant, so they're left untouched."""
    local, _, domain = email.strip().lower().partition("@")
    if domain == "googlemail.com":
        domain = "gmail.com"
    if domain == "gmail.com":
        local = local.split("+", 1)[0].replace(".", "")
    return f"{local}@{domain}"


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str):
        target = _canonical_email(email)

        lower_email = func.lower(UserModel.email)
        local_part = func.split_part(lower_email, "@", 1)
        domain_part = func.split_part(lower_email, "@", 2)
        canonical_domain = case((domain_part == "googlemail.com", "gmail.com"), else_=domain_part)
        canonical_local = case(
            (canonical_domain == "gmail.com", func.replace(func.split_part(local_part, "+", 1), ".", "")),
            else_=local_part,
        )
        normalized_column = canonical_local + "@" + canonical_domain

        user = self.db.query(UserModel).filter(normalized_column == target).first()
        return UserResponse.model_validate(user) if user else None

    def get_by_firebase_uid(self, firebase_uid: str):
        user = self.db.query(UserModel).filter(UserModel.firebase_uid == firebase_uid).first()
        return UserResponse.model_validate(user) if user else None

    def set_firebase_uid(self, user_id: UUID, firebase_uid: str):
        obj = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not obj:
            return None
        obj.firebase_uid = firebase_uid
        self.db.commit()
        return UserResponse.model_validate(obj)

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

