from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker

# Database configuration
DATABASE_URI = "mysql+pymysql://root:0120@localhost:3306/cosmetics_db"
engine = create_engine(DATABASE_URI, pool_recycle=3600)
Session = scoped_session(sessionmaker(bind=engine))


def fetch_products(category=None, skin_type=None, hair_type=None, gender=None, price_min=None, price_max=None):
    """Fetch products from the database with optional filters including price range."""
    try:
        with Session() as session:
            query = "SELECT name, brand, price, description, skin_type, hair_type, ingredients FROM products WHERE 1=1"
            params = {}

            # Filter by category
            if category:
                query += " AND category = :category"
                params["category"] = category

            # Filter by skin_type
            if skin_type:
                query += " AND skin_type = :skin_type"
                params["skin_type"] = skin_type

            # Filter by hair_type
            if hair_type:
                query += " AND hair_type = :hair_type"
                params["hair_type"] = hair_type

            # Filter by gender
            if gender:
                query += " AND (gender = :gender OR gender = 'unisex')"
                params["gender"] = gender

            # Filter by price range (min and max)
            if price_min:
                query += " AND CAST(REGEXP_REPLACE(price, '[^0-9.]', '') AS DECIMAL) >= :price_min"
                params["price_min"] = price_min
            if price_max:
                query += " AND CAST(REGEXP_REPLACE(price, '[^0-9.]', '') AS DECIMAL) <= :price_max"
                params["price_max"] = price_max

            # Add LIMIT to get only the top 10 products
            query += " LIMIT 10"
            
            # Execute the query
            result = session.execute(text(query), params).fetchall()

            # Format and return the result
            return [
                {
                    "name": row.name,
                    "brand": row.brand,
                    "price": row.price,
                    "description": row.description,
                    "skin_type": row.skin_type,
                    "hair_type": row.hair_type,
                    "ingredients": row.ingredients
                }
                for row in result
            ]
    except Exception as e:
        print(f"Error fetching products: {e}")
        return []


def fetch_faq(question):
    """Fetch FAQ based on a partial match of the question."""
    try:
        with Session() as session:
            query = "SELECT answer FROM faq WHERE question LIKE :question"
            result = session.execute(text(query), {"question": f"%{question}%"}).fetchone()
            return result[0] if result else None
    except Exception as e:
        print(f"Error fetching FAQ: {e}")
        return None
