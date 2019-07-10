import sqlite3
import gc
import datetime
from flask import Flask, render_template, g, request, redirect, url_for, flash, session, redirect
from jobs.dbconnect import connection
from wtforms import Form, StringField, PasswordField, validators, BooleanField
from passlib.hash import sha256_crypt
from MySQLdb import escape_string as thwart
from functools import wraps

PATH = 'db/jobs.sqlite'

app = Flask(__name__)
app.secret_key = "super secret key"


def open_connection():
    connection = getattr(g, '_connection', None)
    if connection == None:
        connection = g._connection = sqlite3.connect(PATH)
    connection.row_factory = sqlite3.Row
    return connection

def execute_sql(sql, values=(), commit=False, single=False):
    connection = open_connection()
    cursor = connection.execute(sql, values)
    if commit == True:
        results = connection.commit()
    else:
        results = cursor.fetchone() if single else cursor.fetchall()

    cursor.close()
    return results


@app.teardown_appcontext
def close_connection(exception):
    connection = getattr(g, '_connection', None)
    if connection is not None:
        connection.close()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        logged_in = session.get('logged_in', False)
        if logged_in:
            return f(*args, **kwargs)
        else:
            flash("You need to login first.")
            next=url_for(request.endpoint,**request.view_args)
            return redirect(url_for('login_page', next=next))
    return wrapper


@app.route('/logout/')
@login_required
def logout_page():
    session.clear()
    flash("You have been logged out.")
    gc.collect()
    return redirect(url_for('jobs'))


@app.route('/login/', methods=['GET', 'POST'])
def login_page():
    try:
        c, conn = connection()
        error = ''
        if request.method == "POST":
            attempted_username = request.form['username']
            c.execute("SELECT * FROM users WHERE username=%s", (attempted_username,))
            user_data = c.fetchone()
            if user_data is not None:
                hashed_password = user_data[2]
                if sha256_crypt.verify(request.form['password'], hashed_password):  #pip install passlib ****
                    session['logged_in'] = True
                    session['username'] = attempted_username
                    flash("You are now logged in.")
                    next = request.args.get('next')
                    # is_safe_url should check if the url is safe for redirects.
                    # See http://flask.pocoo.org/snippets/62/ for an example.
                    #if not is_safe_url(next):
                    #    return flask.abort(400)
                    return redirect(next or url_for('jobs')) #return redirect(url_for('jobs'))
            error = "Invalid credentials. Try again."
            gc.collect()
        return render_template("login.html", error=error)

    except Exception as e:
        return render_template('login.html', error=e)		

@app.route('/')
@app.route('/jobs')
def jobs():
    jobs = execute_sql(
        'SELECT job.id, job.title, job.description, job.salary, employer.id as employer_id, employer.name as employer_name FROM job JOIN employer ON employer.id = job.employer_id')
    return render_template('index.html', jobs=jobs)


@app.route('/job/<job_id>')
def job(job_id):
    try:
        job = execute_sql('SELECT job.id, job.title, job.description, job.salary, employer.id as employer_id, employer.name as employer_name FROM job JOIN employer ON employer.id = job.employer_id WHERE job.id = ?',
                          [job_id], single=True)
        flash("flash test!!!!")
        return render_template('job.html', job=job)
    except Exception as e:
        return render_template("500.html", error=str(e))


@app.route('/employer/<employer_id>')
def employer(employer_id):
    employer = execute_sql('SELECT * FROM employer WHERE id=?',
                           [employer_id], single=True)
    jobs = execute_sql('SELECT job.id, job.title, job.description, job.salary FROM job JOIN employer ON employer.id = job.employer_id WHERE employer.id = ?',
                       [employer_id])
    reviews = execute_sql('SELECT review, rating, title, date, status FROM review JOIN employer ON employer.id = review.employer_id WHERE employer.id = ?',
                          [employer_id])
    return render_template('employer.html', employer=employer, jobs=jobs, reviews=reviews)


@app.route('/employer/<employer_id>/review', methods=('GET', 'POST'))
@login_required
def review(employer_id):
    if request.method == "POST":
        review = request.form['review']
        rating = request.form['rating']
        title = request.form['title']
        status = request.form['status']
        date = datetime.datetime.now().strftime("%m/%d/%Y")
        execute_sql('INSERT INTO review (review, rating, title, date, status, employer_id) VALUES (?, ?, ?, ?, ?, ?)',
                    (review, rating, title, date, status, employer_id), commit=True)

        return redirect(url_for('employer', employer_id=employer_id))

    return render_template('review.html', employer_id=employer_id)

# pip install flask-wtf -> required for form support
class RegistrationForm(Form):
    username = StringField('Username', [validators.Length(
        min=4, max=20), validators.DataRequired()])
    email = StringField('Email', [validators.Length(
        min=6, max=50), validators.Email(), validators.DataRequired()])
    password = PasswordField('Password', [validators.Length(min=8, max=16), validators.DataRequired(),
                                          validators.EqualTo('confirm', message="Password do not match.")])
    confirm = PasswordField('Repeat password')
    accept_tos = BooleanField(
        "I accept the <a href='/tos/'>Terms of Service</a> and the "
        "<a href='/privacy/'>Privacy Notice</a> (Last updated 12.07.18).", [validators.DataRequired()])


@app.route('/register/', methods=['GET', 'POST'])
def register_page():
    form = RegistrationForm(request.form)
    if request.method == "POST" and form.validate():
        username = form.username.data
        email = form.email.data
        password = sha256_crypt.encrypt((str(form.password.data)))
        c, conn = connection()
        c.execute("SELECT * FROM users WHERE username = (%s)",
                  [thwart(username)])

        if len(c.fetchall()) > 0:
            flash("That username is already taken.")
            return render_template("register.html", form=form)
        else:
            try:
                c.execute("INSERT INTO users (username, password, email, tracking) VALUES (%s, %s, %s, %s)",
                          [thwart(username), thwart(password), thwart(email), thwart("/introduction-to-python-programming/")])
                conn.commit()
                flash("Thanks for registering!")
                c.close()
                conn.close()
                gc.collect()

                session['logged_in'] = True
                session['username'] = username
                return redirect(url_for('jobs'))
            except Exception as e:
                flash(str(e))
                return render_template("register.html", form=form)

    return render_template("register.html", form=form)

# @app.route('/register/', methods=["GET","POST"])
# def register_page():
#     try:
#         c, conn = connection()
#         return("okay")
#     except Exception as e:
#         return(str(e))

# Error Handling block
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html")


@app.errorhandler(405)
def method_not_found(e):
    return render_template("405.html")

@app.route('/new')
def new():
    return render_template('new.html')
