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

# Game state
game_config = {
    'starting_cash': 10000,
    'game_started': False,
    'max_markets': 10
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

@socketio.on('admin_create_market')
def handle_admin_create_market(data):
    """Admin: Create a new market"""
    try:
        user_id = connected_users.get(request.sid)
        if not user_id or engine.players[user_id].role != UserRole.ADMIN:
            emit('error', {'message': 'Admin access required'})
            return

        # Check max markets
        if len(engine.markets) >= game_config['max_markets']:
            emit('error', {'message': f'Maximum {game_config["max_markets"]} markets allowed'})
            return

        market_id = data.get('id')
        name = data.get('name')
        description = data.get('description', '')
        position_limit = int(data.get('position_limit', 100))
        market_type = data.get('market_type', 'BASIC')
        bundle_formula = data.get('bundle_formula')

        # Validate
        if not market_id or not name:
            emit('error', {'message': 'Market ID and name are required'})
            return

        if market_id in engine.markets:
            emit('error', {'message': 'Market ID already exists'})
            return

        # Create market
        market = Market(
            id=market_id,
            name=name,
            description=description,
            position_limit=position_limit,
            market_type=market_type,
            bundle_formula=bundle_formula
        )

        engine.add_market(market)

        socketio.emit('market_created', {
            'market': market.to_dict(),
            'message': f'Market "{name}" created successfully'
        })

    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('admin_delete_market')
def handle_admin_delete_market(data):
    """Admin: Delete a market"""
    try:
        user_id = connected_users.get(request.sid)
        if not user_id or engine.players[user_id].role != UserRole.ADMIN:
            emit('error', {'message': 'Admin access required'})
            return

        market_id = data.get('market_id')

        if engine.delete_market(market_id):
            socketio.emit('market_deleted', {
                'market_id': market_id,
                'message': f'Market deleted successfully'
            })
        else:
            emit('error', {'message': 'Cannot delete market with active orders or market not found'})

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

        # Check if at least one market exists
        if len(engine.markets) == 0:
            emit('error', {'message': 'Create at least one market before starting the game'})
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

@socketio.on('admin_resolve_game')
def handle_admin_resolve_game(data):
    """Admin: Resolve the game with true values for basic markets"""
    try:
        user_id = connected_users.get(request.sid)
        if not user_id or engine.players[user_id].role != UserRole.ADMIN:
            emit('error', {'message': 'Admin access required'})
            return

        true_values = data.get('true_values', {})

        # Validate that we have values for all BASIC markets
        basic_markets = [m for m in engine.markets.values() if m.market_type == "BASIC"]

        if not basic_markets:
            emit('error', {'message': 'No basic markets exist'})
            return

        missing_markets = []
        for market in basic_markets:
            if market.id not in true_values:
                missing_markets.append(market.name)
            elif true_values[market.id] <= 0:
                emit('error', {'message': f'True value for {market.name} must be positive'})
                return

        if missing_markets:
            emit('error', {'message': f'Missing true values for: {", ".join(missing_markets)}'})
            return

        # Resolve the game
        results = engine.resolve_game(true_values, game_config['starting_cash'])

        # End the game
        game_config['game_started'] = False

        # Create message with true values
        values_str = ", ".join([f'{engine.markets[mid].name}=${val:.2f}' for mid, val in results['true_values'].items()])

        # Broadcast results to all players
        socketio.emit('game_resolved', {
            'message': f'Game resolved! True values: {values_str}',
            'results': results
        })

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
