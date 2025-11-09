// Socket.IO connection
const socket = io();

// Global state
let state = {
    userId: null,
    userName: null,
    userRole: null,
    cash: 0,
    positions: {},
    markets: [],
    orderBooks: {}
};

// DOM Elements
const loginScreen = document.getElementById('login-screen');
const gameScreen = document.getElementById('game-screen');
const usernameInput = document.getElementById('username-input');
const joinBtn = document.getElementById('join-btn');
const userInfo = document.getElementById('user-info');
const cashDisplay = document.getElementById('cash-display');
const marketsGrid = document.getElementById('markets-grid');
const adminControls = document.getElementById('admin-controls');
const positionsList = document.getElementById('positions-list');
const leaderboardBtn = document.getElementById('leaderboard-btn');
const leaderboardModal = document.getElementById('leaderboard-modal');
const leaderboardList = document.getElementById('leaderboard-list');
const resolutionModal = document.getElementById('resolution-modal');
const resolutionResults = document.getElementById('resolution-results');

// Event Listeners
joinBtn.addEventListener('click', handleJoin);
leaderboardBtn.addEventListener('click', showLeaderboard);

document.querySelector('.close').addEventListener('click', () => {
    leaderboardModal.classList.add('hidden');
});

document.querySelector('.close-resolution')?.addEventListener('click', () => {
    resolutionModal.classList.add('hidden');
});

// Admin controls
document.getElementById('update-config-btn')?.addEventListener('click', updateConfig);
document.getElementById('start-game-btn')?.addEventListener('click', startGame);
document.getElementById('end-game-btn')?.addEventListener('click', endGame);
document.getElementById('reset-game-btn')?.addEventListener('click', resetGame);
document.getElementById('resolve-game-btn')?.addEventListener('click', resolveGame);
document.getElementById('create-market-btn')?.addEventListener('click', createMarket);
document.getElementById('market-type')?.addEventListener('change', toggleBundleSection);

// Socket event handlers
socket.on('connected', (data) => {
    console.log('Connected to server');
});

socket.on('registered', (data) => {
    state.userId = data.user_id;
    state.userName = data.name;
    state.userRole = data.role;
    state.cash = data.cash;

    loginScreen.classList.add('hidden');
    gameScreen.classList.remove('hidden');

    userInfo.textContent = `${data.name} (${data.role})`;
    updateCashDisplay();

    if (data.role === 'ADMIN') {
        adminControls.classList.remove('hidden');
    }

    showNotification(`Welcome, ${data.name}!`, 'success');
});

socket.on('game_state', (data) => {
    state.markets = data.markets;

    // Update order books
    data.order_books.forEach(ob => {
        state.orderBooks[ob.market_id] = ob;
    });

    renderMarkets();
    if (state.userRole === 'ADMIN') {
        updateCreatedMarketsList();
        updateResolutionInputs();
        updateBundleMarketsSelector();
    }
});

socket.on('market_created', (data) => {
    showNotification(data.message, 'success');
    socket.emit('get_game_state');
});

socket.on('market_deleted', (data) => {
    showNotification(data.message, 'success');
    socket.emit('get_game_state');
});

socket.on('order_book_update', (data) => {
    state.orderBooks[data.market_id] = data;
    renderOrderBook(data.market_id);
});

socket.on('trade', (trade) => {
    showNotification(
        `Trade: ${trade.quantity} @ $${trade.price.toFixed(2)} in ${trade.market_id}`,
        'trade'
    );
});

socket.on('order_submitted', (data) => {
    showNotification(data.message, 'success');
});

socket.on('order_cancelled', (data) => {
    showNotification(data.message, 'success');
});

socket.on('position_update', (data) => {
    state.cash = data.cash;
    state.positions = data.positions;
    updateCashDisplay();
    updatePositions();
});

socket.on('game_started', (data) => {
    showNotification(data.message, 'success');
});

socket.on('game_ended', (data) => {
    showNotification(data.message, 'success');
    displayLeaderboard(data.leaderboard);
    leaderboardModal.classList.remove('hidden');
});

socket.on('game_resolved', (data) => {
    showNotification(data.message, 'success');
    displayResolutionResults(data.results);
    resolutionModal.classList.remove('hidden');
});

socket.on('game_reset', (data) => {
    showNotification(data.message, 'success');
    state.positions = {};
    updatePositions();
});

socket.on('error', (data) => {
    showNotification(data.message, 'error');
});

socket.on('leaderboard', (leaderboard) => {
    displayLeaderboard(leaderboard);
});

