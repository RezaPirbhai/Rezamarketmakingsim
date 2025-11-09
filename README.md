# Market Making Simulator

A real-time multiplayer trading simulation where players can trade in three interconnected markets (A, B, and A+B bundle) with arbitrage opportunities. Built with Flask, Socket.IO, and vanilla JavaScript.

## Features

- **Real-time order matching** with price-time priority
- **Partial fills** supported
- **Three interconnected markets** (A, B, A+B) creating arbitrage opportunities
- **Admin controls** for game management
- **Live leaderboard** tracking player P&L
- **Position limits** to manage risk
- **Anonymous admin orders** to create market dynamics

## Tech Stack

**Backend:**
- Python 3.9+
- Flask + Flask-SocketIO
- Eventlet for WebSocket support

**Frontend:**
- Vanilla JavaScript
- Socket.IO client
- CSS3 for styling

## Local Development

### Prerequisites
- Python 3.9 or higher
- pip

### Setup

1. **Clone the repository**
   ```bash
   cd ~/MarketMakingSim
   ```

2. **Install Python dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Run the server**
   ```bash
   python app.py
   ```

4. **Open in browser**
   Navigate to `http://localhost:5000`

## How to Play

### For Players:

1. **Join the game** by entering your name and selecting "Player" role
2. **View the three markets**: Size of A, Size of B, and Size of A+B
3. **Place orders** by:
   - Clicking on existing orders to "hit" them (instant execution)
   - Or entering price/quantity and clicking Buy/Sell to create new orders
4. **Monitor your positions** in the positions panel
5. **Track your P&L** via the leaderboard

### For Admin:

1. **Join as admin** by selecting "Admin" role
2. **Configure game settings**:
   - Set starting cash
   - Adjust position limits per market
3. **Control game flow**:
   - Start Game: Allow trading to begin
   - End Game: Stop trading and display final leaderboard
   - Reset Game: Clear all positions and restart
4. **Place anonymous orders** to create market dynamics

### Trading Tips:

- Look for **arbitrage opportunities** between the A, B, and A+B markets
- Watch your **position limits** (default: ±100 per market)
- **Partial fills** are allowed - you don't have to fill entire orders
- Admin orders are **anonymous** - they appear like any other order

## Deployment to Render.com

### Step 1: Prepare for Deployment

Create a `render.yaml` file in the root directory (already configured):

```yaml
services:
  - type: web
    name: market-making-sim
    env: python
    buildCommand: pip install -r backend/requirements.txt
    startCommand: cd backend && python app.py
    envVars:
      - key: PORT
        value: 10000
```

### Step 2: Push to GitHub

```bash
cd ~/MarketMakingSim
git add .
git commit -m "Initial commit: Market Making Simulator"
git push origin main
```

### Step 3: Deploy on Render.com

1. Go to [render.com](https://render.com) and sign up/login
2. Click "New +" and select "Web Service"
3. Connect your GitHub repository
4. Render will auto-detect the `render.yaml` configuration
5. Click "Create Web Service"
6. Wait for deployment (2-3 minutes)
7. Access your app at: `https://your-app-name.onrender.com`

### Environment Variables (Optional)

You can set these in the Render dashboard:
- `PORT`: Auto-set by Render (usually 10000)
- `SECRET_KEY`: Set a secure secret key for Flask sessions

## Game Mechanics

### Order Matching

- **Price-Time Priority**: Best price first, then earliest timestamp
- **Partial Fills**: Orders can be partially filled
- **Market Orders**: Click existing orders to "hit" them at their price
- **Limit Orders**: Place orders at specific prices

### Position Management

- Each market has a position limit (default: ±100)
- Players cannot exceed these limits
- Cash is updated in real-time with each trade

### Leaderboard

- Calculated based on total P&L (cash + unrealized gains/losses)
- Updated in real-time
- Displayed at game end

## Architecture

```
MarketMakingSim/
├── backend/
│   ├── app.py              # Flask + SocketIO server
│   ├── matching_engine.py  # Order matching logic
│   ├── models.py           # Data models
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── index.html          # Main HTML
│   ├── app.js             # Socket.IO client & logic
│   └── styles.css         # Styling
└── README.md
```

## API Events (Socket.IO)

### Client → Server

- `register`: Join game with name and role
- `submit_order`: Place a new order
- `cancel_order`: Cancel an existing order
- `get_leaderboard`: Request current leaderboard
- `admin_setup_game`: Configure game settings (admin only)
- `admin_start_game`: Start the game (admin only)
- `admin_end_game`: End the game (admin only)
- `admin_reset_game`: Reset all positions (admin only)

### Server → Client

- `registered`: Confirmation of registration
- `game_state`: Full game state
- `order_book_update`: Updated order book for a market
- `trade`: Trade execution notification
- `position_update`: Player position update
- `leaderboard`: Leaderboard data
- `game_started`: Game start notification
- `game_ended`: Game end notification with final leaderboard
- `error`: Error messages

## Future Enhancements

- [ ] Add mark-to-market P&L calculation
- [ ] Implement order history
- [ ] Add market data visualization (charts)
- [ ] Support for market orders vs limit orders
- [ ] Time-based rounds with automatic end
- [ ] Historical trade data export
- [ ] Mobile responsive design improvements

## License

MIT License - feel free to use and modify!

## Contributing

Pull requests welcome! Please feel free to contribute.

## Support

For issues or questions, open an issue on GitHub.
