from typing import List, Tuple, Optional
from collections import defaultdict
from datetime import datetime
import uuid
from models import Order, Trade, OrderSide, Market, Player

class OrderBook:
    def __init__(self, market: Market):
        self.market = market
        self.bids: List[Order] = []  # Buy orders, sorted high to low
        self.asks: List[Order] = []  # Sell orders, sorted low to high
        self.orders_by_id = {}  # Quick lookup

    def add_order(self, order: Order) -> List[Trade]:
        """Add order to book and attempt to match. Returns list of trades."""
        trades = []

        if order.side == OrderSide.BUY:
            trades = self._match_buy_order(order)
            if order.remaining_quantity > 0:
                self.bids.append(order)
                self.bids.sort(key=lambda x: (-x.price, x.timestamp))  # Price-time priority
                self.orders_by_id[order.id] = order
        else:  # SELL
            trades = self._match_sell_order(order)
            if order.remaining_quantity > 0:
                self.asks.append(order)
                self.asks.sort(key=lambda x: (x.price, x.timestamp))  # Price-time priority
                self.orders_by_id[order.id] = order

        return trades

    def _match_buy_order(self, buy_order: Order) -> List[Trade]:
        """Match a buy order against asks (sell orders)"""
        trades = []

        while buy_order.remaining_quantity > 0 and self.asks:
            best_ask = self.asks[0]

            # Check if prices cross
            if buy_order.price < best_ask.price:
                break

            # Execute trade at the resting order's price (best_ask.price)
            trade_quantity = min(buy_order.remaining_quantity, best_ask.remaining_quantity)
            trade_price = best_ask.price

            # Create trade
            trade = Trade(
                id=str(uuid.uuid4()),
                market_id=self.market.id,
                buyer_id=buy_order.user_id,
                seller_id=best_ask.user_id,
                price=trade_price,
                quantity=trade_quantity,
                timestamp=datetime.now()
            )
            trades.append(trade)

            # Update quantities
            buy_order.remaining_quantity -= trade_quantity
            best_ask.remaining_quantity -= trade_quantity

            # Remove filled order
            if best_ask.remaining_quantity == 0:
                self.asks.pop(0)
                del self.orders_by_id[best_ask.id]

        return trades

    def _match_sell_order(self, sell_order: Order) -> List[Trade]:
        """Match a sell order against bids (buy orders)"""
        trades = []

        while sell_order.remaining_quantity > 0 and self.bids:
            best_bid = self.bids[0]

            # Check if prices cross
            if sell_order.price > best_bid.price:
                break

            # Execute trade at the resting order's price (best_bid.price)
            trade_quantity = min(sell_order.remaining_quantity, best_bid.remaining_quantity)
            trade_price = best_bid.price

            # Create trade
            trade = Trade(
                id=str(uuid.uuid4()),
                market_id=self.market.id,
                buyer_id=best_bid.user_id,
                seller_id=sell_order.user_id,
                price=trade_price,
                quantity=trade_quantity,
                timestamp=datetime.now()
            )
            trades.append(trade)

            # Update quantities
            sell_order.remaining_quantity -= trade_quantity
            best_bid.remaining_quantity -= trade_quantity

            # Remove filled order
            if best_bid.remaining_quantity == 0:
                self.bids.pop(0)
                del self.orders_by_id[best_bid.id]

        return trades

    def cancel_order(self, order_id: str, user_id: str) -> bool:
        """Cancel an order. Returns True if successful."""
        if order_id not in self.orders_by_id:
            return False

        order = self.orders_by_id[order_id]

        # Only order owner can cancel (admins can cancel their own)
        if order.user_id != user_id:
            return False

        # Remove from book
        if order.side == OrderSide.BUY:
            self.bids = [o for o in self.bids if o.id != order_id]
        else:
            self.asks = [o for o in self.asks if o.id != order_id]

        del self.orders_by_id[order_id]
        return True

    def get_order_book_display(self, depth: int = 10) -> dict:
        """Get order book for display"""
        # Aggregate by price level
        bid_levels = defaultdict(int)
        ask_levels = defaultdict(int)

        for bid in self.bids:
            bid_levels[bid.price] += bid.remaining_quantity

        for ask in self.asks:
            ask_levels[ask.price] += ask.remaining_quantity

        # Convert to sorted lists
        bids_display = sorted(
            [{'price': price, 'quantity': qty} for price, qty in bid_levels.items()],
            key=lambda x: -x['price']
        )[:depth]

        asks_display = sorted(
            [{'price': price, 'quantity': qty} for price, qty in ask_levels.items()],
            key=lambda x: x['price']
        )[:depth]

        return {
            'market_id': self.market.id,
            'bids': bids_display,
            'asks': asks_display
        }

    def to_dict(self):
        """Full order book state"""
        return {
            'market_id': self.market.id,
            'bids': [order.to_dict() for order in self.bids],
            'asks': [order.to_dict() for order in self.asks]
        }


