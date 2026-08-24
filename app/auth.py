import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import credentials, auth

load_dotenv()

# --- 1. INITIALIZATION LOGS ---
print(">>> [AUTH INIT] Checking Firebase initialization...", flush=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

google_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
firebase_project_id = os.getenv("FIREBASE_PROJECT_ID")

if google_creds and not os.path.isabs(google_creds):
    google_creds = str(PROJECT_ROOT / google_creds)

print(f">>> [AUTH INIT] FIREBASE_PROJECT_ID = {firebase_project_id!r}", flush=True)

try:
    app = firebase_admin.get_app()
    print(f">>> [AUTH INIT] Existing Firebase app found: {app.name} (Project: {app.project_id})", flush=True)
except ValueError:
    print(">>> [AUTH INIT] No existing Firebase app. Initializing new app...", flush=True)
    
    init_options = {"projectId": firebase_project_id} if firebase_project_id else {}
    
    if google_creds and os.path.exists(google_creds):
        cred = credentials.Certificate(google_creds)
        firebase_admin.initialize_app(cred, options=init_options)
    else:
        print(">>> [AUTH INIT] Initializing with Application Default Credentials (ADC)...", flush=True)
        firebase_admin.initialize_app(options=init_options)
        
    app = firebase_admin.get_app()
    print(f">>> [AUTH INIT] Firebase initialized successfully! Active project ID: {app.project_id}", flush=True)


security = HTTPBearer()


# --- 2. REQUEST & TOKEN VERIFICATION LOGS ---
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    
    # Log token presence and length (avoid printing full token in prod logs)
    token_preview = f"{token[:15]}...{token[-10:]}" if token and len(token) > 25 else "EMPTY/INVALID"
    print(f">>> [AUTH REQUEST] Received Bearer token: {token_preview} (len={len(token) if token else 0})", flush=True)
    
    try:
        # Verify token
        decoded_token = auth.verify_id_token(token)
        print(f">>> [AUTH REQUEST] Token verified successfully for user: {decoded_token.get('email')} (sub={decoded_token.get('sub')})", flush=True)
        return decoded_token
    except Exception as e:
        print(">>> [AUTH REQUEST ERROR] Token verification failed!", flush=True)
        print(f">>> [AUTH REQUEST ERROR] Exception Type: {type(e).__name__}", flush=True)
        print(f">>> [AUTH REQUEST ERROR] Exception Details: {str(e)}", flush=True)
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {type(e).__name__} - {str(e)}",
        )