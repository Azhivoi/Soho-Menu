# Delivery Configuration for SOHO Cafe

# Minimum order amount to place an order (BYN)
MIN_ORDER_AMOUNT=20

# Free delivery threshold (BYN) - orders below this pay delivery fee
FREE_DELIVERY_THRESHOLD=40

# Standard delivery fee when order is below free threshold (BYN)
STANDARD_DELIVERY_FEE=5

# Delivery zones configuration
# Format: ZONE_NAME|PRICE|MIN_ORDER|DESCRIPTION
DELIVERY_ZONES=[
  {
    "name": "Центр города",
    "price": 0,
    "min_order": 20,
    "time": "30-45 минут",
    "description": "Бесплатная доставка от 20 BYN"
  },
  {
    "name": "В пределах города",
    "price": 5,
    "min_order": 20,
    "time": "45-60 минут",
    "description": "При заказе от 40 BYN доставка бесплатно"
  },
  {
    "name": "Пригород",
    "price": 10,
    "min_order": 40,
    "time": "60-90 минут",
    "description": "При заказе от 60 BYN доставка бесплатно"
  }
]

# Pickup discount percentage
PICKUP_DISCOUNT=10

# Working hours
OPENING_HOUR=10
CLOSING_HOUR=22
LAST_ORDER_MINUTES_BEFORE_CLOSE=30
