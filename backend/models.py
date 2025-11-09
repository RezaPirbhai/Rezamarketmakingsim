from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class UserRole(Enum):
    ADMIN = "ADMIN"
    PLAYER = "PLAYER"

class MarketType(Enum):
    BASIC = "BASIC"
    BUNDLE = "BUNDLE"

class BundleOperation(Enum):
    ADD = "ADD"
    SUBTRACT = "SUBTRACT"
    MULTIPLY = "MULTIPLY"

@dataclass
class Order:
    id: str
    market_id: str
    user_id: str
    side: OrderSide
    price: float
    quantity: int
    remaining_quantity: int
    timestamp: datetime
    is_admin: bool = False

    def __post_init__(self):
        if isinstance(self.side, str):
            self.side = OrderSide[self.side]

    def to_dict(self):
        return {
            'id': self.id,
            'market_id': self.market_id,
            'user_id': 'ADMIN' if self.is_admin else self.user_id,  # Hide admin identity
            'side': self.side.value,
            'price': self.price,
            'quantity': self.quantity,
            'remaining_quantity': self.remaining_quantity,
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class Trade:
    id: str
    market_id: str
    buyer_id: str
    seller_id: str
    price: float
    quantity: int
    timestamp: datetime

    def to_dict(self):
        return {
            'id': self.id,
            'market_id': self.market_id,
            'buyer_id': self.buyer_id,
            'seller_id': self.seller_id,
            'price': self.price,
            'quantity': self.quantity,
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class Position:
    market_id: str
    quantity: int = 0
    realized_pnl: float = 0.0

    def to_dict(self):
        return {
            'market_id': self.market_id,
            'quantity': self.quantity,
            'realized_pnl': self.realized_pnl
        }

@dataclass
class Player:
    id: str
    name: str
    role: UserRole
    cash: float
    positions: dict = field(default_factory=dict)  # market_id -> Position

    def __post_init__(self):
        if isinstance(self.role, str):
            self.role = UserRole[self.role]

    def get_position(self, market_id: str) -> Position:
        if market_id not in self.positions:
            self.positions[market_id] = Position(market_id=market_id)
        return self.positions[market_id]

    def update_position(self, market_id: str, quantity: int, price: float):
        """Update position and cash after a trade"""
        position = self.get_position(market_id)

        # Update position
        old_quantity = position.quantity
        position.quantity += quantity

        # Update cash (buying reduces cash, selling increases it)
        self.cash -= quantity * price

        # Update realized P&L if closing a position
        if old_quantity * position.quantity < 0:  # Position flip or close
            closed_quantity = min(abs(old_quantity), abs(quantity))
            # P&L calculation would need average cost basis tracking
            # For simplicity, we'll calculate it from trades

    def to_dict(self, include_positions=False):
        data = {
            'id': self.id,
            'name': self.name,
            'role': self.role.value,
            'cash': self.cash
        }
        if include_positions:
            data['positions'] = {k: v.to_dict() for k, v in self.positions.items()}
        return data

@dataclass
class Market:
    id: str
    name: str
    description: str
    position_limit: int
    market_type: str = "BASIC"  # BASIC or BUNDLE
    tick_size: float = 0.01
    # For bundle markets
    bundle_formula: Optional[dict] = None  # {"operation": "ADD", "markets": ["market_a", "market_b"]}

    def __post_init__(self):
        if isinstance(self.market_type, str):
            self.market_type = self.market_type
        if self.bundle_formula and isinstance(self.bundle_formula.get('operation'), str):
            # Keep as string for now
            pass

    def calculate_bundle_value(self, market_values: dict) -> Optional[float]:
        """Calculate the value of a bundle market based on component markets"""
        if self.market_type != "BUNDLE" or not self.bundle_formula:
            return None

        operation = self.bundle_formula.get('operation')
        markets = self.bundle_formula.get('markets', [])

        if not all(m in market_values for m in markets):
            return None

        values = [market_values[m] for m in markets]

        if operation == "ADD":
            return sum(values)
        elif operation == "SUBTRACT":
            # Subtract all subsequent values from the first
            result = values[0]
            for v in values[1:]:
                result -= v
            return result
        elif operation == "MULTIPLY":
            result = 1
            for v in values:
                result *= v
            return result

        return None

    def to_dict(self):
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'position_limit': self.position_limit,
            'market_type': self.market_type,
            'tick_size': self.tick_size
        }
        if self.bundle_formula:
            data['bundle_formula'] = self.bundle_formula
        return data
