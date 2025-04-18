from extensions import db
from sqlalchemy.sql import func
from sqlalchemy import Boolean

#Store valid RFID UIDs
class RFIDTags(db.Model):
    __tablename__='rfidtags'
    rfid_uid = db.Column(db.Integer, primary_key=True)

#Product table
class Purchase(db.Model):
    __tablename__ = 'purchase'

    id = db.Column(db.Integer, primary_key=True)
    rfid_uid = db.Column(db.Integer, db.ForeignKey('rfidtags.rfid_uid'), unique=False, nullable=False)
    name = db.Column(db.String(80), unique=False, nullable=False)
    weight = db.Column(db.Float, unique=False, nullable=False)
    cost = db.Column(db.Float, unique=False, nullable=False)
    purchased_at = db.Column(db.DateTime, nullable=False)
    
#Archived purchases
class ArchivedPurchase(db.Model):
    __tablename__ = 'archived_purchases'

    id = db.Column(db.Integer, primary_key=True)
    rfid_uid = db.Column(db.Integer, db.ForeignKey('rfidtags.rfid_uid'), unique=False, nullable=False)
    name = db.Column(db.String(80), unique=False, nullable=False)
    weight = db.Column(db.Float, unique=False, nullable=False)
    cost = db.Column(db.Float, unique=False, nullable=False)
    archived_at = db.Column(db.DateTime, default=func.now(), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), unique=False, nullable=False)

#Orders
class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_cost = db.Column(db.Float, unique=False, nullable=False)
    points_used = db.Column(db.Integer, unique=False, nullable=False)
    checkout_session_id = db.Column(db.String(500), unique=False, nullable=False)
    order_refunded = db.Column(db.Boolean, unique=False, nullable=False)
    archived_purchases = db.relationship('ArchivedPurchase', backref='order', lazy=True)

#For list of items store sells
class Item(db.Model):
    __tablename__ = 'item'

    name = db.Column(db.String(80), primary_key=True, nullable=False)
    cost = db.Column(db.Float, unique=False, nullable=False)

#For user accounts
class Account(db.Model):
    __tablename__='account'

    email = db.Column(db.String(80), unique=True, nullable=False, primary_key=True)
    name=db.Column(db.String(80), unique=False, nullable=False)
    rfid_uid = db.Column(db.Integer, db.ForeignKey('rfidtags.rfid_uid'), unique=True, nullable=False)
    points = db.Column(db.Integer, unique=False, nullable=False)
    created_at = db.Column(db.DateTime, default=func.now(), nullable=False)

#For employee verification
class Employee(db.Model):
    __tablename__='employee'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=False, nullable=False)
    pin = db.Column(db.Integer, unique=False, nullable=False)

#For MQTT to retrieve the dispensers product name and cost per gram
class DispenserDetails(db.Model):
    __tablename__='dispenser_details'
    id = db.Column(db.Integer, primary_key=True) #This will be the dispenser number
    product_name = db.Column(db.String(100), unique=False, nullable=False) #Product name for the dispenser
    cost_per_gram = db.Column(db.Float, unique=False, nullable=False) #Cost per gram for the dispenser in pennies
