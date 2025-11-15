from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import socketio as sio_module
import logging
from datetime import datetime
import uvicorn

from config import settings
from redis_manager import redis_manager
from socket_handlers import sio
from models import MessageHistoryQuery

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting up server...")
    await redis_manager.connect()
    yield
    logger.info("Shutting down server...")
    await redis_manager.disconnect()

app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade FastAPI server with Socket.IO, Redis, and real-time features",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API Endpoints
@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }

@app.get("/health")
async def health_check():
    try:
        await redis_manager.redis.ping()
        redis_status = "healthy"
    except:
        redis_status = "unhealthy"
    
    online_users = await redis_manager.get_online_users()
    rooms = await redis_manager.get_all_rooms()
    
    return {
        "status": "healthy" if redis_status == "healthy" else "degraded",
        "redis": redis_status,
        "timestamp": datetime.utcnow().isoformat(),
        "connections": len(online_users),
        "rooms": len(rooms)
    }

@app.get("/users/online")
async def get_online_users():
    """Get list of online users"""
    users = await redis_manager.get_online_users()
    return {
        "online_users": users,
        "count": len(users)
    }

@app.get("/rooms")
async def get_rooms():
    """Get list of active rooms"""
    rooms = await redis_manager.get_all_rooms()
    rooms_info = {}
    
    for room, count in rooms.items():
        members = await redis_manager.get_room_members(room)
        rooms_info[room] = {
            "members": list(members),
            "member_count": count
        }
    
    return {
        "rooms": rooms_info,
        "count": len(rooms_info)
    }

@app.get("/rooms/{room_name}")
async def get_room_info(room_name: str):
    """Get information about a specific room"""
    members = await redis_manager.get_room_members(room_name)
    if not members:
        raise HTTPException(status_code=404, detail="Room not found")
    
    return {
        "room": room_name,
        "members": list(members),
        "member_count": len(members)
    }

@app.post("/messages/history")
async def get_message_history(query: MessageHistoryQuery):
    """Get message history"""
    messages = await redis_manager.get_message_history(
        user_id=query.user_id,
        room=query.room,
        limit=query.limit,
        offset=query.offset
    )
    
    return {
        "messages": messages,
        "count": len(messages)
    }

@app.get("/messages/conversation/{user1}/{user2}")
async def get_conversation(user1: str, user2: str, limit: int = 50):
    """Get conversation between two users"""
    messages = await redis_manager.get_conversation_history(user1, user2, limit)
    
    return {
        "participants": [user1, user2],
        "messages": messages,
        "count": len(messages)
    }

@app.get("/messages/unread/{user_id}")
async def get_unread_count(user_id: str, from_user: str = None):
    """Get unread message count"""
    count = await redis_manager.get_unread_count(user_id, from_user)
    
    return {
        "user_id": user_id,
        "unread_count": count
    }

@app.get("/users/{user_id}/rooms")
async def get_user_rooms(user_id: str):
    """Get all rooms a user is in"""
    rooms = await redis_manager.get_user_rooms(user_id)
    
    return {
        "user_id": user_id,
        "rooms": rooms,
        "count": len(rooms)
    }

# Mount Socket.IO app
socket_app = sio_module.ASGIApp(
    sio,
    other_asgi_app=app,
    socketio_path='/socket.io'
)

if __name__ == "__main__":
    uvicorn.run(
        socket_app,
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )