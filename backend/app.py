from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import uuid
import os
from models import Market, Player, UserRole
from matching_engine import MatchingEngine

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize matching engine
engine = MatchingEngine()
connected_users = {}  # session_id -> user_id

# Initialize default markets
def initialize_markets():
    markets = [
        Market(id="market_a", name="Size of A", description="Market for asset A", position_limit=100),
        Market(id="market_b", name="Size of B", description="Market for asset B", position_limit=100),
        Market(id="market_ab", name="Size of A+B", description="Bundle market (A+B)", position_limit=100)
    ]
    for market in markets:
        engine.add_market(market)

initialize_markets()

# Game state
game_config = {
    'starting_cash': 10000,
    'game_started': False
}

# HTTP Routes
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

# WebSocket Events

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    emit('connected', {'session_id': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')
    if request.sid in connected_users:
        del connected_users[request.sid]

@socketio.on('register')
def handle_register(data):
    """Register a new user (admin or player)"""
    name = data.get('name', f'User_{uuid.uuid4().hex[:6]}')
    role = data.get('role', 'PLAYER')  # ADMIN or PLAYER

    user_id = str(uuid.uuid4())
    player = Player(
        id=user_id,
        name=name,
        role=UserRole[role],
        cash=game_config['starting_cash']
    )
    engine.add_player(player)
    connected_users[request.sid] = user_id

    emit('registered', {
        'user_id': user_id,
        'name': name,
        'role': role,
        'cash': player.cash
    })

    # Send initial game state
    emit('game_state', get_game_state())

    # Broadcast user joined
    socketio.emit('user_joined', {
        'user_id': user_id,
        'name': name,
        'role': role
    })

@socketio.on('get_game_state')
def handle_get_game_state():
    """Get current game state"""
    emit('game_state', get_game_state())

@socketio.on('submit_order')
def handle_submit_order(data):
    """Submit a new order"""
    try:
        user_id = connected_users.get(request.sid)
        if not user_id:
            emit('error', {'message': 'Not registered'})
            return

        market_id = data['market_id']
        side = data['side']  # BUY or SELL
        price = float(data['price'])
        quantity = int(data['quantity'])

        order, trades = engine.submit_order(user_id, market_id, side, price, quantity)

        # Broadcast order book update
        order_book = engine.order_books[market_id].get_order_book_display()
        socketio.emit('order_book_update', order_book)

        # Broadcast trades
        if trades:
            for trade in trades:
                socketio.emit('trade', trade.to_dict())

        # Emit success to sender
        emit('order_submitted', {
            'order_id': order.id,
            'message': f'Order submitted successfully. {len(trades)} trade(s) executed.'
        })

        # Update positions for affected users
        if trades:
            affected_users = set([trade.buyer_id for trade in trades] + [trade.seller_id for trade in trades])
            for uid in affected_users:
                send_position_update(uid)

    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('cancel_order')
def handle_cancel_order(data):
    """Cancel an existing order"""
    try:
        user_id = connected_users.get(request.sid)
        if not user_id:
            emit('error', {'message': 'Not registered'})
            return

        market_id = data['market_id']
        order_id = data['order_id']

        success = engine.cancel_order(user_id, market_id, order_id)

        if success:
            # Broadcast order book update
            order_book = engine.order_books[market_id].get_order_book_display()
            socketio.emit('order_book_update', order_book)

            emit('order_cancelled', {'order_id': order_id, 'message': 'Order cancelled successfully'})
        else:
            emit('error', {'message': 'Failed to cancel order'})

    except Exception as e:
        emit('error', {'message': str(e)})

# Admin Events

@socketio.on('admin_setup_game')
def handle_admin_setup(data):
    """Admin: Setup game configuration"""
    try:
        user_id = connected_users.get(request.sid)
        if not user_id or engine.players[user_id].role != UserRole.ADMIN:
            emit('error', {'message': 'Admin access required'})
            return

        # Update game config
        if 'starting_cash' in data:
            game_config['starting_cash'] = float(data['starting_cash'])

        if 'position_limits' in data:
            for market_id, limit in data['position_limits'].items():
                if market_id in engine.markets:
                    engine.markets[market_id].position_limit = int(limit)

        socketio.emit('game_config_updated', game_config)
        emit('success', {'message': 'Game configuration updated'})

    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('admin_start_game')
def handle_admin_start_game():
    """Admin: Start the game"""
    try:
        user_id = connected_users.get(request.sid)
        if not user_id or engine.players[user_id].role != UserRole.ADMIN:
            emit('error', {'message': 'Admin access required'})
            return

        game_config['game_started'] = True
        socketio.emit('game_started', {'message': 'Game has started!'})

    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('admin_end_game')
def handle_admin_end_game():
    """Admin: End the game and show leaderboard"""
    try:
        user_id = connected_users.get(request.sid)
        if not user_id or engine.players[user_id].role != UserRole.ADMIN:
            emit('error', {'message': 'Admin access required'})
            return

        game_config['game_started'] = False
        leaderboard = engine.get_leaderboard()

        socketio.emit('game_ended', {
            'message': 'Game has ended!',
            'leaderboard': leaderboard
        })

    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('admin_reset_game')
def handle_admin_reset_game():
    """Admin: Reset the game"""
    try:
        user_id = connected_users.get(request.sid)
        if not user_id or engine.players[user_id].role != UserRole.ADMIN:
            emit('error', {'message': 'Admin access required'})
            return

        engine.reset_game(game_config['starting_cash'])
        game_config['game_started'] = False

        socketio.emit('game_reset', {'message': 'Game has been reset'})
        socketio.emit('game_state', get_game_state())

    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('get_leaderboard')
def handle_get_leaderboard():
    """Get current leaderboard"""
    leaderboard = engine.get_leaderboard()
    emit('leaderboard', leaderboard)

# Helper functions

def get_game_state():
    """Get complete game state"""
    return {
        'markets': [market.to_dict() for market in engine.markets.values()],
        'order_books': engine.get_all_order_books(),
        'game_started': game_config['game_started'],
        'starting_cash': game_config['starting_cash']
    }

def send_position_update(user_id):
    """Send position update to a specific user"""
    player = engine.players.get(user_id)
    if not player:
        return

    # Find session_id for this user
    session_id = None
    for sid, uid in connected_users.items():
        if uid == user_id:
            session_id = sid
            break

    if session_id:
        socketio.emit('position_update', {
            'cash': player.cash,
            'positions': {k: v.to_dict() for k, v in player.positions.items()}
        }, room=session_id)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
