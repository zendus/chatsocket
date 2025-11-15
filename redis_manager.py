import redis.asyncio as redis
from typing import Optional, Set, List, Dict
import json
from datetime import datetime, timedelta
import logging
from config import settings

logger = logging.getLogger(__name__)

class RedisManager:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.pubsub = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
            await self.redis.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")
    
    # User Session Management
    async def set_user_session(self, user_id: str, session_id: str):
        """Map user to session"""
        await self.redis.hset("user_sessions", user_id, session_id)
        await self.redis.hset("session_users", session_id, user_id)
    
    async def get_user_session(self, user_id: str) -> Optional[str]:
        """Get session ID for user"""
        return await self.redis.hget("user_sessions", user_id)
    
    async def get_session_user(self, session_id: str) -> Optional[str]:
        """Get user ID for session"""
        return await self.redis.hget("session_users", session_id)
    
    async def remove_session(self, session_id: str) -> Optional[str]:
        """Remove session and return user_id"""
        user_id = await self.redis.hget("session_users", session_id)
        if user_id:
            await self.redis.hdel("user_sessions", user_id)
            await self.redis.hdel("session_users", session_id)
        return user_id
    
    async def get_online_users(self) -> List[str]:
        """Get all online users"""
        users = await self.redis.hkeys("user_sessions")
        return users if users else []
    
    # Room Management
    async def join_room(self, user_id: str, room: str):
        """Add user to room"""
        await self.redis.sadd(f"room:{room}:members", user_id)
    
    async def leave_room(self, user_id: str, room: str):
        """Remove user from room"""
        await self.redis.srem(f"room:{room}:members", user_id)
    
    async def get_room_members(self, room: str) -> Set[str]:
        """Get all members of a room"""
        members = await self.redis.smembers(f"room:{room}:members")
        return members if members else set()
    
    async def get_user_rooms(self, user_id: str) -> List[str]:
        """Get all rooms a user is in"""
        keys = await self.redis.keys("room:*:members")
        rooms = []
        for key in keys:
            if await self.redis.sismember(key, user_id):
                room_name = key.split(":")[1]
                rooms.append(room_name)
        return rooms
    
    async def get_all_rooms(self) -> Dict[str, int]:
        """Get all rooms with member counts"""
        keys = await self.redis.keys("room:*:members")
        rooms = {}
        for key in keys:
            room_name = key.split(":")[1]
            count = await self.redis.scard(key)
            rooms[room_name] = count
        return rooms
    
    # Message History
    async def save_message(self, message: Dict):
        """Save message to history"""
        message_id = message["id"]
        message_json = json.dumps(message, default=str)
        
        # Save to general message history
        await self.redis.zadd(
            "messages:all",
            {message_json: datetime.fromisoformat(message["timestamp"]).timestamp()}
        )
        
        # Save to user-specific history
        if message.get("type") == "private":
            from_user = message["from_user"]
            to_user = message["to_user"]
            
            # Save for both participants
            await self.redis.zadd(
                f"messages:user:{from_user}",
                {message_json: datetime.fromisoformat(message["timestamp"]).timestamp()}
            )
            await self.redis.zadd(
                f"messages:user:{to_user}",
                {message_json: datetime.fromisoformat(message["timestamp"]).timestamp()}
            )
        
        # Save to room-specific history
        elif message.get("type") == "group":
            room = message["room"]
            await self.redis.zadd(
                f"messages:room:{room}",
                {message_json: datetime.fromisoformat(message["timestamp"]).timestamp()}
            )
        
        # Set expiration (retention period)
        expire_seconds = settings.MESSAGE_RETENTION_DAYS * 24 * 60 * 60
        await self.redis.expire("messages:all", expire_seconds)
        
        # Store message metadata for read receipts
        await self.redis.hset(f"message:{message_id}", mapping=message)
        await self.redis.expire(f"message:{message_id}", expire_seconds)
    
    async def get_message_history(
        self,
        user_id: Optional[str] = None,
        room: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """Get message history"""
        if room:
            key = f"messages:room:{room}"
        elif user_id:
            key = f"messages:user:{user_id}"
        else:
            key = "messages:all"
        
        # Get messages in reverse chronological order
        messages = await self.redis.zrevrange(
            key, offset, offset + limit - 1
        )
        
        if not messages:
            return []
        
        return [json.loads(msg) for msg in messages]
    
    async def get_conversation_history(
        self,
        user1: str,
        user2: str,
        limit: int = 50
    ) -> List[Dict]:
        """Get private conversation between two users"""
        all_messages = await self.get_message_history(user_id=user1, limit=200)
        
        # Filter for messages between these two users
        conversation = [
            msg for msg in all_messages
            if msg.get("type") == "private" and (
                (msg["from_user"] == user1 and msg["to_user"] == user2) or
                (msg["from_user"] == user2 and msg["to_user"] == user1)
            )
        ]
        
        return conversation[:limit]
    
    # Read Receipts
    async def mark_message_read(self, message_id: str, user_id: str):
        """Mark message as read by user"""
        await self.redis.sadd(f"message:{message_id}:read_by", user_id)
    
    async def get_message_readers(self, message_id: str) -> Set[str]:
        """Get users who read the message"""
        readers = await self.redis.smembers(f"message:{message_id}:read_by")
        return readers if readers else set()
    
    async def get_unread_count(self, user_id: str, from_user: Optional[str] = None) -> int:
        """Get unread message count"""
        messages = await self.get_message_history(user_id=user_id, limit=100)
        
        unread = 0
        for msg in messages:
            if msg.get("to_user") == user_id and msg["from_user"] != user_id:
                if from_user and msg["from_user"] != from_user:
                    continue
                
                message_id = msg["id"]
                readers = await self.get_message_readers(message_id)
                if user_id not in readers:
                    unread += 1
        
        return unread
    
    # Typing Indicators (temporary, expire after 5 seconds)
    async def set_typing(self, user_id: str, target: str, is_room: bool = False):
        """Set typing indicator"""
        key = f"typing:room:{target}" if is_room else f"typing:user:{target}"
        await self.redis.sadd(key, user_id)
        await self.redis.expire(key, 5)  # Auto-expire after 5 seconds
    
    async def remove_typing(self, user_id: str, target: str, is_room: bool = False):
        """Remove typing indicator"""
        key = f"typing:room:{target}" if is_room else f"typing:user:{target}"
        await self.redis.srem(key, user_id)
    
    async def get_typing_users(self, target: str, is_room: bool = False) -> Set[str]:
        """Get users currently typing"""
        key = f"typing:room:{target}" if is_room else f"typing:user:{target}"
        users = await self.redis.smembers(key)
        return users if users else set()

redis_manager = RedisManager()