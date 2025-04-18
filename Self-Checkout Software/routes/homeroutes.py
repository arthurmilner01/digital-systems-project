from flask import Blueprint, request, render_template, redirect, url_for, flash, session
from models import *
from extensions import db

homeBlueprint = Blueprint('home', __name__)

#Page for user to input their RFID UID
@homeBlueprint.route("/scanrfid", methods=["POST", "GET"])
def rfidUID():
    if request.method == "POST":
        rfidUID = request.form["rfidUID"]
        rfidUIDCheck = db.session.query(RFIDTags).filter_by(rfid_uid=rfidUID).first()
        #If rfid uid in rfid tags table
        if rfidUIDCheck:
            return redirect(url_for("checkout.checkout", rfidUID= rfidUID))
        else:
            flash("Invalid rfid.", "error")
            return render_template("rfidinput.html")
    elif request.method == "GET":
        #Clear the session to remove authorisation
        #Should already be cleared but good contingency if employee forgets to log-out
        #Also clear checkout session ID for good measure
        if "checkoutSessionID" in session:
            session.pop("checkoutSessionID", None)
        if "AdminAccess" in session:
            session.pop("AdminAccess", None)
        return render_template("rfidinput.html")
    
@homeBlueprint.route("/employee_login", methods=["POST", "GET"])
def employeeLogin():
    if request.method == "POST":
        pin = request.form["employeePin"]
        pinCheck = db.session.query(Employee).filter_by(pin=pin).first()
        #Redirect to Flask-admin, the session will be used to check if access is authorised
        if pinCheck:
            session["AdminAccess"] = True
            flash("Employee authorised, accessing admin. Please log-out when finished.")
            return redirect(url_for('admin.index'))
        else:
            flash("Invalid employee pin, you have been redirected to the page for scanning a customer tag.", "error")
            return redirect(url_for('home.rfidUID'))
    else:
        return render_template("employeelogin.html")

#Route to clear the admin login session
@homeBlueprint.route("/employee_logout", methods=['GET'])
def employeeLogout():
    #Clear the session to remove authorisation
    if "AdminAccess" in session:
        session.pop("AdminAccess", None)
    #Return to scan rfid page
    return redirect(url_for('home.rfidUID'))