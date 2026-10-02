from fastapi import APIRouter, Depends, Request, Response, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func
from pathlib import Path
import uuid, mimetypes
from app.db.session import get_db
from app.models.entities import User, Shop, Product, CartItem, Order, OrderItem, OrderEvent, Prescription
from app.schemas.api import LoginIn, UserOut, CartAdd, CheckoutIn, TransitionIn
from app.services.auth import authenticate, current_user, audit
from app.services.orders import transition, make_code
from app.integrations.providers import MockPaymentProvider, OCRProvider, StorageProvider
from app.core.security import set_session, clear_session, csrf_token, ensure_csrf
from app.core.config import get_settings

router=APIRouter(prefix="/api")

@router.get("/health")
def health(db:Session=Depends(get_db)):
    db.execute(select(1)); return {"success":True,"status":"ok","mode":"MOCK/DEVELOPMENT"}

@router.get("/csrf")
def get_csrf(response:Response):
    t=csrf_token(); response.set_cookie("nova_csrf",t,httponly=False,secure=get_settings().env=="production",samesite="lax",path="/"); return {"csrfToken":t}

@router.post("/auth/login")
def login(payload:LoginIn,response:Response,request:Request,db:Session=Depends(get_db)):
    ensure_csrf(request)
    result=authenticate(db,payload.phone,payload.password)
    if not result: raise HTTPException(401,detail={"code":"INVALID_CREDENTIALS","message":"Invalid login details"})
    user,token=result; set_session(response,token); audit(db,user.id,"LOGIN_SUCCESS","User authenticated",request.client.host if request.client else "unknown")
    return {"success":True,"user":UserOut.model_validate(user,from_attributes=True).model_dump()}

@router.post("/auth/logout")
def logout(response:Response, request:Request, db:Session=Depends(get_db)):
    ensure_csrf(request); u=current_user(db,request.cookies.get("nova_session")); clear_session(response)
    if u: audit(db,u.id,"LOGOUT","User logged out",request.client.host if request.client else "unknown")
    return {"success":True}

@router.get("/me")
def me(request:Request,db:Session=Depends(get_db)):
    u=current_user(db,request.cookies.get("nova_session"));
    if not u: raise HTTPException(401,detail={"code":"AUTH_REQUIRED","message":"Please sign in"})
    return UserOut.model_validate(u,from_attributes=True)

@router.get("/catalog")
def catalog(q:str="", category:str="", db:Session=Depends(get_db)):
    stmt=select(Product).where(Product.active==True)
    if q: stmt=stmt.where(or_(Product.name.ilike(f"%{q}%"),Product.description.ilike(f"%{q}%")))
    if category: stmt=stmt.where(Product.category==category)
    products=db.scalars(stmt.order_by(Product.name)).all()
    shops={s.id:s for s in db.scalars(select(Shop)).all()}
    return [{**{k:getattr(p,k) for k in ["id","shop_id","name","category","description","price_paise","stock","prescription_required","image_url"]},"shop_name":shops.get(p.shop_id).name if shops.get(p.shop_id) else "Unknown","shop_rating":shops.get(p.shop_id).rating if shops.get(p.shop_id) else 0} for p in products]

@router.get("/shops")
def shops(db:Session=Depends(get_db)):
    return db.scalars(select(Shop).order_by(Shop.rating.desc())).all()

@router.get("/cart")
def cart(request:Request,db:Session=Depends(get_db)):
    u=current_user(db,request.cookies.get("nova_session"))
    if not u: return {"items":[],"total_paise":0}
    rows=db.scalars(select(CartItem).where(CartItem.user_id==u.id)).all(); data=[]; total=0
    for row in rows:
        p=db.get(Product,row.product_id)
        if not p: continue
        line=p.price_paise*row.quantity; total += line
        data.append({"id":row.id,"product_id":p.id,"name":p.name,"price_paise":p.price_paise,"quantity":row.quantity,"stock":p.stock,"prescription_required":p.prescription_required})
    return {"items":data,"total_paise":total}

@router.post("/cart")
def add_cart(payload:CartAdd,request:Request,db:Session=Depends(get_db)):
    ensure_csrf(request); u=current_user(db,request.cookies.get("nova_session"))
    if not u: raise HTTPException(401,detail={"code":"AUTH_REQUIRED","message":"Sign in to use cart"})
    p=db.get(Product,payload.product_id)
    if not p or not p.active: raise HTTPException(404,detail={"code":"PRODUCT_NOT_FOUND","message":"Product unavailable"})
    if payload.quantity>p.stock: raise HTTPException(409,detail={"code":"INSUFFICIENT_STOCK","message":"Not enough stock"})
    row=db.scalar(select(CartItem).where(CartItem.user_id==u.id,CartItem.product_id==p.id))
    if row: row.quantity=min(p.stock,row.quantity+payload.quantity)
    else: db.add(CartItem(user_id=u.id,product_id=p.id,quantity=payload.quantity))
    db.commit(); return cart(request,db)