class MatchingEngine:
    def __init__(self):
        self.markets: dict[str, Market] = {}
        self.order_books: dict[str, OrderBook] = {}
        self.players: dict[str, Player] = {}
        self.trade_history: List[Trade] = []

    def add_market(self, market: Market):
        """Add a new market"""
        self.markets[market.id] = market
        self.order_books[market.id] = OrderBook(market)

    def add_player(self, player: Player):
        """Add a new player"""
        self.players[player.id] = player

    def submit_order(self, user_id: str, market_id: str, side: str,
                     price: float, quantity: int) -> Tuple[Order, List[Trade]]:
        """Submit an order to the matching engine"""
        if market_id not in self.order_books:
            raise ValueError(f"Market {market_id} does not exist")

        if user_id not in self.players:
            raise ValueError(f"Player {user_id} does not exist")

        player = self.players[user_id]
        market = self.markets[market_id]

        # Check position limits
        current_position = player.get_position(market_id).quantity
        side_enum = OrderSide[side]

        if side_enum == OrderSide.BUY:
            potential_position = current_position + quantity
        else:
            potential_position = current_position - quantity

        if abs(potential_position) > market.position_limit:
            raise ValueError(f"Order would exceed position limit of {market.position_limit}")

        # Create order
        order = Order(
            id=str(uuid.uuid4()),
            market_id=market_id,
            user_id=user_id,
            side=side_enum,
            price=price,
            quantity=quantity,
            remaining_quantity=quantity,
            timestamp=datetime.now(),
            is_admin=player.role.value == "ADMIN"
        )

        # Submit to order book
        trades = self.order_books[market_id].add_order(order)

        # Update player positions for all trades
        for trade in trades:
            buyer = self.players[trade.buyer_id]
            seller = self.players[trade.seller_id]

            buyer.update_position(market_id, trade.quantity, trade.price)
            seller.update_position(market_id, -trade.quantity, trade.price)

            self.trade_history.append(trade)

        return order, trades

    def cancel_order(self, user_id: str, market_id: str, order_id: str) -> bool:
        """Cancel an order"""
        if market_id not in self.order_books:
            return False

        return self.order_books[market_id].cancel_order(order_id, user_id)

    def get_all_order_books(self) -> List[dict]:
        """Get all order books for display"""
        return [ob.get_order_book_display() for ob in self.order_books.values()]

    def get_leaderboard(self, mark_prices: dict = None) -> List[dict]:
        """Calculate leaderboard based on total P&L

        Args:
            mark_prices: Optional dict of {market_id: price} for mark-to-market valuation
        """
        leaderboard = []

        for player in self.players.values():
            if player.role.value == "PLAYER":  # Exclude admin
                total_pnl = player.cash

                # Add unrealized P&L from positions if mark prices provided
                if mark_prices:
                    for market_id, position in player.positions.items():
                        if market_id in mark_prices:
                            # Unrealized P&L = position_quantity * mark_price
                            total_pnl += position.quantity * mark_prices[market_id]

                leaderboard.append({
                    'player_id': player.id,
                    'name': player.name,
                    'cash': player.cash,
                    'positions': {k: v.to_dict() for k, v in player.positions.items()},
                    'total_pnl': total_pnl
                })

        # Sort by total P&L descending
        leaderboard.sort(key=lambda x: x['total_pnl'], reverse=True)
        return leaderboard

    def resolve_game(self, true_value_a: float, true_value_b: float) -> dict:
        """Resolve the game with true values of A and B

        Args:
            true_value_a: The true/final value of asset A
            true_value_b: The true/final value of asset B

        Returns:
            Dictionary with final results including leaderboard and settlement details
        """
        # Calculate true value of A+B
        true_value_ab = true_value_a + true_value_b

        mark_prices = {
            'market_a': true_value_a,
            'market_b': true_value_b,
            'market_ab': true_value_ab
        }

        # Get final leaderboard with mark-to-market
        final_leaderboard = self.get_leaderboard(mark_prices)

        # Calculate settlement details for each player
        settlements = []
        for player in self.players.values():
            if player.role.value == "PLAYER":
                starting_cash = 10000  # This should come from game config
                settlement = {
                    'player_id': player.id,
                    'name': player.name,
                    'starting_cash': starting_cash,
                    'ending_cash': player.cash,
                    'positions': {},
                    'position_values': {},
                    'total_value': player.cash
                }

                # Calculate value of each position
                for market_id, position in player.positions.items():
                    if market_id in mark_prices:
                        position_value = position.quantity * mark_prices[market_id]
                        settlement['positions'][market_id] = position.quantity
                        settlement['position_values'][market_id] = position_value
                        settlement['total_value'] += position_value

                settlement['total_pnl'] = settlement['total_value'] - starting_cash
                settlements.append(settlement)

        return {
            'true_values': mark_prices,
            'leaderboard': final_leaderboard,
            'settlements': settlements
        }

    def reset_game(self, starting_cash: float):
        """Reset all player positions and cash"""
        for player in self.players.values():
            player.cash = starting_cash
            player.positions = {}

        # Clear all order books
        for market_id in self.markets:
            self.order_books[market_id] = OrderBook(self.markets[market_id])

        self.trade_history = []
