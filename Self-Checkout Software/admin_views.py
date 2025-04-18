# admin_views.py

from flask_admin import expose, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from models import *
from extensions import db
from flask import session, redirect, url_for, flash

#Adding auth check to main admin page
class CustomAdminIndexView(AdminIndexView):
    @expose('/') #To change the main admin page
    def index(self):
        #If authorised use normal index view, otherwise redirect to home
        if session.get("AdminAccess"):
            return super().index()
        else:
            flash("You are not authorised to access this page.")
            return redirect(url_for('home.rfidUID'))
        

#Adding auth check to other admin pages, secure model view built in
#is_accessible and inaccessible_callback are built in with Flask-Admin
#All model views will inherit from the custom view
class SecureModelView(ModelView):
    def is_accessible(self):
        return "AdminAccess" in session

    def inaccessible_callback(self, name, **kwargs):
        flash("You are not authorised to access this page.")
        return redirect(url_for('home.rfidUID'))


class ItemAdminView(SecureModelView):
    column_list = ['name', 'cost']
    column_sortable_list = ['name', 'cost']
    form_columns = ['name', 'cost']
    column_searchable_list = ['name']

class RFIDTagsAdminView(SecureModelView):
    column_list = ['rfid_uid']
    column_sortable_list = ['rfid_uid']
    form_columns = ['rfid_uid']
    column_searchable_list = ['rfid_uid']

class EmployeeAdminView(SecureModelView):
    column_list = ['name', 'pin']
    form_columns = ['name', 'pin']
    column_sortable_list = ['name']
    column_searchable_list = ['name']

class DispenserDetailsView(SecureModelView):
    column_list = ['id', 'product_name', 'cost_per_gram']
    form_columns = ['id', 'product_name', 'cost_per_gram']
    column_sortable_list = ['id', 'product_name', 'cost_per_gram']
    column_searchable_list = ['id', 'product_name']

class AccountAdminView(SecureModelView):
    column_list = ['email', 'name', 'rfid_uid', 'points', 'created_at']
    column_sortable_list = ['email', 'name', 'rfid_uid', 'points', 'created_at']
    form_columns = ['email', 'name', 'rfid_uid', 'points', 'created_at']
    column_searchable_list = ['email', 'name', 'rfid_uid']

    #Using flask session to store the rfid uid before it is updated
    def on_form_prefill(self, form, id):
        account = self.get_one(id)
        session['original_rfid_uid'] = account.rfid_uid #Gets original rfid_uid
        session.modified = True

    #Runs when account is updated/created
    def on_model_change(self, form, model, is_created):
        #Is created false means model is updated not new
        if not is_created:
            if 'rfid_uid' in form.data:
                print(f"Old RFID: {session.get('original_rfid_uid')}, New RFID: {form.data['rfid_uid']}")
                #If rfid_uid has been changed
                if model.rfid_uid != session.get('original_rfid_uid'):
                    #Get the previous rfid UID
                    oldRfidUID = session.get('original_rfid_uid')
                    #Get the new rfid UID
                    newRfidUID = model.rfid_uid
                    #Get account creation date
                    createdAt = model.created_at
                    #Get all current purchases attached to new rfid UID
                    purchasesToUpdate = db.session.query(Purchase).filter(Purchase.rfid_uid == oldRfidUID).all()
                    #Get archived purchases on or after account's creation date
                    archivedPurchasesToUpdate = db.session.query(ArchivedPurchase).filter(ArchivedPurchase.rfid_uid == oldRfidUID, ArchivedPurchase.archived_at >= createdAt).all()
                    #Update rfid UID for these purchases/archived purchases to maintain account history
                    for purchase in purchasesToUpdate:
                        purchase.rfid_uid = newRfidUID
                    for archivedPurchase in archivedPurchasesToUpdate:
                        archivedPurchase.rfid_uid = newRfidUID

                    #Check new tag UID is in RFIDTags table
                    newTagCheck = db.session.query(RFIDTags).filter_by(rfid_uid=newRfidUID).first()
                    #If new tag UID is not in RFIDTags table, add the tag
                    if newTagCheck is None:
                        addTag = RFIDTags(rfid_uid=newRfidUID)
                        db.session.add(addTag)

                    #Grab old tag
                    removeTag = db.session.query(RFIDTags).filter_by(rfid_uid=oldRfidUID).first()
                    #Remove tag if still in RFID tags table
                    if removeTag is not None:
                        db.session.delete(removeTag)

                    db.session.commit()
        #Will continue as normal for rest of the changes submitted
        return super(AccountAdminView, self).on_model_change(form, model, is_created)

