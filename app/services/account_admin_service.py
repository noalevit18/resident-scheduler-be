from repositories.account_admin_repository import AccountAdminRepository
from schemas.schemas import AccountAdminCreate
from uuid import UUID

class AccountAdminService:
    def __init__(self, repository: AccountAdminRepository):
        self.repository = repository

    def get_all_admins(self, account_id: UUID):
        return self.repository.get_all(account_id)

    def create_admin(self, data: AccountAdminCreate):
        return self.repository.create(data)

    def delete_admin(self, admin_id: UUID, account_id: UUID):
        if not self.repository.delete(admin_id, account_id):
            raise ValueError("Admin not found")
        return True
