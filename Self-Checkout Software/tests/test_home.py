import pytest

#Testing rfidUID/scanrfid page
@pytest.mark.parametrize(
    "rfidUID, expectedMessage, expectedRedirect",
    [
        (101, None, "/checkout/checkout"), #Valid rfid UID
        (10000000, "Invalid rfid.", "/home/scanrfid"), #Invalid rfid UID
        ("testrfid", "Invalid rfid.", "/home/scanrfid"), #String rfid UID
        (10.241, "Invalid rfid.", "/home/scanrfid") #Float rfid UID
    ]
)
def test_scan_rfid(client, rfidUID, expectedMessage, expectedRedirect):
    #Post rfid UID
    response = client.post("home/scanrfid",
                        data={"rfidUID": rfidUID}, 
                        follow_redirects=True)
    #Get as string
    data = response.data.decode("utf-8")


    assert response.status_code == 200
    assert expectedRedirect in response.request.path
    if expectedMessage:
        assert expectedMessage in data

def test_scan_rfid_clear_sessions(client):
    with client.session_transaction() as session:
        session['checkoutSessionID'] = "test"  #Setting session
        session['AdminAccess'] = True  #Setting session

    #Sending GET request
    response = client.get("home/scanrfid", follow_redirects=True)
    #Get response as string
    data = response.data.decode("utf-8")

    with client.session_transaction() as session:
        #Checking session is removed on GET
        assert "checkoutSessionID" not in session
        assert "AdminAccess" not in session 
    
    #Check redirect
    assert response.status_code == 200
    assert "/home/scanrfid" in data

@pytest.mark.parametrize(
    "employeePin, expectedMessage, expectedRedirect",
    [
        (123456, "Invalid employee pin, you have been redirected to the page for scanning a customer tag.", "/home/scanrfid"), #Invalid employee pin
        (2522945794, "Employee authorised, accessing admin. Please log-out when finished.", "/admin"), #Valid employee pin
        ("testrfid", "Invalid employee pin, you have been redirected to the page for scanning a customer tag.", "/home/scanrfid"), #String employee pin
        (10.241, "Invalid employee pin, you have been redirected to the page for scanning a customer tag.", "/home/scanrfid") #Float employee pin
    ]
)
def test_employee_login(client, employeePin, expectedMessage, expectedRedirect):
    response = client.post("home/employee_login", 
                           data={"employeePin": employeePin}, 
                           follow_redirects=True)
    #Get as string
    data = response.data.decode("utf-8")

    #Redirect correctly followed
    assert response.status_code == 200
    assert expectedRedirect in response.request.path
    #Flashed message is as expected
    assert expectedMessage in data

def test_employee_logout(client):
    #Create session
    with client.session_transaction() as session:
        session['AdminAccess'] = True

    response = client.get("home/employee_logout", follow_redirects=True)
    data = response.data.decode("utf-8")

    #Check session is cleared
    with client.session_transaction() as session:
        assert "AdminAccess" not in session

    #Check redirect
    assert response.status_code == 200
    assert "/home/scanrfid" in data