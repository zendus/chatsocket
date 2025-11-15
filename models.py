from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class MessageType(str, Enum):
    PRIVATE = "private"
    GROUP = "group"
    NOTIFICATION = "notification"

class NotificationType(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"

class NotificationPayload(BaseModel):
    to_user: str = Field(..., description="Target user ID")
    message: str = Field(..., min_length=1)
    type: NotificationType = Field(default=NotificationType.INFO)

class PrivateMessagePayload(BaseModel):
    to_user: str = Field(..., description="Target user ID")
    message: str = Field(..., min_length=1)

class GroupMessagePayload(BaseModel):
    room: str = Field(..., description="Group/room name")
    message: str = Field(..., min_length=1)

class JoinRoomPayload(BaseModel):
    room: str = Field(..., description="Group/room name")

class TypingPayload(BaseModel):
    to_user: Optional[str] = Field(None, description="For private typing indicator")
    room: Optional[str] = Field(None, description="For group typing indicator")

class ReadReceiptPayload(BaseModel):
    message_id: str = Field(..., description="Message ID to mark as read")

class MessageHistoryQuery(BaseModel):
    user_id: Optional[str] = None
    room: Optional[str] = None
    limit: int = Field(default=50, le=100)
    offset: int = Field(default=0, ge=0)

class Message(BaseModel):
    id: str
    type: MessageType
    from_user: str
    to_user: Optional[str] = None
    room: Optional[str] = None
    message: str
    timestamp: datetime
    read_by: List[str] = []