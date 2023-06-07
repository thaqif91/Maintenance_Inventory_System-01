from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from passlib.hash import sha256_crypt
from flask_sqlalchemy import SQLAlchemy
import pandas as pd

app = Flask(__name__)
app.config['SECRET_KEY'] = 'thisisscretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root@localhost/test'
# Initialize the Flask-Login extension
login_manager = LoginManager()
login_manager.init_app(app)

# Connect to the MySQL database
db = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="",
    database="test"
)

mycursor = db.cursor()


def get_data():
    query = "select * from inventory where status = 'active'"
    mycursor.execute(query)
    return mycursor.fetchall()


def select_data(id):
    query = f"SELECT * FROM inventory WHERE id = {id} and status = 'active'"
    mycursor.execute(query)
    return mycursor.fetchone()


def find_data(item):
    query = f"SELECT * FROM inventory WHERE parts='{item}' and status = 'active'"
    mycursor.execute(query)
    data = mycursor.fetchone()
    try:
        return data
    except TypeError:
        return None

def find_data_delete(item):
    query = f"SELECT * FROM inventory WHERE parts='{item}' and status = 'delete'"
    mycursor.execute(query)
    data = mycursor.fetchone()
    try:
        return data
    except TypeError:
        return None


# Define a User class that extends UserMixin
class User(UserMixin):
    def __init__(self, id):
        self.id = id


# Define a user_loader function that retrieves a User object from the user ID
@login_manager.user_loader
def user_loader(id):
    query = f"SELECT * FROM login WHERE id = {id} and status = 'active'"
    mycursor.execute(query)
    user = mycursor.fetchone()
    if user is None:
        return None
    else:
        return User(user[0])


@app.route("/")
@login_required
def home():
    return render_template("inv.html", data=get_data())


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name").title()
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm-password")
        query = f"SELECT * FROM login WHERE name = '{name}' and status = 'active'"
        mycursor.execute(query)
        user = mycursor.fetchone()
        if not user:
            query = "SELECT * FROM login ORDER BY id DESC LIMIT 1"
            mycursor.execute(query)
            last_user = mycursor.fetchone()
            try:
                last_workerid = last_user[3]
            except TypeError:
                last_workerid = 'M-000'
            generate_workerid = last_workerid[:-1] + str(int(last_workerid[-1]) + 1)
            if confirm_password == password:
                hash_password = sha256_crypt.encrypt(password)
                sql = f"INSERT INTO login (name, email, workerID, password, status) VALUES ('{name}', '{email}', '{generate_workerid}', '{hash_password}', 'active')"
                mycursor.execute(sql)
                db.commit()
                flash(f"Your signup is successful and your worker id is {generate_workerid}")
                return render_template("login.html")
            else:
                flash('Your confirm password is incorrect. Please reinsert the password')
        else:
            flash('Name already available, please use other name')
        return render_template("signup.html", name=name, email=email)
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        workerID = request.form.get("workerID")
        password = request.form.get("password")
        query = f"SELECT * FROM login WHERE workerID = '{workerID}' and status = 'active'"
        mycursor.execute(query)
        user = mycursor.fetchone()
        try:
            check_password = sha256_crypt.verify(password, user[4])
        except:
            flash("Worker ID not yet signup! Please signup first.")
            return render_template("login.html", error="Not yet signup!")
        if user and check_password:
            user_obj = User(user[0])
            login_user(user_obj)
            session['workerID'] = workerID
            session['id'] = user[0]
            flash(f"Welcome back {user[1]}")
            return redirect("/")
        else:
            flash("Wrong worker ID or password!")
            return render_template("login.html", error="Invalid username or password")
    else:
        return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")


@app.route("/check", methods=["POST", "GET"])
def check():
    if request.method == "POST":
        inv_name = request.form.get("inventory").title()
        if find_data(inv_name) == None:
            flash(f"'{inv_name}' not yet register in the database")
            return render_template("inv.html", item=inv_name, data=get_data())
        else:
            quantity = find_data(inv_name)[2]
            si_unit = find_data(inv_name)[3]
            flash(f"Current stock for '{inv_name}': {quantity} {si_unit}")
            return render_template("inv.html", item=inv_name, data=get_data())
    return redirect("/")


@app.route("/update", methods=['POST', 'GET'])
def update():
    try:
        inv_name = request.form.get("inventory").title()
    except AttributeError:
        list_inv = [get_data()[x][1].lower() for x in range(len(get_data()))]
        return render_template("register.html", list_inv=list_inv)
    if request.method == "POST":
        # try:
        if find_data(inv_name) == None:
            list_inv = [get_data()[x][1].lower() for x in range(len(get_data()))]
            return render_template("register.html", item=inv_name, list_inv=list_inv)
        else:
            flash(f"Item '{inv_name}' already register into database")
    return render_template("inv.html", item=inv_name, data=get_data())


