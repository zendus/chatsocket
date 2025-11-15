import socketio
from datetime import datetime
import uuid
import logging
from models import (
    NotificationPayload, PrivateMessagePayload, GroupMessagePayload,
    JoinRoomPayload, TypingPayload, ReadReceiptPayload, MessageType
)
from redis_manager import redis_manager

logger = logging.getLogger(__name__)

sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=False
)

@sio.event
async def connect(sid, environ, auth):
    """Handle client connection"""
    user_id = auth.get('user_id') if auth else None
    
    if not user_id:
        logger.warning(f"Connection rejected for {sid}: No user_id provided")
        return False
    
    await redis_manager.set_user_session(user_id, sid)
    
    # Get user's rooms
    rooms = await redis_manager.get_user_rooms(user_id)
    
    await sio.emit('connected', {
        'user_id': user_id,
        'session_id': sid,
        'rooms': rooms,
        'timestamp': datetime.utcnow().isoformat()
    }, room=sid)
    
    logger.info(f"Client {sid} connected as user {user_id}")
    return True

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    user_id = await redis_manager.remove_session(sid)
    if user_id:
        # Remove from all rooms
        rooms = await redis_manager.get_user_rooms(user_id)
        for room in rooms:
            await redis_manager.leave_room(user_id, room)
            await sio.emit('user_left', {
                'user_id': user_id,
                'room': room,
                'timestamp': datetime.utcnow().isoformat()
            }, room=room)
        
        logger.info(f"Client {sid} (user {user_id}) disconnected")

