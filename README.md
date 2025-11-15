# WebSocket Messaging Server

Production-grade FastAPI server with Socket.IO, Redis, real-time messaging, typing indicators, and read receipts.

## Features

✅ **Real-time Messaging**

- Private messages between users
- Group chat rooms
- User notifications

✅ **Message History**

- Persistent message storage in Redis
- Conversation history retrieval
- Configurable retention period

✅ **Typing Indicators**

- Real-time typing status for private chats
- Group chat typing indicators
- Auto-expiring indicators (5 seconds)

✅ **Read Receipts**

- Track message read status
- Notify senders when messages are read
- Unread message counts

✅ **User Presence**

- Online/offline status
- Room membership tracking
- User session management

## Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Install and start Redis:

```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis

# Docker
docker run -d -p 6379:6379 redis:latest
```

3. Configure environment:

```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the server:

```bash
python main.py
```

## File Structure

```
├── main.py              # FastAPI app and REST endpoints
├── config.py            # Configuration and settings
├── models.py            # Pydantic models
├── redis_manager.py     # Redis connection and operations
├── socket_handlers.py   # Socket.IO event handlers
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
└── README.md           # Documentation
```

## Socket.IO Events

### Client → Server

**Connection**

```javascript
socket = io('http://localhost:8000', {
  auth: { user_id: 'user123' },
});
```

**Send Private Message**

```javascript
socket.emit('send_private_message', {
  to_user: 'user456',
  message: 'Hello!',
});
```

**Send Group Message**

```javascript
socket.emit('send_group_message', {
  room: 'general',
  message: 'Hello everyone!',
});
```

**Send Notification**

```javascript
socket.emit('send_notification', {
  to_user: 'user456',
  message: 'You have a new follower',
  type: 'info', // info, warning, error, success
});
```

**Join Group**

```javascript
socket.emit('join_group', {
  room: 'general',
});
```

**Leave Group**

```javascript
socket.emit('leave_group', {
  room: 'general',
});
```

**Typing Indicator**

```javascript
// Private chat
socket.emit('typing', { to_user: 'user456' });
socket.emit('stop_typing', { to_user: 'user456' });

// Group chat
socket.emit('typing', { room: 'general' });
socket.emit('stop_typing', { room: 'general' });
```

**Read Receipt**

```javascript
socket.emit('mark_read', {
  message_id: 'msg-uuid-here',
});
```

### Server → Client

**Connected**

```javascript
socket.on('connected', (data) => {
  console.log('Connected:', data);
  // { user_id, session_id, rooms, timestamp }
});
```

**Private Message**

```javascript
socket.on('private_message', (message) => {
  console.log('New message:', message);
  // { id, type, from_user, to_user, message, timestamp, read_by }
});
```

**Group Message**

```javascript
socket.on('group_message', (message) => {
  console.log('Group message:', message);
  // { id, type, from_user, room, message, timestamp, read_by }
});
```

**Notification**

```javascript
socket.on('notification', (notification) => {
  console.log('Notification:', notification);
});
```

**User Joined/Left**

```javascript
socket.on('user_joined', (data) => {
  console.log('User joined:', data);
});

socket.on('user_left', (data) => {
  console.log('User left:', data);
});
```

**Typing Indicators**

```javascript
socket.on('user_typing', (data) => {
  console.log('User typing:', data);
});

socket.on('user_stopped_typing', (data) => {
  console.log('User stopped typing:', data);
});
```

**Read Receipt**

```javascript
socket.on('message_read', (data) => {
  console.log('Message read:', data);
  // { message_id, read_by, timestamp }
});
```

**Errors**

```javascript
socket.on('error', (error) => {
  console.error('Error:', error);
});
```

## REST API Endpoints

**Health Check**

```
GET /health
```

**Online Users**

```
GET /users/online
```

**List Rooms**

```
GET /rooms
```

**Room Info**

```
GET /rooms/{room_name}
```

**Message History**

```
POST /messages/history
{
    "user_id": "user123",  // optional
    "room": "general",     // optional
    "limit": 50,
    "offset": 0
}
```

**Conversation History**

```
GET /messages/conversation/{user1}/{user2}?limit=50
```

**Unread Count**

```
GET /messages/unread/{user_id}?from_user=user456
```

**User Rooms**

```
GET /users/{user_id}/rooms
```

## Client Example

```javascript
// Connect
const socket = io('http://localhost:8000', {
  auth: { user_id: 'alice' },
});

// Listen for connection
socket.on('connected', (data) => {
  console.log('Connected:', data);
});

// Join a room
socket.emit('join_group', { room: 'general' });

// Listen for group messages
socket.on('group_message', (msg) => {
  console.log(`${msg.from_user}: ${msg.message}`);
});

// Send a message
socket.emit('send_group_message', {
  room: 'general',
  message: 'Hello everyone!',
});

// Typing indicator
let typingTimeout;
messageInput.addEventListener('input', () => {
  socket.emit('typing', { room: 'general' });

  clearTimeout(typingTimeout);
  typingTimeout = setTimeout(() => {
    socket.emit('stop_typing', { room: 'general' });
  }, 3000);
});

// Mark message as read
socket.on('private_message', (msg) => {
  displayMessage(msg);
  socket.emit('mark_read', { message_id: msg.id });
});
```

## Production Deployment

### Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
```

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - '6379:6379'
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  app:
    build: .
    ports:
      - '8000:8000'
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      - redis
    restart: unless-stopped

volumes:
  redis_data:
```

Run with Docker:

```bash
docker-compose up -d
```

### Scaling Considerations

1. **Redis Cluster**: Use Redis Cluster or Sentinel for high availability
2. **Load Balancing**: Use sticky sessions for Socket.IO
3. **Message Queue**: Add RabbitMQ/Kafka for inter-server communication
4. **Database**: Add PostgreSQL/MongoDB for permanent storage
5. **Monitoring**: Add Prometheus + Grafana
6. **Rate Limiting**: Implement per-user rate limits

## Security Best Practices

1. **Authentication**: Implement JWT token authentication
2. **Authorization**: Add role-based access control
3. **Rate Limiting**: Prevent abuse with rate limits
4. **Input Validation**: All inputs are validated with Pydantic
5. **SSL/TLS**: Use HTTPS in production
6. **CORS**: Configure allowed origins properly
7. **Redis Security**: Use password authentication

## Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/
```

## License

MIT License
