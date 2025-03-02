#run using uvicorn main:app --reload
#http://127.0.0.1:8000

from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_db
from models import User
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from decimal import Decimal
import logging
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
import httpx  # To make API requests in FastAPI


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],  # Change this to your frontend URL for security
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

@app.get("/")
async def read_root():
    return {"message": "Hello, FastAPI with PostgreSQL!"}

#ensure that all inputs are of required datatype
class UserCreate(BaseModel):
    email: str
    password: str
    username: str
    balance: Decimal

class LoginRequest(BaseModel):
    username: str
    password: str

class BookingRequest(BaseModel):
    event_id: int
    user_id: int
    price: int
    ticket_count: int

#handle get at users
@app.get("/users/")
async def get_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return users

@app.post("/login/")
async def login(user: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(User).where(User.username == user.username))
        db_user = result.scalars().first()
        if not db_user or db_user.password != user.password:  # Ideally use hashing
            raise HTTPException(status_code=401, detail="Invalid username or password")

        return {"username": db_user.username, "balance": db_user.balance, "id": db_user.id}
    
    except HTTPException as http_err:
        raise http_err  # Don't catch & replace HTTP exceptions, just re-raise them

    except Exception as e:
        logger.error(f"Error retrieving user: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


# API Endpoint to Create a User
@app.post("/users/")
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        new_user = User(email=user.email, password=user.password, username=user.username, balance=user.balance)
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info(f"User Created: {new_user}")
        return {
            "id": new_user.id,
            "email": new_user.email,
            "username": new_user.username,
            "balance": new_user.balance
        }
    except IntegrityError:  # This catches unique constraint violations
        await db.rollback()  # Rollback the transaction
        logger.error("User creation failed: Username or email already exists")
        raise HTTPException(status_code=400, detail="Username or email already exists")
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@app.get("/users/events/")
async def get_events():
    events_url = "http://localhost:8080/api/events"  # Event Service URL
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(events_url)
            response.raise_for_status()  # Raise an error for bad responses (4xx, 5xx)
            return response.json()  # Return the events to the frontend
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Error retrieving events")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/users/bookings/")
async def create_booking(booking: BookingRequest, db: AsyncSession = Depends(get_db)):
    # Step 1: Get User from Database
    print(f"Received booking request: {booking.dict()}")  # Log request
    result = await db.execute(select(User).where(User.id == booking.user_id))
    db_user = result.scalars().first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Step 2: Check User Balance
    if db_user.balance < booking.price:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Step 3: Call Booking API to Create Booking
    try:
        async with httpx.AsyncClient() as client:
            booking_response = await client.post(
                "http://127.0.0.1:5000/bookings", json=booking.dict()
            )
            booking_response.raise_for_status()
            booking_data = booking_response.json()
    except httpx.HTTPStatusError as e:
        if e.response is not None:
            error_json = e.response.json()  # Get error response as dict
            error_message = error_json.get("error", str(error_json))  # Extract error field if it exists
        else:
            error_message = "Booking API error"
    
        raise HTTPException(status_code=e.response.status_code, detail=error_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Step 4: Deduct Balance After Successful Booking
    db_user.balance -= booking.price
    await db.commit()

    return {
        "message": "Booking successful",
        "booking_id": booking_data["booking_id"],
        "remaining_balance": db_user.balance
    }