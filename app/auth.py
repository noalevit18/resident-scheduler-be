import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import credentials, auth

load_dotenv()

# Initialize Firebase Admin if not already initialized
try:
    firebase_admin.get_app()
except ValueError:
    google_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if google_creds and os.path.exists(google_creds):
        # Local development using service account file
        cred = credentials.Certificate(google_creds)
        firebase_admin.initialize_app(cred)
    else:
        # Production on GCP: Use Application Default Credentials (ADC)
        firebase_admin.initialize_app()

security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )