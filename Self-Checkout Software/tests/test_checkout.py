import pytest
import json
from extensions import db
from models import *
from datetime import datetime

#Testing remove purchase on checkout
@pytest.mark.parametrize(
    "purchaseID, expectedSuccess",
    [
        (1, True), #Valid purchase ID
        (10000000, False), #Invalid purchase ID
        ("testrfid", False) #String rfid
    ]
)
def test_valid_remove_purchase(client, purchaseID, expectedSuccess):
    #Calling remove_purchase route with POST with purchase ID
    response = client.post('checkout/remove_purchase', 
                           data=json.dumps({'id': purchaseID}),
                           content_type='application/json')

    #Checking response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] == expectedSuccess

    #Check purchase has been removed if success
    if expectedSuccess:
        removedPurchase = Purchase.query.get(purchaseID)
        assert removedPurchase is None


#Testing add item on checkout
@pytest.mark.parametrize(
    "rfidUID, itemName, itemCost, expectedSuccess",
    [
        (101, "Banana", 9.99, True), #Valid item add
        (101, "Small Glass Container", "StringCost", False), #Invalid string cost
        (10000000, "Small Glass Container", 12.50, False), #Invalid rfid UID
        (101, 12.50, 12.50, False), #Invalid float name
        (101, "Medium Glass Container", -10.50, False) #Invalid negative cost
    ]
)
def test_add_item(client, rfidUID, itemName, itemCost, expectedSuccess):
    #Sending post request to add_item endpoint
    purchasedAt = datetime.now().isoformat()
    response = client.post(
        "checkout/add_item",
        json={
            "rfid_uid": rfidUID,
            "name": itemName,
            "cost": itemCost,
            "purchased_at": purchasedAt
        },
    )

    data = response.get_json()

    #For success pass/fail and database fail
    assert response.status_code in (200, 500)
    assert data["success"] == expectedSuccess

    #If valid ensure correct details are returned
    if expectedSuccess:
        assert "purchase_id" in data
        assert "totalCost" in data
        expectedDateFormat = datetime.fromisoformat(purchasedAt).strftime('%d-%m-%Y %H:%M:%S')
        assert data["formattedDate"] == expectedDateFormat
        #Check item has been added and verify details are correct
        addItem = db.session.query(Purchase).filter_by(id=data["purchase_id"]).first()
        assert addItem is not None
        assert addItem.rfid_uid == rfidUID
        assert addItem.name == itemName
        assert addItem.cost == itemCost
    else: #If invalid only message should be returned
        assert "purchase_id" not in data
        assert "totalCost" not in data


#Testing add custom dispense on checkout
@pytest.mark.parametrize(
    "rfidUID, itemName, itemWeight, itemCost, expectedSuccess",
    [
        (101, "Banana", 12.5, 9.99, True), #Valid dispense add
        (101, "Small Glass Container", "StringWeight", 12.50, False), #Invalid string weight
        (101, "Small Glass Container", 12.5, "StringCost", False), #Invalid string cost
        (10000000, "Small Glass Container", 10.50, 12.50, False), #Invalid rfid UID
        (101, 12.50, 12.50, 9.99, False), #Invalid float name
        (101, "Medium Glass Container", 10, -10.50, False), #Invalid negative cost
        (101, "Medium Glass Container", -10, 10.50, False) #Invalid negative weight
    ]
)
def test_add_custom_dispense(client, rfidUID, itemName, itemWeight, itemCost, expectedSuccess):
    #Sending post request to add_dispense endpoint
    purchasedAt = datetime.now().isoformat()
    response = client.post(
        "checkout/add_dispense",
        json={
            "rfid_uid": rfidUID,
            "name": itemName,
            "weight": itemWeight,
            "cost": itemCost,
            "purchased_at": purchasedAt
        },
    )

    data = response.get_json()
    #For success pass/fail and database fail
    assert response.status_code in (200, 500)
    assert data["success"] == expectedSuccess
    
    if expectedSuccess:
        #Checking all response details are returned
        assert "purchase_id" in data
        assert "totalCost" in data
        assert "pin_url" in data
        assert "remove_url" in data
        expectedDateFormat = datetime.fromisoformat(purchasedAt).strftime('%d-%m-%Y %H:%M:%S')
        assert data["formattedDate"] == expectedDateFormat
        #Check dispense has been added and verify details are correct
        addDispense = db.session.query(Purchase).filter_by(id=data["purchase_id"]).first()
        assert addDispense is not None
        assert addDispense.rfid_uid == rfidUID
        assert addDispense.name == itemName
        assert addDispense.weight == itemWeight
        assert addDispense.cost == itemCost
    else: #Check redundant data not in fail response
        assert "rfid_uid" not in data
        assert "purchase_id" not in data
        assert "totalCost" not in data
        assert "pin_url" not in data
        assert "remove_url" not in data
        assert "formattedDate" not in data

