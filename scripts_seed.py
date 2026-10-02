from app.db.session import SessionLocal, Base, engine
from app.models.entities import User, Shop, Product
from app.core.security import hash_password

Base.metadata.create_all(bind=engine)
db=SessionLocal()
try:
    if not db.query(User).count():
        users=[
            User(name="Demo Customer",phone="9000000001",role="CUSTOMER",password_hash=hash_password("customer123")),
            User(name="Demo Dealer",phone="9000000002",role="DEALER",password_hash=hash_password("dealer123")),
            User(name="Demo Delivery",phone="9000000003",role="DELIVERY_PARTNER",password_hash=hash_password("delivery123")),
            User(name="Demo Admin",phone="9000000004",role="ADMIN",password_hash=hash_password("admin123")),
        ]
        db.add_all(users); db.flush()
        shops=[Shop(name="Nova Medical Hub",category="Medical",address="Main Road, Vijayawada",rating=4.8,dealer_id=users[1].id),Shop(name="Fresh Basket",category="Grocery",address="Market Street, Vijayawada",rating=4.6)]
        db.add_all(shops); db.flush()
        db.add_all([
            Product(shop_id=shops[0].id,name="Vitamin C 500mg",category="Medical",description="Demo OTC product",price_paise=12900,stock=40,prescription_required=False,image_url="/placeholder.svg"),
            Product(shop_id=shops[0].id,name="Allergy Relief Tablets",category="Medical",description="Prescription workflow demo",price_paise=21900,stock=18,prescription_required=True,image_url="/placeholder.svg"),
            Product(shop_id=shops[1].id,name="Basmati Rice 5kg",category="Grocery",description="Premium rice",price_paise=69900,stock=22,image_url="/placeholder.svg"),
            Product(shop_id=shops[1].id,name="Fresh Milk 1L",category="Milk Products",description="Daily essentials",price_paise=6800,stock=50,image_url="/placeholder.svg"),
            Product(shop_id=shops[1].id,name="Notebook A5",category="Stationery",description="Ruled notebook",price_paise=4500,stock=70,image_url="/placeholder.svg"),
        ]); db.commit()
    print("Seed complete")
finally: db.close()
