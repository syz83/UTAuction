from flask import Flask, render_template, redirect, request
from cassandra.cluster import Cluster
import uuid
from bson.objectid import ObjectId
from flask_login import (LoginManager, login_required, login_user, 
                         current_user, logout_user, UserMixin)
from itsdangerous import URLSafeTimedSerializer
import md5

app = Flask(__name__)
#Connect to database
cluster = Cluster()

session = cluster.connect('keyspace1')

table_users = "users"

table_items = "items"

session.execute("CREATE TABLE IF NOT EXISTS %s(id uuid, username text, password text, watch_list list<text>, primary key(id, username));"%table_users)

session.execute("CREATE TABLE IF NOT EXISTS %s(id uuid, userid text, title text, price text, description text, primary key(id, userid));"%table_items)

app.secret_key = "mongodforthewin"

#Login_serializer used to encryt and decrypt the cookie token for the remember
#me option of flask-login
login_serializer = URLSafeTimedSerializer(app.secret_key)


#User model
class User(UserMixin):
	def __init__(self, username, password, watch_list, active=True):
		self.id = username
		self.password = password
		self.active = active
		if(watch_list == None):
			self.watch_list = []
		else:
			self.watch_list = watch_list

	def get_auth_token(self):
		data = [str(self.id), self.password]
		return login_serializer.dumps(data)

	def watchItem(self, id):
		self.watch_list.append(id)
		watch_item_query = session.prepare("UPDATE users SET watch_list=? WHERE id=? and username=?")
		primaryid = session.execute("SELECT id FROM users WHERE username=%s ALLOW FILTERING", (current_user.id))
		session.execute(watch_item_query, (self.watch_list, primaryid[0].id, current_user.id))
		return None

	def removeFromWatchList(self, id):
		self.watch_list.remove(id)
		watch_item_query = session.prepare("UPDATE users SET watch_list=? WHERE id=? and username=?")
		primaryid = session.execute("SELECT id FROM users WHERE username=%s ALLOW FILTERING", (current_user.id))
		session.execute(watch_item_query, (self.watch_list, primaryid[0].id, current_user.id))
		return None

	@staticmethod
	def get(userid):
		select_statement = session.prepare("SELECT * FROM users WHERE username=? ALLOW FILTERING")
		user = session.execute(select_statement, [userid])
		if user:
			return User(user[0].username, user[0].password, user[0].watch_list)
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
		outer_dict[element['id']]= inner_dict
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

@app.route('/market/')
@login_required
def market():
	all_items = session.execute("SELECT * FROM items")
	return render_template('market.html', all_items = all_items)

@app.route('/detail/<id>')
def detail(id):
	item = session.execute("SELECT * FROM items WHERE id=" + id)[0]
	return render_template('detail.html', item=item)

@app.route('/my_items/')
@login_required
def my_items():
	item_query = session.prepare("SELECT * FROM items WHERE userid=? ALLOW FILTERING")
	item_rows = session.execute(item_query, [current_user.id])
	my_items = list()
	for item in item_rows:
		my_items.append(item)
	return render_template('my_items.html', my_items=my_items)

@app.route('/addItem', methods=['POST', 'GET'])
@login_required
def addItem():
	if request.method == 'POST':
		item = {k : v for k,v in request.form.items()}
		item['userid'] = current_user.id
		id = uuid.uuid4()
		insert_item = "INSERT INTO items (id, userid, title, price, description) values("+str(id)+", %s, %s, %s, %s) IF NOT EXISTS"
		session.execute(insert_item, (current_user.id, item['title'], item['price'], item['description']))
		my_items = list()
		for item in item_rows:
			my_items.append(item) 

		return render_template('my_items.html', my_items=my_items)
	else:
		return render_template('my_items.html')

@app.route('/watch/<id>')
def watch(id):
	current_user.watchItem(id)
	item = session.execute("SELECT * FROM items WHERE id=" + id)[0]
	return render_template('detail.html', item=item)

@app.route('/watch_list/')
def watch_list():
	watch_items = list()
	for id in current_user.watch_list:
		witem = session.execute("SELECT * FROM items WHERE id=" + id)
		if witem:
			watch_items.append(witem[0])
	return render_template('watch.html', watch_items = watch_items)

@app.route('/remove_from_watchlist/<id>')
def remove_from_watchlist(id):
	current_user.removeFromWatchList(id)
	watch_items = list()
	for id in current_user.watch_list:
		witem = session.execute("SELECT * FROM items WHERE id=" + id)
		if witem:
			watch_items.append(witem[0])
	return render_template('watch.html', watch_items = watch_items)

@app.route('/removeItem/<id>')
def removeItem(id):
	session.execute("DELETE FROM items where id=" + id)
	item_query = session.prepare("SELECT * FROM items WHERE userid=? ALLOW FILTERING")
	item_rows = session.execute(item_query, [current_user.id])
	my_items = list()
	for item in item_rows:
		my_items.append(item)
	return render_template('my_items.html', my_items=my_items)

@app.route('/buy/<id>')
def buy(id):
	session.execute("DELETE FROM items where id=" + id)
	return render_template('thankyou.html')


@app.route('/update/<id>', methods=['POST', 'GET'])
def updateItem(id):
	if request.method == 'POST':
		item = {k : v for k,v in request.form.items()}
		old_item = session.execute("SELECT title, price, description FROM items WHERE id=" + id)
		update_sell_item = session.prepare("UPDATE items SET title=?, price=?, description=? WHERE userid=? and id=" + id + " IF title=? and price=? and description=?")
		session.execute(update_sell_item, (item['title'], item['price'], item['description'], current_user.id, old_item[0].title, old_item[0].price, old_item[0].description))
		item_query = session.prepare("SELECT * FROM items WHERE userid=? ALLOW FILTERING")
		item_rows = session.execute(item_query, [current_user.id])
		my_items = list()
		for item in item_rows:
			my_items.append(item)
		return render_template('my_items.html', my_items=my_items)
	else:
		return render_template('my_items.html')

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
			id = uuid.uuid4()
			insert_statement = "INSERT INTO "+table_users+"(id, username, password, watch_list) values("+str(id)+", %s, %s, %s) IF NOT EXISTS"
			session.execute(insert_statement, (user['username'], hash_pass(user['password']), []))	
		else:
			return render_template('index.html', alert = "registration-error")

		
if __name__ == '__main__':
    app.debug = True
    app.run()
