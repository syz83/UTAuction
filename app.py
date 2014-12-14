from flask import Flask, render_template, redirect, request
import pymongo
from bson.objectid import ObjectId
from flask_login import (LoginManager, login_required, login_user, 
                         current_user, logout_user, UserMixin)
from itsdangerous import URLSafeTimedSerializer
import md5

#Connect to database
app = Flask(__name__)
connection_string = "mongodb://127.0.0.1"
connection = pymongo.MongoClient(connection_string)
database = connection.utauction
users = database.users
items = database.items
app.secret_key = "mongodforthewin"

#Login_serializer used to encryt and decrypt the cookie token for the remember
#me option of flask-login
login_serializer = URLSafeTimedSerializer(app.secret_key)


#User model
class User(UserMixin):
	def __init__(self, username, password, sell_list, watch_list, active=True):
		self.id = username
		self.password = password
		self.active = active
		self.sell_list = sell_list
		self.watch_list = watch_list

	def get_auth_token(self):
		data = [str(self.id), self.password]
		return login_serializer.dumps(data)

	def sellItem(self, id):
		self.sell_list.append(id)
		users.update({"username": self.id}, {'$set': {"sell_list": self.sell_list}})
		return None

	def watchItem(self, id):
		self.watch_list.append(id)
		users.update({"username": self.id}, {'$set': {"watch_list": self.watch_list}})
		return None

	def removeFromSellList(self, id):
		self.sell_list.remove(ObjectId(id))
		users.update({"username": self.id}, {'$set': {"sell_list": self.sell_list}})
		return None

	def removeFromWatchList(self, id):
		return None


	@staticmethod
	def get(userid):
		cursor = users.find({"username": userid})
		if cursor.count() != 0:
			user = cursor.next()
			return User(user["username"], user["password"], user["sell_list"], user["watch_list"])
		return None

#Useful methods
def hash_pass(password):
	"""
	Return the md5 hash of the password+salt
	"""
	salted_password = password + app.secret_key
	return md5.new(salted_password).hexdigest()

def convert_to_dict(iterable):
	outer_dict = {}
	for element in iterable:
		inner_dict = {} 
		for key in element:
			inner_dict[key] = element[key]	
		outer_dict[element['_id']]= inner_dict
	return outer_dict



login_manager = LoginManager()
 
login_manager.login_view = "index"
login_manager.login_message = u"Please log in to access this page."
login_manager.refresh_view = "reauth"

login_manager.setup_app(app)

@login_manager.user_loader
def load_user(userid):
    return User.get(userid)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        user = {k : v for k,v in request.form.items()}
        cur_user = User.get(user["username"])
    if cur_user != None:
    	if hash_pass(user['password']) == cur_user.password:
    		login_user(cur_user)
    		return render_template('index.html', alert="login-success")
    	else:
    		return render_template('index.html', alert="login-wrong")
    else:
    	return render_template('index.html', alert="login-error")

@app.route('/logout', methods=['POST', 'GET'])
def logout():
	logout_user()
	return redirect('/')

@app.route('/register', methods=['POST', 'GET'])
def register():
	if request.method == 'POST':
		if request.form['password'] == request.form['confirm-password']:
			user = {k : v for k,v in request.form.items()}
			if users.find({"username": user['username']}).count() == 0:
				del user['confirm-password']
				user['password'] = hash_pass(user['password'])
				user['sell_list'] = []
				user['watch_list'] = []
				users.insert(user)
				return render_template('index.html', alert = "registration-success")
			else:
				return render_template('index.html', alert = "registration-duplicate")
		else:
			return render_template('index.html', alert = "registration-error")

@app.route('/market/')
@login_required
def market():
	all_items = items.find() 
	return render_template('market.html', all_items=all_items)

@app.route('/my_items/')
@login_required
def my_items():
	my_items=items.find({'userid': current_user.id})

	return render_template('my_items.html', my_items=my_items)

@app.route('/addItem', methods=['POST', 'GET'])
@login_required
def addItem():
	if request.method == 'POST':
		item = {k : v for k,v in request.form.items()}
		item['userid'] = current_user.id
		items.insert(item)
		current_user.sellItem(items.find(item).next()["_id"])
		my_items = items.find({'userid': current_user.id})
		return render_template('my_items.html', my_items=my_items)
	else:
		return render_template('my_items.html')

@app.route('/detail/<_id>')
def detail(_id):
	item = items.find_one({'_id':ObjectId(_id)})
	return render_template('detail.html', item=item)

@app.route('/watch/<_id>')
def watch(_id):
	current_user.watchItem(_id)
	item = items.find_one({'_id':ObjectId(_id)})
	return render_template('detail.html', item=item)

@app.route('/watch_list/')
def watch_list():
	watch_items = list()
	for id in current_user.watch_list:
		witem = items.find_one({"_id": ObjectId(id)})
		if witem != None:
			watch_items.append(witem)
	return render_template('watch.html', watch_items = watch_items)

@app.route('/buy/<_id>')
def buy(_id):
	seller = User.get(items.find({"_id": ObjectId(_id)}).next()["userid"])
	seller.removeFromSellList(_id)
	items.remove({"_id": ObjectId(_id)})
	return render_template('thankyou.html')

@app.route('/remove_from_watchlist/<_id>')
def remove_from_watchlist(_id):
	current_user.removeFromWatchList(_id)
	watch_items = list()
	for id in current_user.watch_list:
		witem = items.find_one({"_id": ObjectId(id)})
		if witem != None:
			watch_items.append(witem)
	return render_template('watch.html', watch_items = watch_items)

@app.route('/removeItem/<_id>')
def removeItem(_id):
	current_user.removeFromSellList(_id)
	items.remove({"_id": ObjectId(_id)})
	my_items = list()
	for itemid in current_user.sell_list:
		sitem = items.find_one({"_id": itemid})
		if sitem != None:
			my_items.append(sitem)
	return render_template('my_items.html', my_items=my_items)

@app.route('/update/<_id>', methods=['POST', 'GET'])
def updateItem(_id):
	if request.method == 'POST':
		item = {k : v for k,v in request.form.items()}
		items.update({'_id': ObjectId(_id)}, {'$set': item})
		my_items = items.find({'userid': current_user.id})
		return render_template('my_items.html', my_items=my_items)
	else:
		return render_template('my_items.html')

@app.route('/search/', methods=['POST', 'GET'])
def search():
	if request.method == 'POST':
		search_items = items.find({'title': request.form['title']})
		return render_template('search.html', search_items = search_items)
	else:
		return render_template('search.html')

if __name__ == '__main__':
    app.debug = True
    app.run()