// Functions
function handleJoin() {
    const name = usernameInput.value.trim() || `Player_${Math.random().toString(36).substr(2, 6)}`;
    const role = document.querySelector('input[name="role"]:checked').value;

    socket.emit('register', { name, role });
}

function renderMarkets() {
    marketsGrid.innerHTML = '';

    state.markets.forEach(market => {
        const marketCard = createMarketCard(market);
        marketsGrid.appendChild(marketCard);
    });
}

function createMarketCard(market) {
    const card = document.createElement('div');
    card.className = 'market-card';
    card.id = `market-${market.id}`;

    card.innerHTML = `
        <h2>${market.name}</h2>
        <p>${market.description} | Position Limit: ±${market.position_limit}</p>

        <div class="order-book">
            <div class="bids">
                <h4>Bids</h4>
                <div id="bids-${market.id}"></div>
            </div>
            <div class="asks">
                <h4>Asks</h4>
                <div id="asks-${market.id}"></div>
            </div>
        </div>

        <div class="order-form">
            <h4>Place Order</h4>
            <div class="order-inputs">
                <input type="number" id="price-${market.id}" placeholder="Price" step="0.01" />
                <input type="number" id="quantity-${market.id}" placeholder="Quantity" step="1" />
            </div>
            <div class="order-buttons">
                <button class="btn btn-buy" onclick="submitOrder('${market.id}', 'BUY')">Buy</button>
                <button class="btn btn-sell" onclick="submitOrder('${market.id}', 'SELL')">Sell</button>
            </div>
        </div>
    `;

    // Render initial order book if available
    if (state.orderBooks[market.id]) {
        setTimeout(() => renderOrderBook(market.id), 100);
    }

    return card;
}

function renderOrderBook(marketId) {
    const orderBook = state.orderBooks[marketId];
    if (!orderBook) return;

    const bidsContainer = document.getElementById(`bids-${marketId}`);
    const asksContainer = document.getElementById(`asks-${marketId}`);

    if (!bidsContainer || !asksContainer) return;

    // Render bids
    bidsContainer.innerHTML = orderBook.bids.length > 0
        ? orderBook.bids.map(level => `
            <div class="order-level bid" onclick="hitOrder('${marketId}', 'SELL', ${level.price}, ${level.quantity})">
                <span>$${level.price.toFixed(2)}</span>
                <span>${level.quantity}</span>
            </div>
        `).join('')
        : '<p style="color: #999; font-size: 0.9rem;">No bids</p>';

    // Render asks
    asksContainer.innerHTML = orderBook.asks.length > 0
        ? orderBook.asks.map(level => `
            <div class="order-level ask" onclick="hitOrder('${marketId}', 'BUY', ${level.price}, ${level.quantity})">
                <span>$${level.price.toFixed(2)}</span>
                <span>${level.quantity}</span>
            </div>
        `).join('')
        : '<p style="color: #999; font-size: 0.9rem;">No asks</p>';
}

function submitOrder(marketId, side) {
    const priceInput = document.getElementById(`price-${marketId}`);
    const quantityInput = document.getElementById(`quantity-${marketId}`);

    const price = parseFloat(priceInput.value);
    const quantity = parseInt(quantityInput.value);

    if (!price || !quantity || price <= 0 || quantity <= 0) {
        showNotification('Please enter valid price and quantity', 'error');
        return;
    }

    socket.emit('submit_order', {
        market_id: marketId,
        side: side,
        price: price,
        quantity: quantity
    });

    // Clear inputs
    priceInput.value = '';
    quantityInput.value = '';
}

function hitOrder(marketId, side, price, maxQuantity) {
    const quantity = prompt(`How many units do you want to ${side.toLowerCase()}? (Max: ${maxQuantity})`, maxQuantity);

    if (quantity === null || quantity === '') return;

    const qty = parseInt(quantity);
    if (qty <= 0 || qty > maxQuantity) {
        showNotification('Invalid quantity', 'error');
        return;
    }

    socket.emit('submit_order', {
        market_id: marketId,
        side: side,
        price: price,
        quantity: qty
    });
}

function updateCashDisplay() {
    cashDisplay.textContent = `Cash: $${state.cash.toFixed(2)}`;
}

function updatePositions() {
    if (Object.keys(state.positions).length === 0) {
        positionsList.innerHTML = '<p style="color: #999;">No positions</p>';
        return;
    }

    positionsList.innerHTML = Object.entries(state.positions).map(([marketId, position]) => {
        const posClass = position.quantity > 0 ? 'positive' : position.quantity < 0 ? 'negative' : '';
        return `
            <div class="position-item ${posClass}">
                <span>${marketId}</span>
                <span>${position.quantity > 0 ? '+' : ''}${position.quantity}</span>
            </div>
        `;
    }).join('');
}

