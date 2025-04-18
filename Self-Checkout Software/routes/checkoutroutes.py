from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session
import stripe
from datetime import datetime
from models import *
from extensions import db


checkoutBlueprint = Blueprint('checkout', __name__)

stripe.api_key = "******"
STRIPE_PUBLIC_KEY = "******"

#For displaying the checkout
@checkoutBlueprint.route("/checkout")
def checkout():
    #Clear the checkout session ID (if payment cancels redirects here)
    #Check if session exists first
    checkoutSessionID = session.get('checkoutSessionID')
    if checkoutSessionID is not None:
        del session['checkoutSessionID']
    #Get RFID UID input from /scanrfid
    rfidUID = request.args.get('rfidUID')
    #Validate RFID UID
    validRFID = db.session.query(RFIDTags).filter_by(rfid_uid=rfidUID).first()
    if validRFID is None:
        flash("Invalid tag ID entered, please try again.", "error")
        return redirect(url_for('home.rfidUID'))
    #Table headings
    headings = ("Product", "Weight", "Cost", "Time of Purchase", "Keep Item?")
    #Get list of items
    items = db.session.query(Item).all()
    #Returns products attached to that RFID tag
    purchasesByRFID = db.session.query(Purchase).filter_by(rfid_uid=rfidUID).all()
    #Check if RFID is connected to an account
    accountExists = db.session.query(Account).filter_by(rfid_uid=rfidUID).first()
    
    #Calculates total cost of those products
    totalCost = 0
    for purchase in purchasesByRFID:
        totalCost = totalCost + float(purchase.cost)

    return render_template("checkout.html",
                            rfidUID = rfidUID,
                            headings=headings,
                            purchases=purchasesByRFID,
                            totalCost = totalCost,
                            items=items,
                            accountExists=accountExists)


#For cancelling an order
@checkoutBlueprint.route("/cancel/<rfidUID>", methods=["POST"])
def cancel(rfidUID):
    rfidCheck = db.session.query(RFIDTags).filter_by(rfid_uid=rfidUID).first()
    if not rfidCheck:
        flash("Invalid customer tag given.", "error")
        return redirect(url_for('home.rfidUID'))
    
    #Gets products to cancel
    cancelledPurchases = db.session.query(Purchase).filter_by(rfid_uid=rfidUID).all()
    if cancelledPurchases:
        #Removing cancelled purchases
        for purchase in cancelledPurchases:
            db.session.delete(purchase)  #Removes purchase from purchases table
    
        db.session.commit() #Finalise changes
        #Payment cancelled 
        flash("Payment has been cancelled, and purchases have been removed.", "success")
        return redirect(url_for('home.rfidUID')) #Redirect to scanrfid page
    else:
        flash("No purchases found to cancel.", "error")
        return redirect(url_for('home.rfidUID')) #Redirect to scanrfid page


