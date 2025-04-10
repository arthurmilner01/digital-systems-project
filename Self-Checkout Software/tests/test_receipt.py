import pytest
from extensions import db
from models import *

@pytest.mark.parametrize(
    "orderID, rfidUID, expectedSuccess, expectedSendStatus, expectedRedirect",
    [
        (1, 103, True, "An email confirmation of purchase has been sent.", "/receipt/account_receipt"),  #Valid account UID with valid order
        (10121243, 101, False, "Order not found.", "/checkout/checkout"),  #Valid account UID with invalid order
        (4, 999999999, False, "Invalid customer tag given.", "/home/scanrfid"),  #Invalid UID
        (5, 3298572094, False, "Account not found.", "/checkout/checkout"),  #Valid UID without account
    ]
)
def test_account_receipt(client, orderID, rfidUID, expectedSuccess, expectedSendStatus, expectedRedirect):
    response = client.get("receipt/account_receipt/"+str(orderID)+"/"+str(rfidUID), follow_redirects=True)
    responseString = response.data.decode('utf-8')

    assert response.status_code == 200
    assert expectedRedirect in response.request.path
    assert expectedSendStatus in responseString

    #If receipt expected to be valid verify database
    if expectedSuccess == True:
        #Check that the order and dispenses exist in the database
        order = db.session.query(Order).filter_by(id=orderID).first()
        assert order is not None

        dispenses = db.session.query(ArchivedPurchase).filter_by(order_id=orderID).all()
        #Check dispenses are > 0
        assert len(dispenses) > 0

        #Test the account exists/is correctly fetched
        account = db.session.query(Account).filter_by(rfid_uid=rfidUID).first()
        assert account is not None  #Ensure the account is found

@pytest.mark.parametrize(
    "orderID, rfidUID, expectedSuccess, expectedMessage, expectedRedirect",
    [
        (1, 103, False, "An email confirmation of purchase has been sent.", "/receipt/account_receipt"),  #Valid account UID with valid order
        (2, 104, True, "", "receipt/guest_receipt"), #Valid guest UID with valid order
        (999999, 103, False, "Order not found.", "/checkout/checkout"),  #Valid account UID with invalid order
        (4, 999999999, False, "Invalid customer tag given.", "/home/scanrfid"),  #Invalid UID
        (5, 3298572094, False, "Order not found, redirected to the page to scan a customer tag.", "/home/scanrfid"),  #Valid guest UID without order
    ]
)
def test_guest_receipt(client, orderID, rfidUID, expectedSuccess, expectedMessage, expectedRedirect):
    response = client.get("receipt/guest_receipt/"+str(orderID)+"/"+str(rfidUID), follow_redirects=True)
    responseString = response.data.decode('utf-8')

    assert response.status_code == 200
    assert expectedMessage in responseString
    assert expectedRedirect in response.request.path

    #If receipt expected to be valid verify database
    if expectedSuccess == True:
        #Check that the order and dispenses exist in the database
        order = db.session.query(Order).filter_by(id=orderID).first()
        assert order is not None

        dispenses = db.session.query(ArchivedPurchase).filter_by(order_id=orderID).all()
        #Check dispenses are > 0
        assert len(dispenses) > 0

        #Test the RFID is a guest tag
        account = db.session.query(Account).filter_by(rfid_uid=rfidUID).first()
        assert account is None  #Ensure no account found

@pytest.mark.parametrize(
    "orderID, rfidUID, email, name, expectedRedirect, expectedPoints, expectedMessage",
    [
        (2, 104, "test@example.com", "Test User", "/receipt/new_account", 15, ""),  #New account (order = £15 so expected points 15), also tests new account redirect works
        (2, 104, "arthurmilner01@gmail.com", "Different Name", "/receipt/guest_receipt", None, "Email is already in use with an account."),  #Attempting to create an account that already exists
    ]
)
def test_guest_signup(client, orderID, rfidUID, email, name, expectedRedirect, expectedPoints, expectedMessage):
    #Sending POST request with email and name
    response = client.post("/receipt/guest_receipt/"+str(orderID)+"/"+str(rfidUID), data={
        "input-email": email,
        "input-name": name
    }, follow_redirects=True)

    responseString = response.data.decode('utf-8')

    assert response.status_code == 200
    assert expectedMessage in responseString
    assert expectedRedirect in response.request.path

    #If account is expected to be created
    if expectedPoints is not None:
        #Check that the account was created with the correct email and points
        account = db.session.query(Account).filter_by(email=email).first()
        assert account is not None
        assert account.rfid_uid == rfidUID
        assert account.points == expectedPoints
    else:
        #Check a duplicate account is not created
        accounts = db.session.query(Account).filter_by(email=email).all()
        assert len(accounts) == 1


@pytest.mark.parametrize(
    "accountEmail, orderID, expectedSuccess, expectedMessage, expectedRedirect",
    [
        ("arthur2.milner@live.uwe.ac.uk", 1, True, "An email confirmation of your purchase has been sent.", "/receipt/new_account"), #Valid account and order
        ("arthur2.milner@live.uwe.ac.uk", 99999, False, "Provided order number does not exist to the given account, or does not exist at all.", "/home/scanrfid"), #Valid account and invalid order
        ("invalid@example.com", 1, False, "Email provided does not belong to an account.", "/home/scanrfid"), #Invalid account with existing order
        ("invalid@example.com", 1, False, "Email provided does not belong to an account.", "/home/scanrfid"), #Invalid account with invalid order
        ("arthur2.milner@live.uwe.ac.uk", 999999, False, "Provided order number does not exist to the given account, or does not exist at all.", "/home/scanrfid"), #Invalid order ID
        ("arthurmilner01@gmail.com", 1, False, "Provided order number does not exist to the given account, or does not exist at all.", "/home/scanrfid") #Valid account and with another account's order
    ]
)
def test_new_account_page(client, accountEmail, orderID, expectedSuccess, expectedMessage, expectedRedirect):
    response = client.get("/receipt/new_account/"+str(accountEmail)+"/"+str(orderID), follow_redirects=True)
    responseString = response.data.decode('utf-8')

    assert response.status_code == 200
    assert expectedMessage in responseString
    assert expectedRedirect in response.request.path

    if expectedSuccess:
        #Check the account exists in db
        account = db.session.query(Account).filter_by(email=accountEmail).first()
        assert account is not None
        #Check the order exists
        order = db.session.query(Order).filter_by(id=orderID).first()
        assert order is not None
        #Check archived purchases exist
        dispenses = db.session.query(ArchivedPurchase).filter_by(order_id=orderID).all()
        assert len(dispenses) > 0