function showLeaderboard() {
    socket.emit('get_leaderboard');
    leaderboardModal.classList.remove('hidden');
}

function displayLeaderboard(leaderboard) {
    leaderboardList.innerHTML = leaderboard.map((player, index) => `
        <div class="leaderboard-item rank-${index + 1}">
            <div>
                <strong>#${index + 1} ${player.name}</strong>
            </div>
            <div>
                <span>Cash: $${player.cash.toFixed(2)}</span>
                <span style="margin-left: 1rem; font-weight: bold;">
                    P&L: $${player.total_pnl.toFixed(2)}
                </span>
            </div>
        </div>
    `).join('');
}

function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    document.getElementById('notifications').appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Admin functions
function updateConfig() {
    const startingCash = parseFloat(document.getElementById('starting-cash-input').value);

    socket.emit('admin_setup_game', {
        starting_cash: startingCash
    });
}

function startGame() {
    socket.emit('admin_start_game');
}

function endGame() {
    socket.emit('admin_end_game');
}

function resetGame() {
    if (confirm('Are you sure you want to reset the game? All positions will be cleared.')) {
        socket.emit('admin_reset_game');
    }
}

function resolveGame() {
    // Get all BASIC markets
    const basicMarkets = state.markets.filter(m => m.market_type === 'BASIC');

    if (basicMarkets.length === 0) {
        showNotification('No basic markets to resolve', 'error');
        return;
    }

    // Collect true values from inputs
    const trueValues = {};
    let allValid = true;
    let confirmMessage = 'Resolve game with:\n\n';

    for (const market of basicMarkets) {
        const input = document.getElementById(`resolve-${market.id}`);
        if (!input) continue;

        const value = parseFloat(input.value);
        if (!value || value <= 0) {
            showNotification(`Please enter a valid positive value for ${market.name}`, 'error');
            allValid = false;
            return;
        }

        trueValues[market.id] = value;
        confirmMessage += `${market.name}: $${value.toFixed(2)}\n`;
    }

    if (!allValid) return;

    confirmMessage += '\nThis will end the game and calculate final results.';

    if (confirm(confirmMessage)) {
        socket.emit('admin_resolve_game', {
            true_values: trueValues
        });

        // Clear inputs
        for (const market of basicMarkets) {
            const input = document.getElementById(`resolve-${market.id}`);
            if (input) input.value = '';
        }
    }
}

function displayResolutionResults(results) {
    const { true_values, leaderboard, settlements } = results;

    let html = `
        <div class="true-values">
            <h3>True Values</h3>
            <p>Market A: $${true_values.market_a.toFixed(2)} | Market B: $${true_values.market_b.toFixed(2)} | Market A+B: $${true_values.market_ab.toFixed(2)}</p>
        </div>

        <h3>Final Rankings</h3>
    `;

    // Sort settlements by total_pnl for ranking
    settlements.sort((a, b) => b.total_pnl - a.total_pnl);

    settlements.forEach((settlement, index) => {
        const isWinner = index === 0;
        const pnlClass = settlement.total_pnl >= 0 ? 'positive' : 'negative';
        const pnlSign = settlement.total_pnl >= 0 ? '+' : '';

        html += `
            <div class="settlement-item ${isWinner ? 'winner' : ''}">
                <h4>#${index + 1} ${settlement.name} ${isWinner ? '🏆' : ''}</h4>
                <div class="settlement-details">
                    <div class="detail-row">
                        <span class="detail-label">Starting Cash:</span>
                        <span class="detail-value">$${settlement.starting_cash.toFixed(2)}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Ending Cash:</span>
                        <span class="detail-value">$${settlement.ending_cash.toFixed(2)}</span>
                    </div>
        `;

        // Show positions
        if (Object.keys(settlement.positions).length > 0) {
            Object.entries(settlement.positions).forEach(([marketId, qty]) => {
                const value = settlement.position_values[marketId];
                html += `
                    <div class="detail-row">
                        <span class="detail-label">${marketId} Position:</span>
                        <span class="detail-value">${qty > 0 ? '+' : ''}${qty}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">${marketId} Value:</span>
                        <span class="detail-value ${value >= 0 ? 'positive' : 'negative'}">$${value.toFixed(2)}</span>
                    </div>
                `;
            });
        }

        html += `
                </div>
                <div class="final-pnl">
                    Total P&L: <span class="detail-value ${pnlClass}">${pnlSign}$${settlement.total_pnl.toFixed(2)}</span>
                </div>
            </div>
        `;
    });

    resolutionResults.innerHTML = html;
}

// Market Creation Functions

