import pytest
from app import createApp
from extensions import db
from models import *
from datetime import datetime

#! To run:
#! export PYTHONPATH="/Users/arthur/Documents/digital-systems-project/Payment System Software"
#! PYTHONPATH="." pytest
#! Database is filled with dummy data for testing purposes

@pytest.fixture
def client():
    #Use in-memory database for testing
    app = createApp({
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'
    })
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            db.create_all()  #Create the database files for test
            #Adding dummy data and all valid rfid uid
            dummyData = [
            RFIDTags(rfid_uid=101),
            RFIDTags(rfid_uid=102),
            RFIDTags(rfid_uid=103),
            RFIDTags(rfid_uid=104),
            RFIDTags(rfid_uid=3855231550),
            RFIDTags(rfid_uid=3285310127),
            RFIDTags(rfid_uid=2317300995),
            RFIDTags(rfid_uid=3298572094),
            RFIDTags(rfid_uid=1986993982),
            RFIDTags(rfid_uid=2243372291),
            RFIDTags(rfid_uid=3976666627),
            RFIDTags(rfid_uid=2198675518),
            RFIDTags(rfid_uid=1651057411),
            RFIDTags(rfid_uid=3969513984),
            Purchase(rfid_uid=101, name="Apple", weight=1.2, cost=1.50, purchased_at=datetime(2024, 11, 18, 10, 30)),
            Purchase(rfid_uid=101, name="Banana", weight=1.1, cost=1.00, purchased_at=datetime(2024, 10, 10, 8, 00)),
            Purchase(rfid_uid=102, name="Orange", weight=1.3, cost=1.75, purchased_at=datetime(2024, 11, 18, 11, 00)),
            Purchase(rfid_uid=103, name="Milk", weight=2.0, cost=3.50, purchased_at=datetime(2024, 11, 18, 11, 15)),
            Purchase(rfid_uid=103, name="Bread", weight=0.5, cost=2.00, purchased_at=datetime(2024, 11, 18, 11, 20)),
            Purchase(rfid_uid=104, name="Eggs", weight=1.0, cost=2.50, purchased_at=datetime(2024, 11, 18, 12, 00)),
            DispenserDetails(id = 1, product_name = 'Washing Liquid', cost_per_gram = 1.1),
            DispenserDetails(id = 2, product_name = 'Penne Pasta', cost_per_gram = 0.5),
            DispenserDetails(id = 3, product_name = 'Vegetable Oil', cost_per_gram = 4),
            DispenserDetails(id = 4, product_name = 'Cornflakes', cost_per_gram = 0.6),
            Item(name='Small Glass Container', cost=2.50),
            Item(name='Med Glass Container', cost=3.99),
            Item(name='Large Glass Container', cost=5.00),
            Account(email='arthurmilner01@gmail.com', name="Arthur", rfid_uid=101, points=40, created_at=datetime(2024, 10, 17, 9, 00)),
            Employee(name='John', pin=2522945794),
            #! FOR TESTING RECEIPT ROUTE ONLY
            Account(email='arthur2.milner@live.uwe.ac.uk', name="Arthur", rfid_uid=103, points=40, created_at=datetime(2024, 10, 17, 9, 00)),
            Order(id=1, order_cost=15.00, points_used=0, checkout_session_id="N/A", order_refunded=False),
            ArchivedPurchase(rfid_uid=103, name="Shampoo", weight=2.0, cost=10.00, order_id=1),
            ArchivedPurchase(rfid_uid=103, name="Hand Soap", weight=1.0, cost=5.00, order_id=1),
            #! FOR TESTING GUEST RECEIPT AND REFUND ROUTES ONLY
            Order(id=2, order_cost=15.00, points_used=0, checkout_session_id="N/A", order_refunded=True),
            ArchivedPurchase(rfid_uid=104, name="Shampoo", weight=2.0, cost=10.00, order_id=2),
            ArchivedPurchase(rfid_uid=104, name="Hand Soap", weight=1.0, cost=5.00, order_id=2)
            ]
            db.session.bulk_save_objects(dummyData)
            db.session.commit()
            yield client
            db.drop_all() #Drop database after each test