#For taking the stripe payment
@checkoutBlueprint.route('/checkout-session/<rfidUID>', methods=['POST'])
def checkoutSession(rfidUID):
    #Gets total cost dependent on if the user was using points
    usingPoints = request.form.get('using-points-hidden')

    rfidCheck = db.session.query(RFIDTags).filter_by(rfid_uid=rfidUID).first()
    if not rfidCheck:
        flash("Invalid customer tag given.", "error")
        return redirect(url_for('checkout.checkout', rfidUID=rfidUID))


    purchasesByRFID = db.session.query(Purchase).filter_by(rfid_uid=rfidUID).all()
    #If no purchases found
    if not purchasesByRFID:
        flash("No purchases/dispenses were found in your cart, please add items and try again.", "error")
        return redirect(url_for('checkout.checkout', rfidUID=rfidUID))
    
    #If usingPoints is not equal to true or false
    if usingPoints not in ["true", "false"]:
        flash("An error occured regarding loyalty points.", "error")
        return redirect(url_for('checkout.checkout', rfidUID=rfidUID))

    
    #Calculates total cost of order
    totalCost = 0
    for purchase in purchasesByRFID:
        totalCost = totalCost + float(purchase.cost)
    
    #In pennies for Stripe API
    totalCost = int(totalCost * 100)

    #If using account points deduct off cost
    if(usingPoints == "true"):
        accountExists = db.session.query(Account).filter_by(rfid_uid=rfidUID).first()
        if accountExists:
            #Max in case user has more points than the order cost
            totalCost = max(0, totalCost - accountExists.points)
        else:
            flash("An error occured regarding loyalty points.", "error")
            return redirect(url_for('checkout.checkout', rfidUID=rfidUID))
        
    #If cost is below 0
    if totalCost < 0:
        flash("Total was below zero, unable to confirm order.", "error")
        return redirect(url_for('checkout.checkout', rfidUID=rfidUID))
    #If total cost is zero (user either paying with points or free item) avoid creating payment session just add to DB
    if totalCost == 0:
        session['checkoutSessionID'] = "N/A"
        return redirect(url_for('checkout.confirm', rfidUID=rfidUID, usingPoints=usingPoints, totalCost=totalCost))

    print(totalCost)

    #Creating stripe session
    checkoutSession = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[
            {
                'price_data': {
                    'currency': 'gbp',
                    'product_data': {
                        'name': f'Order for Basket {rfidUID}',
                    },
                    'unit_amount': totalCost,  #Total cost in pennies
                },
                'quantity': 1,
            },
        ],
        mode='payment',
        #Redirects for if payment is successful or not
        success_url=url_for('checkout.confirm', rfidUID=rfidUID, usingPoints=usingPoints, totalCost=totalCost, _external=True),
        cancel_url=url_for('checkout.checkout', rfidUID=rfidUID, _external=True),
        billing_address_collection='auto',
        customer_email=None,
        allow_promotion_codes=False,
    )
    #Getting checkout session ID to store in database
    session['checkoutSessionID'] = checkoutSession.id
    #Send user to the stripe session
    return redirect(checkoutSession.url)

#For confirming an order after payment has been processed, needs to be GET because of stripe success url
@checkoutBlueprint.route("/confirm/<rfidUID>", methods=["GET"])
def confirm(rfidUID):
    try:
        #Confirm RFID UID valid
        rfidCheck = db.session.query(RFIDTags).filter_by(rfid_uid=rfidUID).first()
        if not rfidCheck:
            flash("Invalid customer tag given.", "error")
            return redirect(url_for('home.rfidUID', rfidUID=rfidUID))
        
        #Getting if the user used points and the cost after point discount
        usingPoints = request.args.get('usingPoints')
        #In try except in case string cost is passed
        try:
            afterPointsCost = int(request.args.get('totalCost'))
        except:
            flash("Total cost given was invalid, unable to confirm order.", "error")
            return redirect(url_for('checkout.checkout', rfidUID=rfidUID))

        #If usingPoints is not equal to true or false 
        if usingPoints not in ["true", "false"]:
            flash("An error occured regarding loyalty points.", "error")
            return redirect(url_for('checkout.checkout', rfidUID=rfidUID))
        
        #If cost is below 0
        if afterPointsCost < 0:
            flash("Total cost given was invalid, unable to confirm order.", "error")
            return redirect(url_for('checkout.checkout', rfidUID=rfidUID))
        
        #Get cost without point discount
        purchases = db.session.query(Purchase).filter_by(rfid_uid=rfidUID).all()
        #If no purchases found
        if not purchases:
            flash("No purchases/dispenses were found in your cart, please add items and try again.", "error")
            return redirect(url_for('checkout.checkout', rfidUID=rfidUID))
        
        #Cost of order without loyalty point discount
        withoutPointCost = sum(float(purchase.cost) for purchase in purchases)

        #Get account tied to rfid UID
        account = db.session.query(Account).filter_by(rfid_uid=rfidUID).first()
        #If using loyalty points but points is set to true
        if usingPoints == "true" and account is None:
            flash("An error occured regarding loyalty points.", "error")
            return redirect(url_for('checkout.checkout', rfidUID=rfidUID))

        if usingPoints == "true":
            #Get prices in pennies and find difference to calculate points to deduct
            priceDifference = (withoutPointCost * 100) - afterPointsCost
        else:
            priceDifference = 0

        #If account exists
        if account is not None:
            if account.points >= priceDifference:
                #Deduct the points (one point is one penny)
                account.points -= priceDifference
            else:
                account.points = 0

            #Add points for the purchase, one point for every £ spent
            account.points += afterPointsCost // 100
            
        #Get checkout session ID and clear the session key
        sessionID = session.pop('checkoutSessionID', None)

        if sessionID is None or not isinstance(sessionID, str):
            flash("An error occured with Stripe, please contact a member of staff.", "error")
            return redirect(url_for('checkout.checkout', rfidUID=rfidUID))


        #Create Order ID for order and store total cost and points used
        thisOrder = Order(order_cost=withoutPointCost, points_used=priceDifference, checkout_session_id=sessionID, order_refunded=False)
        db.session.add(thisOrder)
        #Flush to update database but do not commit until all changes are made
        db.session.flush()

        orderID = thisOrder.id #Grab ID

        #Add purchases to archived purchases to keep a record
        for purchase in purchases:
            archivePurchase = ArchivedPurchase(
                rfid_uid=purchase.rfid_uid,
                name=purchase.name,
                weight=purchase.weight,
                cost=purchase.cost,
                order_id=orderID  #Foreign key from Order table
            )
            db.session.add(archivePurchase) #Adding to archive table
            db.session.delete(purchase) #Deleting from purchase table

        db.session.commit() #Finalise changes
        #Success message to confirm payment to user
        flash("Payment Confirmed and Order Finalized!", "success")

        if account is not None:
            #If rfid tag linked to an account
            return redirect(url_for('receipt.accountReceipt', orderID=orderID, rfidUID=rfidUID))
        else:
            #If rfid tag not linked to an account
            return redirect(url_for('receipt.guestReceipt', orderID=orderID, rfidUID=rfidUID))
    except Exception as e:
            #If error
            print(e)
            db.session.rollback()
            return jsonify({'success': False}), 500
    
#For AJAX removal of items
@checkoutBlueprint.route('/remove_purchase', methods=['POST'])
def removePurchase():
    try:
        #Parses JSON from AJAX
        data = request.get_json()
        purchase_id = data.get('id')

        #Deleted purchase from db
        purchase = db.session.query(Purchase).filter_by(id=purchase_id).first()
        if purchase:
            rfidUID = purchase.rfid_uid
            #Delete the purchase
            db.session.delete(purchase)
            db.session.commit()

            #Get total cost to use in AJAX for updating
            purchasesByRFID = db.session.query(Purchase).filter_by(rfid_uid=rfidUID).all()
            #If no purchases set total cost to 0
            if not purchasesByRFID:
                totalCost = 0
            else:
                #Calculates new total cost
                totalCost = 0
                for purchase in purchasesByRFID:
                    totalCost = totalCost + float(purchase.cost)
                totalCost = round(totalCost, 2)

            return jsonify({'success':True,
                        'totalCost':totalCost})
        else:
            flash("Purchase not found.", "error")
            return jsonify(success=False, message="Purchase not found.")
    except Exception as e:
        #If error
        print(e)
        db.session.rollback()
        return jsonify({'success': False}), 500
    
#For AJAX custom dispense addition
@checkoutBlueprint.route('/add_dispense', methods=['POST'])
def addDispense():
    try:
        # Get JSON data from the request
        data = request.get_json()

        # Extract product details from the request data
        rfid_uid = int(data.get('rfid_uid'))
        product_name = data.get('name')
        product_weight = float(data.get('weight'))
        product_cost = float(data.get('cost'))
        purchased_at = data.get('purchased_at')
        purchased_at = datetime.fromisoformat(purchased_at)

        #If RFID UID invalid
        rfidCheck = db.session.query(RFIDTags).filter_by(rfid_uid=rfid_uid).first()
        if rfidCheck == None:
            return jsonify({'success': False,
                        'message': 'Invalid customer tag.'})
        #If item name is empty or not a string
        if not isinstance(product_name, str) or not product_name:
            return jsonify({'success': False,
                        'message': 'Invalid item name.'})
        #If item weight is empty or not a float/int or not positive
        if not isinstance(product_weight, (float, int)) or not product_weight or product_weight <= 0:
            return jsonify({'success': False,
                        'message': 'Invalid item weight.'})
        #If item cost is empty or not a float/int or not positive
        if not isinstance(product_cost, (float, int)) or not product_cost or product_cost <= 0:
            return jsonify({'success': False,
                        'message': 'Invalid item cost.'})

        #Create custom dispense
        customPurchase = Purchase(
            rfid_uid = rfid_uid,
            name=product_name,
            weight=product_weight,
            cost=product_cost,
            purchased_at= purchased_at
        )

        #Add the custom dispense
        db.session.add(customPurchase)
        db.session.commit()

        #Get total cost to use in AJAX for updating
        purchasesByRFID = db.session.query(Purchase).filter_by(rfid_uid=rfid_uid).all()

        #Calculates total cost of those products
        totalCost = 0
        for purchase in purchasesByRFID:
            totalCost = totalCost + float(purchase.cost)
        totalCost = round(totalCost, 2)

        formattedDate = purchased_at.strftime('%d-%m-%Y %H:%M:%S')

        #Return success and details needed to add to table
        return jsonify({'success': True,
                        'purchase_id': customPurchase.id,
                        'pin_url': url_for('checkout.validatePin'),
                        'remove_url': url_for('checkout.removePurchase'),
                        'totalCost': totalCost,
                        'formattedDate': formattedDate})
    except Exception as e:
        #If error
        print(e)
        db.session.rollback()
        return jsonify({'success': False}), 500

