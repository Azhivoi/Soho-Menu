from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = FastAPI(title="SOHO API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
def get_db():
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL", "postgresql://soho:soho_secret@db:5432/soho"),
        cursor_factory=RealDictCursor
    )
    return conn

# Initialize database
@app.on_event("startup")
def startup():
    conn = get_db()
    cur = conn.cursor()
    
    # Create tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            category_id INTEGER REFERENCES categories(id),
            image_url TEXT,
            is_new BOOLEAN DEFAULT FALSE,
            is_hit BOOLEAN DEFAULT FALSE
        );
        
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            total DECIMAL(10,2) NOT NULL,
            status VARCHAR(50) DEFAULT 'new',
            customer_name VARCHAR(100),
            customer_phone VARCHAR(20),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS order_items (
            id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL,
            name VARCHAR(200) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            quantity INTEGER NOT NULL
        );
    """)
    
    # Insert default categories
    cur.execute("""
        INSERT INTO categories (name, slug) VALUES 
            ('Пицца', 'pizza'),
            ('Суши', 'sushi'),
            ('Бургеры', 'burgers'),
            ('Wok', 'wok'),
            ('Салаты', 'salads'),
            ('Суши Сеты', 'sushi-sets'),
            ('Напитки', 'drinks'),
            ('Соусы', 'sauces'),
            ('Фритюр', 'fry'),
            ('Драники', 'draniki')
        ON CONFLICT (slug) DO NOTHING;
    """)
    
    # Insert sample products if empty
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()['count'] == 0:
        cur.execute("""
            INSERT INTO products (name, description, price, category_id, is_hit) VALUES
                ('Пепперони', 'Пицца с пепперони и сыром', 22.00, 1, TRUE),
                ('Маргарита', 'Классическая пицца с томатами и моцареллой', 18.00, 1, FALSE),
                ('Филадельфия', 'Ролл с лососем и сливочным сыром', 17.00, 2, TRUE),
                ('Калифорния', 'Ролл с крабом и авокадо', 15.50, 2, FALSE),
                ('Чикен Бургер', 'Бургер с куриной котлетой', 18.50, 3, TRUE);
        """)
    
    conn.commit()
    cur.close()
    conn.close()

# Pydantic models
class Category(BaseModel):
    id: int
    name: str
    slug: str

class Product(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    category_id: int
    category_name: Optional[str]
    image_url: Optional[str]
    is_new: bool
    is_hit: bool

class OrderItem(BaseModel):
    product_id: int
    name: str
    price: float
    quantity: int

class OrderCreate(BaseModel):
    items: List[OrderItem]
    total: float
    customer_name: Optional[str] = ""
    customer_phone: Optional[str] = ""
    comment: Optional[str] = ""

class Order(BaseModel):
    id: int
    items: List[OrderItem]
    total: float
    status: str
    created_at: str

# Endpoints
@app.get("/")
def root():
    return {"status": "ok", "service": "SOHO API"}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/categories", response_model=List[Category])
def get_categories():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM categories ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/products", response_model=List[Product])
def get_products(category_id: Optional[int] = None, q: Optional[str] = None):
    conn = get_db()
    cur = conn.cursor()
    
    query = """
        SELECT p.*, c.name as category_name 
        FROM products p 
        JOIN categories c ON p.category_id = c.id 
        WHERE 1=1
    """
    params = []
    
    if category_id:
        query += " AND p.category_id = %s"
        params.append(category_id)
    
    if q:
        query += " AND (p.name ILIKE %s OR p.description ILIKE %s)"
        params.extend([f"%{q}%", f"%{q}%"])
    
    query += " ORDER BY p.is_hit DESC, p.is_new DESC, p.name"
    
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/products/{product_id}", response_model=Product)
def get_product(product_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, c.name as category_name 
        FROM products p 
        JOIN categories c ON p.category_id = c.id 
        WHERE p.id = %s
    """, (product_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return dict(row)

@app.post("/api/orders", response_model=Order)
def create_order(order: OrderCreate):
    conn = get_db()
    cur = conn.cursor()
    
    # Create order
    cur.execute(
        "INSERT INTO orders (total, status, customer_name, customer_phone, comment) VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at",
        (order.total, "new", order.customer_name, order.customer_phone, order.comment)
    )
    order_row = cur.fetchone()
    order_id = order_row['id']
    created_at = order_row['created_at']
    
    # Create order items
    for item in order.items:
        cur.execute(
            "INSERT INTO order_items (order_id, product_id, name, price, quantity) VALUES (%s, %s, %s, %s, %s)",
            (order_id, item.product_id, item.name, item.price, item.quantity)
        )
    
    conn.commit()
    cur.close()
    conn.close()
    
    return {
        "id": order_id,
        "items": order.items,
        "total": order.total,
        "status": "new",
        "created_at": str(created_at)
    }

@app.get("/api/orders", response_model=List[Order])
def get_orders():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
    orders = cur.fetchall()
    
    result = []
    for order in orders:
        cur.execute("SELECT product_id, name, price, quantity FROM order_items WHERE order_id = %s", (order['id'],))
        items = cur.fetchall()
        result.append({
            "id": order['id'],
            "items": [dict(row) for row in items],
            "total": float(order['total']),
            "status": order['status'],
            "created_at": str(order['created_at'])
        })
    
    cur.close()
    conn.close()
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
