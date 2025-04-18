from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
import stripe
from models import *
from extensions import db
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

refundBlueprint = Blueprint('refund', __name__)

#API key for sendgrid
SENDGRID_API_KEY = '******'
#API key for Stripe
stripe.api_key = "******"
STRIPE_PUBLIC_KEY = "******"

#Route for entering the refund request details
@refundBlueprint.route("/refund_request", methods=["GET"])
def refundRequest():
    return render_template('refundrequest.html')

#Route for validating the refund request
@refundBlueprint.route("/validate_refund", methods=["POST"])
def validateRefund():
    try:
        data = request.get_json()
        refundOrderID = data.get('refundOrderID')

        order = db.session.get(Order, refundOrderID)

        if order is None:
            return jsonify({
                    'success': False,
                    'message': "Order ID not found."
                    })
        
        if order.order_refunded is True:
            return jsonify({
                    'success': False,
                    'message': "Order already refunded."
                    })

        #If points were used deduct them from the refund amount (1 points = 1 pence)
        if order.points_used > 0:
            refundAmount = order.order_cost - (order.points_used/100)
        else:
            refundAmount = order.order_cost

        print(refundAmount)

        if refundAmount < 0:
            return jsonify({
                    'success': False,
                    'message': "Refund amount was calculated below zero."
                    })

        return jsonify({
            'success': True,
            'message': "Refund valid",
            'refundAmount': refundAmount,
            'refundPoints': order.points_used
            })
    except Exception as e:
        return jsonify({
                    'success': False,
                    'message': "Error validating refund."
                    }), 500
    
@refundBlueprint.route("/refund_session", methods=["POST"])
def refundSession():
    data = request.get_json()
    refundOrderID = data.get('refundOrderID')
    refundAmount = data.get('refundAmount')
    refundPoints = data.get('refundPoints')

    #Get order
    order = db.session.get(Order, refundOrderID)

    #For ensuring user doesn't end up with more points after refunding
    #Points the users would have earned from the order
    orderPointsEarned = (order.order_cost*100) // 100 

    #If money is to be refunded
    if refundAmount > 0:
        #Use session ID to get payment intent ID
        checkoutSession = stripe.checkout.Session.retrieve(order.checkout_session_id)
        paymentIntentID = checkoutSession.payment_intent
        #Create the refund
        refund = stripe.Refund.create(
                payment_intent=paymentIntentID,
                amount=int(refundAmount*100) #In pennies
        )
        #Check refund status to determine whether refund requests was successful
        if (refund.status == 'succeeded') or (refund.status == 'pending'):
            #Update database to reflect refund
            order.order_refunded = True
            getAccount = db.session.query(ArchivedPurchase).filter_by(order_id=refundOrderID).first()
            account = db.session.query(Account).filter_by(rfid_uid=getAccount.rfid_uid).first()
            #If refund is attached to an account
            if account != None:
                #Ensure points do not fall below 0, will use the bigger value of the two here
                newPoints = account.points + order.points_used - orderPointsEarned
                account.points = max(0, newPoints)
                confirmationMessage = Mail(
                from_email='arthur2.milner@live.uwe.ac.uk',
                to_emails=account.email,
                subject='Email Receipt Confirmation for Refund of Order '+ str(order.id),
                html_content=f'''
                <html>
                    <body>
                        <h2><b>Refund Receipt</b></h2>
                        <h3><b>Order Number:</b> {order.id}</h3>
                        <h4><b>Points Refunded:</b> {refundPoints}</h4>
                        <h4><b>Amount Refunded:</b> {refundAmount}</h4>
                    </body>
                </html>
                '''
                )

                sendgridClient = SendGridAPIClient(SENDGRID_API_KEY)
                status = sendgridClient.send(confirmationMessage)
                #202 means email successfully sent
                if(status.status_code==202):
                    sendStatus = "An email confirmation of refund has been sent."
                else:
                    sendStatus = "There was an error sending the email confirmation."
            else:
                #No email sent if no account
                sendStatus = ""
            #Commit changes regardless of account or not
            db.session.commit()
            
            flash("Refund successfully processed, please allow 3-5 days for it to complete. Any points used have also been returned. "+ sendStatus, "success")
            return jsonify({"success": True,})
        else:
            return jsonify({
                    'success': False,
                    'message': "Stripe failed to process the refund."
                    })
    elif refundAmount == 0: #If only points are to be refunded
        #Update database to reflect refund
        order.order_refunded = True
        getAccount = db.session.query(ArchivedPurchase).filter_by(order_id=refundOrderID).first()
        account = db.session.query(Account).filter_by(rfid_uid=getAccount.rfid_uid).first()
        #If refund is attached to an account (never shouldn't be the case here)
        if account != None:
            #Ensure points do not fall below 0, will use the bigger value of the two here
            newPoints = account.points + order.points_used - orderPointsEarned
            account.points = max(0, newPoints)
            confirmationMessage = Mail(
            from_email='arthur2.milner@live.uwe.ac.uk',
            to_emails=account.email,
            subject='Email Receipt Confirmation for Refund of Order '+ str(order.id),
            html_content=f'''
            <html>
                <body>
                    <h2><b>Refund Receipt</b></h2>
                    <h3><b>Order Number:</b> {order.id}</h3>
                    <h4><b>Points Refunded:</b> {refundPoints}</h4>
                    <h4><b>Amount Refunded:</b> {refundAmount}</h4>
                </body>
            </html>
            '''
            )

            sendgridClient = SendGridAPIClient(SENDGRID_API_KEY)
            status = sendgridClient.send(confirmationMessage)
            #202 means email successfully sent
            if(status.status_code==202):
                sendStatus = "An email confirmation of refund has been sent."
            else:
                sendStatus = "There was an error sending the email confirmation."
        else:
            sendStatus = ""
        db.session.commit()

        flash("Refund successfully processed, please allow 3-5 days for it to complete. Any points used have also been returned. "+ sendStatus, "success")
        return jsonify({"success": True,})
    else:
        return jsonify({
                    'success': False,
                    'message': "An error occured processing the refund."
                    })