function toggleBundleSection() {
    const marketType = document.getElementById('market-type').value;
    const bundleSection = document.getElementById('bundle-formula-section');

    if (marketType === 'BUNDLE') {
        bundleSection.classList.remove('hidden');
        updateBundleMarketsSelector();
    } else {
        bundleSection.classList.add('hidden');
    }
}

function createMarket() {
    const marketId = document.getElementById('market-id').value.trim();
    const name = document.getElementById('market-name').value.trim();
    const description = document.getElementById('market-description').value.trim();
    const positionLimit = parseInt(document.getElementById('market-position-limit').value);
    const marketType = document.getElementById('market-type').value;

    if (!marketId || !name) {
        showNotification('Market ID and Name are required', 'error');
        return;
    }

    const marketData = {
        id: marketId,
        name: name,
        description: description,
        position_limit: positionLimit,
        market_type: marketType
    };

    if (marketType === 'BUNDLE') {
        const operation = document.getElementById('bundle-operation').value;
        const selectedMarkets = Array.from(document.querySelectorAll('#bundle-markets-selector input:checked'))
            .map(cb => cb.value);

        if (selectedMarkets.length < 2) {
            showNotification('Please select at least 2 markets for the bundle', 'error');
            return;
        }

        marketData.bundle_formula = {
            operation: operation,
            markets: selectedMarkets
        };
    }

    socket.emit('admin_create_market', marketData);

    // Clear form
    document.getElementById('market-id').value = '';
    document.getElementById('market-name').value = '';
    document.getElementById('market-description').value = '';
    document.getElementById('market-position-limit').value = '100';
}

function deleteMarket(marketId) {
    if (confirm('Are you sure you want to delete this market?')) {
        socket.emit('admin_delete_market', { market_id: marketId });
    }
}

function updateCreatedMarketsList() {
    const marketsList = document.getElementById('created-markets-list');
    const marketCount = document.getElementById('market-count');

    marketCount.textContent = state.markets.length;

    if (state.markets.length === 0) {
        marketsList.innerHTML = '<p style="color: #999; font-size: 0.9rem;">No markets created yet</p>';
        return;
    }

    marketsList.innerHTML = state.markets.map(market => {
        const isBundle = market.market_type === 'BUNDLE';
        let formulaText = '';

        if (isBundle && market.bundle_formula) {
            const op = market.bundle_formula.operation;
            const opSymbol = op === 'ADD' ? '+' : op === 'SUBTRACT' ? '-' : '×';
            const marketNames = market.bundle_formula.markets
                .map(mid => state.markets.find(m => m.id === mid)?.name || mid)
                .join(` ${opSymbol} `);
            formulaText = ` = ${marketNames}`;
        }

        return `
            <div class="created-market-item ${isBundle ? 'bundle' : ''}">
                <div class="market-info">
                    <h5>${market.name} ${isBundle ? '(Bundle)' : ''}</h5>
                    <p>${market.description}${formulaText}</p>
                    <p style="font-size: 0.8rem; margin-top: 0.25rem;">Position Limit: ±${market.position_limit}</p>
                </div>
                <div class="market-actions">
                    <button class="btn btn-danger" onclick="deleteMarket('${market.id}')">Delete</button>
                </div>
            </div>
        `;
    }).join('');
}

function updateResolutionInputs() {
    const resolutionInputs = document.getElementById('resolution-inputs');
    const basicMarkets = state.markets.filter(m => m.market_type === 'BASIC');

    if (basicMarkets.length === 0) {
        resolutionInputs.innerHTML = '<p style="color: #999;">No basic markets to resolve. Create basic markets first.</p>';
        return;
    }

    resolutionInputs.innerHTML = basicMarkets.map(market => `
        <input type="number"
               id="resolve-${market.id}"
               placeholder="True Value of ${market.name}"
               step="0.01" />
    `).join('');
}

function updateBundleMarketsSelector() {
    const selector = document.getElementById('bundle-markets-selector');
    const basicMarkets = state.markets.filter(m => m.market_type === 'BASIC');

    if (basicMarkets.length === 0) {
        selector.innerHTML = '<p style="color: #999; font-size: 0.9rem;">Create basic markets first</p>';
        return;
    }

    selector.innerHTML = basicMarkets.map(market => `
        <label class="bundle-markets-selector">
            <input type="checkbox" value="${market.id}" />
            ${market.name}
        </label>
    `).join('');
}

// Make functions global for onclick handlers
window.submitOrder = submitOrder;
window.hitOrder = hitOrder;
window.deleteMarket = deleteMarket;

// Request initial game state on load
socket.emit('get_game_state');