@router.delete("/cart/{product_id}")
def remove_cart(product_id:int,request:Request,db:Session=Depends(get_db)):
    ensure_csrf(request); u=current_user(db,request.cookies.get("nova_session"));
    if not u: raise HTTPException(401,detail={"code":"AUTH_REQUIRED","message":"Sign in"})
    row=db.scalar(select(CartItem).where(CartItem.user_id==u.id,CartItem.product_id==product_id))
    if row: db.delete(row); db.commit()
    return cart(request,db)

@router.post("/checkout")
def checkout(payload:CheckoutIn,request:Request,db:Session=Depends(get_db)):
    ensure_csrf(request); u=current_user(db,request.cookies.get("nova_session"));
    if not u: raise HTTPException(401,detail={"code":"AUTH_REQUIRED","message":"Sign in to checkout"})
    items=db.scalars(select(CartItem).where(CartItem.user_id==u.id)).all()
    if not items: raise HTTPException(400,detail={"code":"CART_EMPTY","message":"Cart is empty"})
    products=[db.get(Product,i.product_id) for i in items]
    shop_ids={p.shop_id for p in products if p};
    if len(shop_ids)!=1: raise HTTPException(409,detail={"code":"ONE_SHOP_PER_ORDER","message":"This demo checkout groups one shop per order"})
    subtotal=0
    for row,p in zip(items,products):
        if not p or not p.active or p.stock<row.quantity: raise HTTPException(409,detail={"code":"STOCK_CHANGED","message":f"{p.name if p else 'Item'} is no longer available in that quantity"})
        subtotal += p.price_paise*row.quantity
    order=Order(order_code=make_code(),customer_id=u.id,shop_id=next(iter(shop_ids)),status="CREATED",subtotal_paise=subtotal,delivery_fee_paise=4900 if subtotal<49900 else 0,total_paise=subtotal+(4900 if subtotal<49900 else 0),payment_status="PENDING",customer_address=payload.address)
    db.add(order); db.flush()
    for row,p in zip(items,products):
        p.stock -= row.quantity
        db.add(OrderItem(order_id=order.id,product_id=p.id,name_snapshot=p.name,unit_price_paise=p.price_paise,quantity=row.quantity))
        db.delete(row)
    db.add(OrderEvent(order_id=order.id,actor_id=u.id,previous_status=None,new_status="CREATED"))
    if payload.payment_method=="MOCK_UPI":
        pay=MockPaymentProvider().create_intent(order.total_paise,order.order_code); order.payment_provider_ref=pay["reference"]; order.payment_status="CONFIRMED"; order.status="PAYMENT_CONFIRMED"; db.add(OrderEvent(order_id=order.id,actor_id=u.id,previous_status="CREATED",new_status="PAYMENT_CONFIRMED"))
    else:
        order.status="PAYMENT_PENDING"; db.add(OrderEvent(order_id=order.id,actor_id=u.id,previous_status="CREATED",new_status="PAYMENT_PENDING"))
    db.commit(); db.refresh(order)
    return {"success":True,"order":order_payload(db,order)}

def order_payload(db,o, viewer_role: str | None = None):
    payload={"id":o.id,"order_code":o.order_code,"status":o.status,"subtotal_paise":o.subtotal_paise,"delivery_fee_paise":o.delivery_fee_paise,"total_paise":o.total_paise,"payment_status":o.payment_status,"shop":db.get(Shop,o.shop_id).name if db.get(Shop,o.shop_id) else "","created_at":o.created_at.isoformat()}
    if viewer_role in {"CUSTOMER","DELIVERY_PARTNER","ADMIN","SUPER_ADMIN"}: payload["address"]=o.customer_address
    return payload

@router.get("/orders")
def orders(request:Request,db:Session=Depends(get_db)):
    u=current_user(db,request.cookies.get("nova_session"));
    if not u: raise HTTPException(401,detail={"code":"AUTH_REQUIRED","message":"Sign in"})
    stmt=select(Order).order_by(Order.created_at.desc())
    if u.role=="CUSTOMER": stmt=stmt.where(Order.customer_id==u.id)
    elif u.role=="DEALER": stmt=stmt.where(Order.shop_id.in_(select(Shop.id).where(Shop.dealer_id==u.id)))
    elif u.role=="DELIVERY_PARTNER": stmt=stmt.where(Order.delivery_partner_id==u.id)
    return [order_payload(db,o,u.role) for o in db.scalars(stmt).all()]