#Testing cancel order on checkout
@pytest.mark.parametrize(
    "rfidUID, expectedMessage, expectedRedirect",
    [
        (1986993982, "No purchases found to cancel.", "/home/scanrfid"), #Valid UID with no purchases
        (105, "Invalid customer tag given.", "/home/scanrfid"), #Invalid UID with no purchases
        (101, "Payment has been cancelled, and purchases have been removed.", "/home/scanrfid"), #Valid UID with purchases
    ]
)
def test_cancel_order(client, rfidUID, expectedMessage, expectedRedirect):
    response = client.post('checkout/cancel/'+str(rfidUID),
                           follow_redirects=True)
    
    responseString = response.data.decode('utf-8')

    assert response.status_code == 200 #Check redirect followed
    assert expectedMessage in responseString #Check correct flash message
    assert response.request.path == expectedRedirect #Check redirect is to correct page
    #Checking any purchases attached to the rfid UID have been removed
    checkCancelled = db.session.query(Purchase).filter_by(rfid_uid=rfidUID).all()
    assert len(checkCancelled) == 0

#Test checkout session (Route which sends Stripe API request)
#Testing the parameters which should NOT send a request to Stripe
@pytest.mark.parametrize(
    "rfidUID, usingPoints, expectedMessage, expectedRedirect",
    [
        (1986993982, "true", "No purchases/dispenses were found in your cart, please add items and try again.", "/checkout/checkout"), #Valid UID with no purchases
        (105, "false", "Invalid customer tag given.", "/home/scanrfid"), #Invalid UID with no purchases
        (101, "N/A", "An error occured regarding loyalty points.", "/checkout/checkout"), #Valid UID with purchases but invalid using points
    ]
)
def test_checkout_session(client, rfidUID, usingPoints, expectedMessage, expectedRedirect):
    response = client.post('checkout/checkout-session/'+str(rfidUID),
                            data={"using-points-hidden": usingPoints},
                            follow_redirects=True)

    responseString = response.data.decode('utf-8')

    #Check the flash message is correct
    assert response.status_code == 200  #Check redirect was followed
    assert expectedMessage in responseString #Check flashed message
    assert response.request.path == expectedRedirect #Check redirect is to correct page

#Test confirm route which finalises purchase in the database
@pytest.mark.parametrize(
    "rfidUID, usingPoints, totalCost, expectedMessage, expectedRedirect",
    [
        (1986993982, "true", 500, "No purchases/dispenses were found in your cart, please add items and try again.", "/checkout/checkout"),  #Valid UID without purchases
        (101, "false", 250, "Payment Confirmed and Order Finalized!", "/receipt/account_receipt"),  #Valid account UID with purchases using points false, cost passed is purchases cost
        (102, "true", 1000, "An error occured regarding loyalty points.", "/checkout/checkout"),  #Valid guest UID with purchases using points true
        (102, "false", 175, "Payment Confirmed and Order Finalized!", "/receipt/guest_receipt"),  #Valid guest UID with purchases using points false, cost passed is purchases cost
        (105, "true", 500, "Invalid customer tag given.", "/home/scanrfid"),  #Invalid RFID UID
        (1986993982, "true", "StringCost", "Total cost given was invalid, unable to confirm order.", "/checkout/checkout"),  #String total cost
    ]
)
#Testing confirm order on checkout
def test_confirm_order(client, rfidUID, usingPoints, totalCost, expectedMessage, expectedRedirect):
    with client.session_transaction() as session:
        session['checkoutSessionID'] = "test"  #Setting session

    response = client.get("/checkout/confirm/"+str(rfidUID),
                            query_string={"usingPoints": usingPoints,
                                          "totalCost": totalCost},
                            follow_redirects=True)
    responseString = response.data.decode('utf-8')

    #Check flash message is correct
    assert response.status_code == 200
    assert expectedMessage in responseString
    #Check redirect is to the expected page
    assert expectedRedirect in response.request.path

    #If the confirm order is valid (a receipt is presented to user)
    if "receipt" in response.request.path:
        #Get last order added
        orderCheck = db.session.query(Order).order_by(Order.id.desc()).first()
        #Check total cost sent (cost after point deduction) + points used
        #equals total cost of order
        assert orderCheck.order_cost == (totalCost + orderCheck.points_used) / 100
        #Check purchases have been archived
        archivedPurchases = db.session.query(ArchivedPurchase).filter_by(order_id=orderCheck.id).all()
        assert len(archivedPurchases) > 0