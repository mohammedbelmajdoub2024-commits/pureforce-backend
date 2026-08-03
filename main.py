import os
import uuid
import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import jwt
import bcrypt
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import requests as http_requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pureforce:secret@db:5432/pureforce")
JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# --- Database Setup ---
is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    history = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(100), nullable=False)
    product = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False)
    address = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Ensure tables are created (in a real app, use Alembic)
from sqlalchemy import text
try:
    with engine.connect() as conn:
        # Check if the 'orders' table exists and lacks the 'user_id' column
        res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='orders' AND column_name='user_id'"))
        row = res.fetchone()
        
        # If the table exists but is missing 'user_id', drop it to trigger recreation
        # Also check if table exists first to avoid false drops
        table_exists_res = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'orders')"))
        table_exists = table_exists_res.scalar()
        
        if table_exists and not row:
            print("Detected outdated 'orders' table. Dropping to recreate with 'user_id' column.")
            conn.execute(text("DROP TABLE IF EXISTS orders CASCADE"))
            conn.commit()
except Exception as migration_err:
    print(f"Skipping orders table schema migration check: {migration_err}")

Base.metadata.create_all(bind=engine)

# --- Security ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Auth Dependency ---
from auth import verify_token

def get_current_user(decoded_token: dict = Depends(verify_token), db: Session = Depends(get_db)):
    email = decoded_token.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload: no email")
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Auto-create user in local DB if they registered via Firebase
        user = User(
            email=email, 
            username=email.split('@')[0], 
            password_hash="firebase_managed"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# --- App & Endpoints ---
app = FastAPI(title="PureForce Bleach API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://stirring-monstera-e17e3e.netlify.app"],
   allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserCreate(BaseModel):
    email: str
    username: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class ChatPrompt(BaseModel):
    session_id: str
    prompt: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/register", status_code=201)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pw = get_password_hash(user.password)
    new_user = User(email=user.email, username=user.username, password_hash=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created successfully", "user_id": new_user.id}

@app.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    token = create_access_token({"sub": str(db_user.id), "username": db_user.username})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/generate")
def generate(req: ChatPrompt, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured in .env")
    
    try:
        session_id = uuid.UUID(req.session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id format")

    chat_session = db.query(ChatSession).filter(ChatSession.id == str(session_id), ChatSession.user_id == user.id).first()
    
    if not chat_session:
        chat_session = ChatSession(id=str(session_id), user_id=user.id, history=[])
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)
    
    history = list(chat_session.history)
    history.append({"role": "user", "parts": [req.prompt]})
    
    try:
        # Build messages for Groq (OpenAI-compatible format)
        messages = [
            {"role": "system", "content": "You are PureForce AI, a helpful virtual expert for PureForce Bleach products. You help customers use products safely, answer cleaning questions, and provide usage tips. Be friendly, concise, and professional."}
        ]
        for msg in history[:-1]:
            role = "assistant" if msg["role"] == "assistant" else "user"
            text = msg["parts"][0] if isinstance(msg["parts"][0], str) else str(msg["parts"][0])
            messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": req.prompt})

        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }

        resp = http_requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )

        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=resp.json().get("error", {}).get("message", resp.text))

        ai_text = resp.json()["choices"][0]["message"]["content"]

        history.append({"role": "assistant", "parts": [ai_text]})
        chat_session.history = history
        db.commit()

        return {"response": ai_text}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class OrderRequest(BaseModel):
    name: str
    email: str
    phone: str
    product: str
    quantity: int
    address: str

from email_utils import send_order_notification

@app.post("/order")
def create_order(req: OrderRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # 1. Persist the order in the SQLite database
        new_order = Order(
            user_id=user.id,
            name=req.name,
            email=req.email,
            phone=req.phone,
            product=req.product,
            quantity=req.quantity,
            address=req.address
        )
        db.add(new_order)
        db.commit()
        db.refresh(new_order)

        # 2. Attempt to email the order notification (fails gracefully if SMTP configs are missing)
        try:
            send_order_notification({
                "name": req.name,
                "email": req.email,
                "phone": req.phone,
                "product": req.product,
                "quantity": req.quantity,
                "address": req.address
            })
        except Exception as email_err:
            # We print the error but do not fail the request since the order is safely saved in the DB
            print(f"Skipping order email notification due to: {email_err}")

        return {"message": "Order placed successfully", "order_id": new_order.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders")
def get_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        orders = db.query(Order).filter(Order.user_id == user.id).order_by(Order.created_at.desc()).all()
        return orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