@app.route("/updates/<item>/<quantity>/<unit>")
def updates(item, quantity, unit):
    flash(f"balance {item} is {quantity} {unit}")
    return render_template("update.html", item=find_data(item))


@app.route("/register", methods=['POST', 'GET'])
def register():
    if request.method == "POST":
        inv_name = request.form.get("inventory").title()
        quantity = int(request.form.get("quantity"))
        si_unit = request.form.get("selection")
        check_data = find_data(inv_name)
        check_delete_stock = find_data_delete(inv_name)
        if check_data is None:
            if check_delete_stock is None:
                # push to inventory
                sql = f"INSERT INTO inventory (parts, quantity, unit, status) VALUES ('{inv_name}', {quantity}, '{si_unit}', 'active')"
                mycursor.execute(sql)
                db.commit()
                # push to userLog
                sql1 = f"INSERT INTO userLog (workerId, userId, parts, qtyIn, unit, remarks) VALUES ('{session['workerID']}', '{session['id']}', '{inv_name}', {quantity}, '{si_unit}', 'new stock register')"
                mycursor.execute(sql1)
                db.commit()
                flash(f"Your new item '{inv_name}' for {quantity}{si_unit} was register successfully")
                return redirect("/")
            else:
                sql = f"UPDATE inventory SET quantity = {quantity}, unit= '{si_unit}', status = 'active' WHERE id = {check_delete_stock[0]}"
                mycursor.execute(sql)
                db.commit()
                return redirect("/")
        else:
            flash(f'Inventory {inv_name} already register in the database please check at the dashboard, or Please use other inventory name')
            return render_template("register.html")
    return redirect("/")


@app.route("/delete/<int:id>", methods=['POST', 'GET'])
def delete(id):
    # push to database
    sql = f"UPDATE inventory SET status = 'delete' WHERE id = {id}"
    # sql = f"DELETE from inventory WHERE id = {id}"
    mycursor.execute(sql)
    db.commit()
    print(f"{id}")
    return redirect("/")


@app.route("/add/<int:id>", methods=['POST', 'GET'])
def add(id):
    inv_name = request.form.get("inventory").title()
    quantity = int(request.form.get("quantity"))
    si_unit = request.form.get("selection")
    # push to database
    sql = f"UPDATE inventory SET quantity = quantity + {quantity} WHERE id = {id} and status = 'active'"
    mycursor.execute(sql)
    db.commit()
    # push to userLog
    sql1 = f"INSERT INTO userLog (workerId, userId, parts, qtyIn, unit, remarks) VALUES ('{session['workerID']}', '{session['id']}', '{inv_name}', {quantity}, '{si_unit}', 'Stock In')"
    mycursor.execute(sql1)
    db.commit()
    balance = find_data(inv_name)[2]
    flash(
        f"Your item '{inv_name}' was added {quantity} {si_unit} successfully and the update balance is {balance} {si_unit}")
    return redirect("/")


@app.route("/sub/<int:id>", methods=['POST', 'GET'])
def sub(id):
    inv_name = request.form.get("inventory").title()
    quantity = int(request.form.get("quantity"))
    si_unit = request.form.get("selection")
    machine = request.form.get("selection1")
    # push to database
    sql = f"UPDATE inventory SET quantity = quantity - {quantity} WHERE id = {id} and status = 'active'"
    mycursor.execute(sql)
    db.commit()
    # push to userLog
    sql1 = f"INSERT INTO userLog (workerId, userId, parts, qtyOut, unit, remarks) VALUES ('{session['workerID']}', '{session['id']}', '{inv_name}', {quantity}, '{si_unit}', '{machine}')"
    mycursor.execute(sql1)
    db.commit()
    balance = find_data(inv_name)[2]
    flash(
        f"Your item '{inv_name}' was takeout {quantity} {si_unit} successfully and the update balance is {balance} {si_unit}")
    return redirect("/")

@app.route("/csv", methods=['POST', 'GET'])
def save_csv():
    data = get_data()
    df = pd.DataFrame(data)
    df.columns = ['Id','Items', 'Quantity', 'Unit', 'Status', 'Date Registered']
    d = df.iloc[:,[1,2,3,4]]
    d.to_csv(r'/Users/muhammadthaqif/Downloads/data.csv', index=False, sep='\t')
    # d.to_excel('raw_data.xls', index=False)
    flash("Your csv file was successfully downloads")
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True, port=1080)