#For AJAX adding item
@checkoutBlueprint.route('/add_item', methods=['POST'])
def addItem():
    try:
        # Get JSON data from the request
        data = request.get_json()

        # Extract product details from the request data
        rfid_uid = int(data.get('rfid_uid'))
        item_name = data.get('name')
        item_weight = 0.0
        item_cost = float(data.get('cost'))
        purchased_at = data.get('purchased_at')
        purchased_at = datetime.fromisoformat(purchased_at)

        #If RFID UID invalid
        rfidCheck = db.session.query(RFIDTags).filter_by(rfid_uid=rfid_uid).first()
        if rfidCheck == None:
            return jsonify({'success': False,
                        'message': 'Invalid customer tag.'})
        #If item name is empty or not a string
        if not isinstance(item_name, str) or not item_name:
            return jsonify({'success': False,
                        'message': 'Invalid item name.'})
        #If item cost is empty or not a float/int or not positive
        if not isinstance(item_cost, (float, int)) or not item_cost or item_cost <= 0:
            return jsonify({'success': False,
                        'message': 'Invalid item cost.'})


        #Create custom dispense
        item = Purchase(
            rfid_uid = rfid_uid,
            name=item_name,
            weight=item_weight,
            cost=item_cost,
            purchased_at= purchased_at
        )

        #Add the item to the purchase
        db.session.add(item)
        db.session.commit()

        #Get new total cost to use in AJAX for updating
        purchasesByRFID = db.session.query(Purchase).filter_by(rfid_uid=rfid_uid).all()

        #Calculates total cost of those products
        totalCost = 0
        for purchase in purchasesByRFID:
            totalCost = totalCost + float(purchase.cost)
        totalCost = round(totalCost, 2)

        formattedDate = purchased_at.strftime('%d-%m-%Y %H:%M:%S')

        #Return success and details needed to add to table
        return jsonify({'success': True,
                        'purchase_id': item.id,
                        'pin_url': url_for('checkout.validatePin'),
                        'remove_url': url_for('checkout.removePurchase'),
                        'totalCost': totalCost,
                        'formattedDate': formattedDate})
    except Exception as e:
        #If error
        print(e)
        db.session.rollback()
        return jsonify({'success': False}), 500
    
#Route for validating input employee pin
@checkoutBlueprint.route('/validate-pin', methods=['POST'])
def validatePin():
    #Grab pin details from AJAX
    data = request.get_json()
    pin = int(data.get('pin'))
    #Get returned rows filtered by pin
    pinValid = db.session.query(Employee).filter_by(pin=pin).first()
    #If employee pin is correct
    #Send jsonified True/False value as response
    if pinValid:
        return jsonify(validPin=True)
    else:
        return jsonify(validPin=False)