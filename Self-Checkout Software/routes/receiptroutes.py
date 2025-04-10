from flask import Blueprint, request, render_template, redirect, url_for, flash
from sqlalchemy import func
from models import *
from extensions import db
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


receiptBlueprint = Blueprint('receipt', __name__)

#API key for sendgrid
SENDGRID_API_KEY = '******'

#Receipt if already an account holder
@receiptBlueprint.route("/account_receipt/<orderID>/<rfidUID>", methods=["GET"])
def accountReceipt(orderID, rfidUID):
    #Check RFID
    rfidCheck = db.session.query(RFIDTags).filter_by(rfid_uid=rfidUID).first()
    if not rfidCheck:
        flash("Invalid customer tag given.", "error")
        return redirect(url_for('checkout.checkout', rfidUID=rfidUID))
    #Grab account and order details for emailing/displaying html
    account = db.session.query(Account).filter_by(rfid_uid=rfidUID).first()
    if not account:
        flash("Account not found.", "error")
        return redirect(url_for('checkout.checkout', rfidUID=rfidUID))
    #For sending receipt confirmation email
    order = db.session.query(Order).filter_by(id=orderID).first()
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for('checkout.checkout', rfidUID=rfidUID))
    #Purchases made for displaying on receipt
    dispenses = db.session.query(ArchivedPurchase).filter_by(order_id=order.id).all()
    if not dispenses:
        flash("No purchases found for this order.", "error")
        return redirect(url_for('checkout.checkout', rfidUID=rfidUID))
    dispenseName = []
    for dispense in dispenses:
        dispenseName.append(dispense.name)
    #Construct email using sendgrid Mail
    confirmationMessage = Mail(
        from_email='arthur2.milner@live.uwe.ac.uk',
        to_emails=account.email,
        subject='Email Receipt Confirmation for Order '+ str(order.id),
        html_content=f'''
        <html>
            <body>
                <h2><b>Order Receipt</b></h2>
                <h3><b>Order Number:</b> {order.id}</h3>
                <h3><b>Purchases:</b></h3>
                <p>{", ".join(dispenseName)}</p>
                <h4><b>Points Used:</b> {order.points_used}</h4>
                <h4><b>Order Total:</b> {order.order_cost:.2f}</h4>
            </body>
        </html>
        '''
    )

    sendgridClient = SendGridAPIClient(SENDGRID_API_KEY)
    status = sendgridClient.send(confirmationMessage)
    print(status)
    
    #202 means email successfully sent
    if(status.status_code==202):
        sendStatus = "An email confirmation of purchase has been sent."
    else:
        sendStatus = "There was an error sending the email confirmation."

    return render_template('accountreceipt.html', account=account, sendStatus=sendStatus)

#Receipt for guest
@receiptBlueprint.route("/guest_receipt/<orderID>/<rfidUID>", methods=["GET", "POST"])
def guestReceipt(orderID, rfidUID):
    #Check RFID
    rfidCheck = db.session.query(RFIDTags).filter_by(rfid_uid=rfidUID).first()
    if not rfidCheck:
        flash("Invalid customer tag given.", "error")
        return redirect(url_for('checkout.checkout', rfidUID=rfidUID))
    
    #Check rfid is not with an account
    accountCheck = db.session.query(Account).filter_by(rfid_uid=rfidUID).first()
    if accountCheck != None:
        flash("Customer tag is set to an account.", "error")
        return redirect(url_for('receipt.accountReceipt', orderID=orderID, rfidUID=rfidUID))

    order = db.session.query(Order).filter_by(id=orderID).first()
    if order == None:
        flash("Order not found, redirected to the page to scan a customer tag.", "error")
        return redirect(url_for('home.rfidUID'))
    
    #Get the purchases from the order ID
    archivedPurchases = db.session.query(ArchivedPurchase).filter_by(order_id=order.id).all()

    if request.method == "POST":
        #If user submits their personal details
        email = request.form["input-email"]
        name = request.form["input-name"]
        #Check email and RFID UID are not already in use
        emailCheck = db.session.query(Account).filter_by(email=email).first()
        if emailCheck != None: #If email is in use
            flash("Email is already in use with an account.", "error")
            return redirect(url_for('receipt.guestReceipt', orderID=orderID, rfidUID=rfidUID))
        else: #If checks are passsed
            #Get earliest order purchase archived_at value for account creation date as a single value
            #This is so the items will show as purchased by the new account
            accountDate = db.session.query(func.min(ArchivedPurchase.archived_at)).filter_by(order_id=order.id).scalar()
            #Add appropriate points based on order cost
            pointsFromPurchase = (order.order_cost // 1)
            #Create account
            newAccount = Account(email=email, name=name, rfid_uid=rfidUID, points=pointsFromPurchase, created_at=accountDate)
            #Insert account into database
            db.session.add(newAccount)
            db.session.commit()
            #Redirect to account created page displaying confirmation and a button for next dispense
            return redirect(url_for('receipt.newAccount', accountEmail=email, orderID=order.id))
        
    elif request.method == "GET":
        return render_template('guestreceipt.html', order=order, archivedPurchases=archivedPurchases, rfidUID=rfidUID)
    
#On new account creation
@receiptBlueprint.route("/new_account/<accountEmail>/<orderID>", methods=["GET"])
def newAccount(accountEmail, orderID):
    account = db.session.query(Account).filter_by(email=accountEmail).first()
    #Check account exists
    if account == None:
        flash("Email provided does not belong to an account.")
        return redirect(url_for('home.rfidUID'))
    #Check order rfid uid matches account rfid uid
    orderIDCheck = db.session.query(ArchivedPurchase).filter_by(order_id=orderID, rfid_uid=account.rfid_uid).first()
    if orderIDCheck == None:
        flash("Provided order number does not exist to the given account, or does not exist at all.")
        return redirect(url_for('home.rfidUID'))
    
    #Grabbing order details
    order = db.session.query(Order).filter_by(id=orderID).first()
    #Purchases made for displaying on receipt
    dispenses = db.session.query(ArchivedPurchase).filter_by(order_id=order.id).all()
    dispenseName = []
    for dispense in dispenses:
        dispenseName.append(dispense.name)

    #Construct email using sendgrid Mail
    confirmationMessage = Mail(
        from_email='arthur2.milner@live.uwe.ac.uk',
        to_emails=account.email,
        subject='Email Receipt Confirmation for Order '+ str(order.id),
        html_content=f'''
        <html>
            <body>
                <h2><b>Order Receipt</b></h2>
                <h3><b>Order Number:</b> {order.id}</h3>
                <h3><b>Purchases:</b></h3>
                <p>{", ".join(dispenseName)}</p>
                <h4><b>Points Used:</b> {order.points_used}</h4>
                <h4><b>Order Total:</b> {order.order_cost:.2f}</h4>
            </body>
        </html>
        '''
    )

    #Making API call to send email
    sendgridClient = SendGridAPIClient(SENDGRID_API_KEY)
    #Get status of email send
    status = sendgridClient.send(confirmationMessage)
    
    #202 means email successfully sent
    if(status.status_code==202):
        sendStatus="An email confirmation of your purchase has been sent."
    else:
        sendStatus='There was an error sending email confirmation of your order.'

    return render_template('accountcreated.html', account=account, sendStatus=sendStatus)