from flask import Flask, render_template, redirect, request
import pymongo

app = Flask(__name__)
connection_string = "mongodb://127.0.0.1"
connection = pymongo.MongoClient(connection_string)
database = connection.utauction
users = database.users
items = database.items

def valid_login(user, password):
	if users.find({'username': user, 'password': password}):
		return True
	else:
		return False


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/market/')
def market():
	return render_template('market.html')

@app.route('/item/')
def item():
	return render_template('item.html')

@app.route('/login/', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        user = {k : v for k,v in request.form.items()}
        cursor = users.find({'username': user['username'], 'password': user['password']})
    if cursor.count() == 0:
    	return render_template('index.html', alert="login-error")
    else:
    	return render_template('index.html', alert="login-success")

@app.route('/register/', methods=['POST', 'GET'])
def register():
	if request.method == 'POST':
		if request.form['password'] == request.form['confirm-password']:
			user = {k : v for k,v in request.form.items()}
			del user['confirm-password']
			users.insert(user)
			return render_template('index.html', alert = "registration-success")
		else:
			return render_template('index.html', alert = "registration-error")

if __name__ == '__main__':
    app.debug = True
    app.run()