@sio.event
async def send_notification(sid, data):
    """Send notification to specific user"""
    try:
        sender_id = await redis_manager.get_session_user(sid)
        if not sender_id:
            await sio.emit('error', {'message': 'Unauthorized'}, room=sid)
            return
        
        payload = NotificationPayload(**data)
        target_session = await redis_manager.get_user_session(payload.to_user)
        
        if not target_session:
            await sio.emit('error', {
                'message': f'User {payload.to_user} is not online'
            }, room=sid)
            return
        
        notification = {
            'id': str(uuid.uuid4()),
            'type': MessageType.NOTIFICATION,
            'from_user': sender_id,
            'to_user': payload.to_user,
            'message': payload.message,
            'notification_type': payload.type,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await redis_manager.save_message(notification)
        await sio.emit('notification', notification, room=target_session)
        await sio.emit('notification_sent', {
            'to_user': payload.to_user,
            'status': 'delivered'
        }, room=sid)
        
        logger.info(f"Notification sent from {sender_id} to {payload.to_user}")
        
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def send_private_message(sid, data):
    """Send private message to specific user"""
    try:
        sender_id = await redis_manager.get_session_user(sid)
        if not sender_id:
            await sio.emit('error', {'message': 'Unauthorized'}, room=sid)
            return
        
        payload = PrivateMessagePayload(**data)
        target_session = await redis_manager.get_user_session(payload.to_user)
        
        message = {
            'id': str(uuid.uuid4()),
            'type': MessageType.PRIVATE,
            'from_user': sender_id,
            'to_user': payload.to_user,
            'message': payload.message,
            'timestamp': datetime.utcnow().isoformat(),
            'read_by': []
        }
        
        await redis_manager.save_message(message)
        
        if target_session:
            await sio.emit('private_message', message, room=target_session)
            await sio.emit('message_sent', {
                'message_id': message['id'],
                'to_user': payload.to_user,
                'status': 'delivered'
            }, room=sid)
        else:
            await sio.emit('message_sent', {
                'message_id': message['id'],
                'to_user': payload.to_user,
                'status': 'offline'
            }, room=sid)
        
        # Remove typing indicator
        await redis_manager.remove_typing(sender_id, payload.to_user)
        
        logger.info(f"Private message sent from {sender_id} to {payload.to_user}")
        
    except Exception as e:
        logger.error(f"Error sending private message: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def join_group(sid, data):
    """Join a group/room"""
    try:
        user_id = await redis_manager.get_session_user(sid)
        if not user_id:
            await sio.emit('error', {'message': 'Unauthorized'}, room=sid)
            return
        
        payload = JoinRoomPayload(**data)
        room_name = payload.room
        
        await sio.enter_room(sid, room_name)
        await redis_manager.join_room(user_id, room_name)
        
        members = await redis_manager.get_room_members(room_name)
        
        await sio.emit('user_joined', {
            'user_id': user_id,
            'room': room_name,
            'timestamp': datetime.utcnow().isoformat()
        }, room=room_name)
        
        # Get recent message history
        history = await redis_manager.get_message_history(room=room_name, limit=50)
        
        await sio.emit('joined_group', {
            'room': room_name,
            'members': list(members),
            'member_count': len(members),
            'history': history
        }, room=sid)
        
        logger.info(f"User {user_id} joined group {room_name}")
        
    except Exception as e:
        logger.error(f"Error joining group: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def leave_group(sid, data):
    """Leave a group/room"""
    try:
        user_id = await redis_manager.get_session_user(sid)
        if not user_id:
            await sio.emit('error', {'message': 'Unauthorized'}, room=sid)
            return
        
        payload = JoinRoomPayload(**data)
        room_name = payload.room
        
        await sio.leave_room(sid, room_name)
        await redis_manager.leave_room(user_id, room_name)
        
        await sio.emit('user_left', {
            'user_id': user_id,
            'room': room_name,
            'timestamp': datetime.utcnow().isoformat()
        }, room=room_name)
        
        await sio.emit('left_group', {'room': room_name}, room=sid)
        
        logger.info(f"User {user_id} left group {room_name}")
        
    except Exception as e:
        logger.error(f"Error leaving group: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def send_group_message(sid, data):
    """Send message to group/room"""
    try:
        sender_id = await redis_manager.get_session_user(sid)
        if not sender_id:
            await sio.emit('error', {'message': 'Unauthorized'}, room=sid)
            return
        
        payload = GroupMessagePayload(**data)
        room_name = payload.room
        
        members = await redis_manager.get_room_members(room_name)
        if sender_id not in members:
            await sio.emit('error', {
                'message': f'You are not a member of {room_name}'
            }, room=sid)
            return
        
        message = {
            'id': str(uuid.uuid4()),
            'type': MessageType.GROUP,
            'from_user': sender_id,
            'room': room_name,
            'message': payload.message,
            'timestamp': datetime.utcnow().isoformat(),
            'read_by': []
        }
        
        await redis_manager.save_message(message)
        await sio.emit('group_message', message, room=room_name)
        
        # Remove typing indicator
        await redis_manager.remove_typing(sender_id, room_name, is_room=True)
        
        logger.info(f"Group message sent by {sender_id} to {room_name}")
        
    except Exception as e:
        logger.error(f"Error sending group message: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def typing(sid, data):
    """Handle typing indicator"""
    try:
        user_id = await redis_manager.get_session_user(sid)
        if not user_id:
            return
        
        payload = TypingPayload(**data)
        
        if payload.to_user:
            # Private typing
            await redis_manager.set_typing(user_id, payload.to_user)
            target_session = await redis_manager.get_user_session(payload.to_user)
            if target_session:
                await sio.emit('user_typing', {
                    'user_id': user_id,
                    'timestamp': datetime.utcnow().isoformat()
                }, room=target_session)
        
        elif payload.room:
            # Group typing
            members = await redis_manager.get_room_members(payload.room)
            if user_id in members:
                await redis_manager.set_typing(user_id, payload.room, is_room=True)
                await sio.emit('user_typing', {
                    'user_id': user_id,
                    'room': payload.room,
                    'timestamp': datetime.utcnow().isoformat()
                }, room=payload.room, skip_sid=sid)
        
    except Exception as e:
        logger.error(f"Error handling typing: {str(e)}")

@sio.event
async def stop_typing(sid, data):
    """Handle stop typing indicator"""
    try:
        user_id = await redis_manager.get_session_user(sid)
        if not user_id:
            return
        
        payload = TypingPayload(**data)
        
        if payload.to_user:
            await redis_manager.remove_typing(user_id, payload.to_user)
            target_session = await redis_manager.get_user_session(payload.to_user)
            if target_session:
                await sio.emit('user_stopped_typing', {
                    'user_id': user_id,
                    'timestamp': datetime.utcnow().isoformat()
                }, room=target_session)
        
        elif payload.room:
            await redis_manager.remove_typing(user_id, payload.room, is_room=True)
            await sio.emit('user_stopped_typing', {
                'user_id': user_id,
                'room': payload.room,
                'timestamp': datetime.utcnow().isoformat()
            }, room=payload.room, skip_sid=sid)
        
    except Exception as e:
        logger.error(f"Error handling stop typing: {str(e)}")

@sio.event
async def mark_read(sid, data):
    """Mark message as read"""
    try:
        user_id = await redis_manager.get_session_user(sid)
        if not user_id:
            await sio.emit('error', {'message': 'Unauthorized'}, room=sid)
            return
        
        payload = ReadReceiptPayload(**data)
        await redis_manager.mark_message_read(payload.message_id, user_id)
        
        # Notify sender
        message_data = await redis_manager.redis.hgetall(f"message:{payload.message_id}")
        if message_data:
            sender = message_data.get('from_user')
            if sender:
                sender_session = await redis_manager.get_user_session(sender)
                if sender_session:
                    await sio.emit('message_read', {
                        'message_id': payload.message_id,
                        'read_by': user_id,
                        'timestamp': datetime.utcnow().isoformat()
                    }, room=sender_session)
        
        logger.info(f"Message {payload.message_id} marked read by {user_id}")
        
    except Exception as e:
        logger.error(f"Error marking message read: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)