@router.post("/orders/{order_id}/transition")
def change_order(order_id:int,payload:TransitionIn,request:Request,db:Session=Depends(get_db)):
    ensure_csrf(request); u=current_user(db,request.cookies.get("nova_session"));
    if not u: raise HTTPException(401,detail={"code":"AUTH_REQUIRED","message":"Sign in"})
    o=db.get(Order,order_id)
    if not o: raise HTTPException(404,detail={"code":"ORDER_NOT_FOUND","message":"Order not found"})
    if u.role=="CUSTOMER" and o.customer_id!=u.id: raise HTTPException(403,detail={"code":"FORBIDDEN","message":"Not your order"})
    if u.role=="DEALER":
        allowed=db.scalar(select(Shop).where(Shop.id==o.shop_id,Shop.dealer_id==u.id))
        if not allowed: raise HTTPException(403,detail={"code":"FORBIDDEN","message":"Not your shop order"})
    if u.role=="DELIVERY_PARTNER" and o.delivery_partner_id!=u.id: raise HTTPException(403,detail={"code":"FORBIDDEN","message":"Not your delivery"})
    allowed_by_role={
        "CUSTOMER": {"CANCELLED"},
        "DEALER": {"SHOP_SELECTION","SHOP_ACCEPTED","PREPARING","READY_FOR_PICKUP","DELIVERY_ASSIGNMENT"},
        "DELIVERY_PARTNER": {"PICKED_UP","OUT_FOR_DELIVERY","DELIVERED"},
        "ADMIN": set(),
        "SUPER_ADMIN": set(),
    }
    if u.role in {"CUSTOMER","DEALER","DELIVERY_PARTNER"} and payload.status not in allowed_by_role[u.role]:
        raise HTTPException(403,detail={"code":"ROLE_TRANSITION_FORBIDDEN","message":"Your role cannot perform this transition"})
    transition(db,o,u.id,payload.status)
    return order_payload(db,o,u.role)

@router.post("/prescriptions/{order_id}")
def upload_prescription(order_id:int,request:Request,file:UploadFile=File(...),db:Session=Depends(get_db)):
    ensure_csrf(request); u=current_user(db,request.cookies.get("nova_session"));
    if not u: raise HTTPException(401,detail={"code":"AUTH_REQUIRED","message":"Sign in"})
    o=db.get(Order,order_id)
    if not o or o.customer_id!=u.id: raise HTTPException(404,detail={"code":"ORDER_NOT_FOUND","message":"Order not found"})
    allowed={"application/pdf","image/jpeg","image/png"}; name=Path(file.filename or "upload").name
    if file.content_type not in allowed or not StorageProvider().validate_filename(name): raise HTTPException(400,detail={"code":"UNSAFE_FILE","message":"Only PDF/JPG/PNG files are accepted"})
    data=file.file.read()
    if len(data)>get_settings().max_upload_bytes: raise HTTPException(413,detail={"code":"FILE_TOO_LARGE","message":"File is too large"})
    root=Path(get_settings().upload_dir); root.mkdir(parents=True,exist_ok=True); key=f"{uuid.uuid4().hex}_{name}"; (root/key).write_bytes(data)
    p=Prescription(order_id=o.id,customer_id=u.id,storage_key=key,status="PENDING_REVIEW",ocr_status=OCRProvider().extract(key)["status"]); db.add(p); db.commit()
    return {"success":True,"prescription_id":p.id,"status":p.status,"ocr_status":p.ocr_status,"mode":"MOCK/DEVELOPMENT"}

@router.post("/admin/orders/{order_id}/assign/{delivery_partner_id}")
def assign_delivery(order_id:int, delivery_partner_id:int, request:Request, db:Session=Depends(get_db)):
    ensure_csrf(request); u=current_user(db,request.cookies.get("nova_session"))
    if not u or u.role not in {"ADMIN","SUPER_ADMIN"}: raise HTTPException(403,detail={"code":"FORBIDDEN","message":"Admin only"})
    o=db.get(Order,order_id); partner=db.get(User,delivery_partner_id)
    if not o or not partner or partner.role!="DELIVERY_PARTNER" or not partner.active: raise HTTPException(404,detail={"code":"DELIVERY_PARTNER_NOT_FOUND","message":"Delivery partner not found"})
    if o.status!="DELIVERY_ASSIGNMENT": raise HTTPException(409,detail={"code":"ORDER_NOT_READY","message":"Order is not awaiting delivery assignment"})
    o.delivery_partner_id=partner.id
    transition(db,o,u.id,"DELIVERY_ASSIGNED")
    return order_payload(db,o,"ADMIN")

@router.get("/admin/overview")
def admin_overview(request:Request,db:Session=Depends(get_db)):
    u=current_user(db,request.cookies.get("nova_session"));
    if not u or u.role not in {"ADMIN","SUPER_ADMIN"}: raise HTTPException(403,detail={"code":"FORBIDDEN","message":"Admin only"})
    return {"users":db.scalar(select(func.count(User.id))),"orders":db.scalar(select(func.count(Order.id))),"products":db.scalar(select(func.count(Product.id))),"prescriptions_pending":db.scalar(select(func.count(Prescription.id)).where(Prescription.status=="PENDING_REVIEW"))}
