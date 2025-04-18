from flask import Flask
import os
from routes.checkoutroutes import *
from routes.homeroutes import *
from routes.receiptroutes import *
from routes.refundroutes import *
from flask_admin import Admin
from flask_admin.menu import MenuLink
from admin_views import *
from extensions import db
from models import *

def createApp(testConfig=None):
   app = Flask(__name__)
   app.config['SECRET_KEY'] = 'secretkey123'   

   #For unit testing
   if testConfig is None:
      #Creating the flask alchemy database 
      sqlitePath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'purchases.db')
      app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+sqlitePath
   else:
      app.config.update(testConfig)

   app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

   db.init_app(app)

   app.register_blueprint(checkoutBlueprint, url_prefix='/checkout')
   app.register_blueprint(homeBlueprint, url_prefix='/home')
   app.register_blueprint(receiptBlueprint, url_prefix='/receipt')
   app.register_blueprint(refundBlueprint, url_prefix="/refund")


   admin = Admin(app, name='Admin Dashboard', template_mode='bootstrap4', index_view= CustomAdminIndexView())
   admin.add_view(AccountAdminView(Account, db.session))
   admin.add_view(ItemAdminView(Item, db.session))
   admin.add_view(RFIDTagsAdminView(RFIDTags, db.session))
   admin.add_view(EmployeeAdminView(Employee, db.session))
   admin.add_view(DispenserDetailsView(DispenserDetails, db.session))
   admin.add_link(MenuLink(name='Logout', category='', url='/home/employee_logout'))

   return app

if __name__ == "__main__":
   app = createApp()
   app.run(debug=True)