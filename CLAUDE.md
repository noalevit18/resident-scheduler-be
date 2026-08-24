# Project Overview & Architecture
- **Stack**: Python FastAPI (Backend), SQLAlchemy, Alembic, Pydantic, PostgreSQL, Docker.
- **Backend structure**: `backend/app/` — routes in `routers/`, business logic in `services/`, DB models in `models/`, DAO in `repositories/`, pydantic schemas in `schemas/`.
- ** Dependency injection**: all the dependencies are in `app/dependencies`.
- ** Alembic migration files are in `app/migrations/` and init file is `app/alembic.ini`.

# Workflow & Commands
- **Install BE**: `cd backend && pip install --no-cache-dir -r requirements.txt`
- **Run BE Dev**: `uvicorn app.main:app --reload`
- **Run Tests**: `pytest` (backend)
- 

# Code Style & Conventions
- **Python**: PEP 8 with type hints on all functions and Pydantic models for request/response payloads.
- **Error Handling**: Return unified API error response format: `{ "error": "code", "message": "details" }`.

# Git & Verification Instructions
- Run typecheck and unit tests before completing any feature work.
- Keep commits scoped and descriptive.


### Standards
1. **Layered Architecture:** Enforce strict `Router -> Service -> Repository` separation:
   - **Router:** Handles HTTP routing, Pydantic validation, and response mapping.
   - **Service:** Contains business logic, domain rules, and orchestration.
   - **Repository:** Manages direct PostgreSQL operations via SQLAlchemy 2.0+ async syntax.
2. **Authentication:** Authenticate requests using Firebase Admin SDK (Google Firebase JWT tokens).
3. **Structured Logging:**
   - Use the project's standard `Logger`.
   - **Mandatory:** Print an `INFO` level log upon successfully completing any complex action or data operation (e.g., `logger.info("Successfully calculated shift distribution for period_id=%s", period_id)`).