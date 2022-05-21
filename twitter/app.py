import datetime


from flask import Flask
from flask import g
from flask import jsonify
from flask import redirect
from flask import request
from flask import session
from flask import url_for, abort, render_template, flash
from functools import wraps
from hashlib import md5
from peewee import *
from forms import ParcelForm
# config - aside from our database, the rest is for use by Flask
DATABASE = 'tweepee.db'
DEBUG = True
SECRET_KEY = 'hin6bab8ge25*r=x&amp;+5$0kn=-#log$pt^#@vrqjld!^2ci@g*b'

# create a flask application - this ``app`` object will be used to handle
# inbound requests, routing them to the proper 'view' functions, etc
app = Flask(__name__)
app.config.from_object(__name__)

# create a peewee database instance -- our models will use this database to
# persist information
database = SqliteDatabase(DATABASE)

# model definitions -- the standard "pattern" is to define a base model class
# that specifies which database to use.  then, any subclasses will automatically
# use the correct storage. for more information, see:
# https://charlesleifer.com/docs/peewee/peewee/models.html#model-api-smells-like-django
class BaseModel(Model):
    class Meta:
        database = database

# the user model specifies its fields (or columns) declaratively, like django
class User(BaseModel):
    username = CharField(unique=True)
    password = CharField()
    email = CharField()
    join_date = DateTimeField()

    # it often makes sense to put convenience methods on model instances, for
    # example, "give me all the users this user is following":
    def following(self):
        # query other users through the "relationship" table
        return (User
                .select()
                .join(Relationship, on=Relationship.to_user)
                .where(Relationship.from_user == self)
                .order_by(User.username))

    def followers(self):
        return (User
                .select()
                .join(Relationship, on=Relationship.from_user)
                .where(Relationship.to_user == self)
                .order_by(User.username))

    def is_following(self, user):
        return (Relationship
                .select()
                .where(
                    (Relationship.from_user == self) &
                    (Relationship.to_user == user))
                .exists())

    def gravatar_url(self, size=80):
        return 'http://www.gravatar.com/avatar/%s?d=identicon&s=%d' % \
            (md5(self.email.strip().lower().encode('utf-8')).hexdigest(), size)


# this model contains two foreign keys to user -- it essentially allows us to
# model a "many-to-many" relationship between users.  by querying and joining
# on different columns we can expose who a user is "related to" and who is
# "related to" a given user
class Relationship(BaseModel):
    from_user = ForeignKeyField(User, backref='relationships')
    to_user = ForeignKeyField(User, backref='related_to')

    class Meta:
        indexes = (
            # Specify a unique multi-column index on from/to-user.
            (('from_user', 'to_user'), True),
        )


# a dead simple one-to-many relationship: one user has 0..n parcels, exposed by
# the foreign key.  because we didn't specify, a users parcels will be accessible
# as a special attribute, User.parcel_set
class Parcel(BaseModel):
    user = ForeignKeyField(User, backref='parcels')
    parcelnumber = TextField()
    sendername = TextField()
    sendermobilenumber = TextField()
    senderaddress = TextField()
    receivername = TextField()
    receivermobilenumber = TextField()
    receiveraddress = TextField()
    parcelweight = DecimalField()
    amount = DecimalField()
    pub_date = DateTimeField()
    destination_branch = IntegerField()
    is_received_at_destination = BitField()
    is_delivered_to_receiever = BitField()
    def tojson(self):
        return {"parcelnumber": self.parcelnumber,
                "sendername": self.sendername,
                "sendermobilenumber": self.sendermobilenumber}


# simple utility function to create tables
def create_tables():
    with database:
        database.create_tables([User, Relationship, Parcel])

# flask provides a "session" object, which allows us to store information across
# requests (stored by default in a secure cookie).  this function allows us to
# mark a user as being logged-in by setting some values in the session data:
def auth_user(user):
    session['logged_in'] = True
    session['user_id'] = user.id
    session['username'] = user.username
    flash('You are logged in as %s' % (user.username))

# get the user from the session
def get_current_user():
    if session.get('logged_in'):
        return User.get(User.id == session['user_id'])

# view decorator which indicates that the requesting user must be authenticated
# before they can access the view.  it checks the session to see if they're
# logged in, and if not redirects them to the login view.
def login_required(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return inner

# given a template and a SelectQuery instance, render a paginated list of
# objects from the query inside the template
def object_list(template_name, qr, var_name='object_list', **kwargs):
    kwargs.update(
        page=int(request.args.get('page', 1)),
        pages=qr.count() / 20 + 1)
    kwargs[var_name] = qr.paginate(kwargs['page'])
    return render_template(template_name, **kwargs)

# retrieve a single object matching the specified query or 404 -- this uses the
# shortcut "get" method on model, which retrieves a single object or raises a
# DoesNotExist exception if no matching object exists
# https://charlesleifer.com/docs/peewee/peewee/models.html#Model.get)
def get_object_or_404(model, *expressions):
    try:
        return model.get(*expressions)
    except model.DoesNotExist:
        abort(404)

def convertTuple(tup):
    st = ''.join(map(str, tup))
    return st

# custom template filter -- flask allows you to define these functions and then
# they are accessible in the template -- this one returns a boolean whether the
# given user is following another user.
@app.template_filter('is_following')
def is_following(from_user, to_user):
    return from_user.is_following(to_user)

# Request handlers -- these two hooks are provided by flask and we will use them
# to create and tear down a database connection on each request.
@app.before_request
def before_request():
    g.db = database
    g.db.connect(reuse_if_open = True)

@app.after_request
def after_request(response):
    g.db.close()
    return response

# views -- these are the actual mappings of url to view function
@app.route('/')
def homepage():
    # depending on whether the requesting user is logged in or not, show them
    # either the public timeline or their own private timeline
    if session.get('logged_in'):
        return private_timeline()
    else:
        return parcels()

@app.route('/private/')
def private_timeline():
    # the private timeline exemplifies the use of a subquery -- we are asking for
    # parcels where the person who created the parcel is someone the current
    # user is following.  these parcels are then ordered newest-first.
    user = get_current_user()
    parcels = (Parcel
                .select()
                .where(Parcel.user << user.following())
                .order_by(Parcel.pub_date.desc()))
    return object_list('private_parcels.html', parcels, 'parcel_list')

@app.route('/parcels/')
def parcels():
    # simply display all parcels, newest first
    parcels = Parcel.select().order_by(Parcel.pub_date.desc())
    return object_list('parcels.html', parcels, 'parcel_list')

@app.route('/join/', methods=['GET', 'POST'])
def join():
    if request.method == 'POST' and request.form['username']:
        try:
            with database.atomic():
                # Attempt to create the user. If the username is taken, due to the
                # unique constraint, the database will raise an IntegrityError.
                user = User.create(
                    username=request.form['username'],
                    password=md5((request.form['password']).encode('utf-8')).hexdigest(),
                    email=request.form['email'],
                    join_date=datetime.datetime.now())

            # mark the user as being 'authenticated' by setting the session vars
            auth_user(user)
            return redirect(url_for('homepage'))

        except IntegrityError:
            flash('That username is already taken')

    return render_template('join.html')

@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['username']:
        try:
            pw_hash = md5(request.form['password'].encode('utf-8')).hexdigest()
            user = User.get(
                (User.username == request.form['username']) &
                (User.password == pw_hash))
        except User.DoesNotExist:
            flash('The password entered is incorrect')
        else:
            auth_user(user)
            return redirect(url_for('homepage'))

    return render_template('login.html')

@app.route('/logout/')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out')
    return redirect(url_for('homepage'))

@app.route('/following/')
@login_required
def following():
    user = get_current_user()
    return object_list('user_following.html', user.following(), 'user_list')

@app.route('/followers/')
@login_required
def followers():
    user = get_current_user()
    return object_list('user_followers.html', user.followers(), 'user_list')

@app.route('/users/')
def user_list():
    users = User.select().order_by(User.username)
    return object_list('user_list.html', users, 'user_list')

@app.route('/users/<username>/')
def user_detail(username):
    # using the "get_object_or_404" shortcut here to get a user with a valid
    # username or short-circuit and display a 404 if no user exists in the db
    user = get_object_or_404(User, User.username == username)

    # get all the users parcels ordered newest-first -- note how we're accessing
    # the parcels -- user.parcel_set.  could also have written it as:
    # Parcel.select().where(Parcel.user == user)
    parcels = user.parcels.order_by(Parcel.pub_date.desc())
    return object_list('user_detail.html', parcels, 'parcel_list', user=user)

@app.route('/users/<username>/follow/', methods=['POST'])
@login_required
def user_follow(username):
    user = get_object_or_404(User, User.username == username)
    try:
        with database.atomic():
            Relationship.create(
                from_user=get_current_user(),
                to_user=user)
    except IntegrityError:
        pass

    flash('You are following %s' % user.username)
    return redirect(url_for('user_detail', username=user.username))

@app.route('/users/<username>/unfollow/', methods=['POST'])
@login_required
def user_unfollow(username):
    user = get_object_or_404(User, User.username == username)
    (Relationship
     .delete()
     .where(
         (Relationship.from_user == get_current_user()) &
         (Relationship.to_user == user))
     .execute())
    flash('You are no longer following %s' % user.username)
    return redirect(url_for('user_detail', username=user.username))

@app.route('/create/', methods=['GET', 'POST'])
@login_required
def create():
    user = get_current_user()
    if request.method == 'POST' and  request.form['sendername'] and request.form['receivermobilenumber']:
        parcel = Parcel.create(
            user=user,
            sendername = request.form['sendername'],
            sendermobilenumber = request.form['sendermobilenumber'],
            senderaddress = request.form['senderaddress'],
            receivername = request.form['receivername'],
            receivermobilenumber = request.form['receivermobilenumber'],
            receiveraddress = request.form['receiveraddress'],
            parcelweight = request.form['parcelweight'],
            amount = request.form['amount'],
            parcelnumber = request.form['parcelnumber'],
            destination_branch = request.form['destination_branch'],
            is_received_at_destination = False,
            is_delivered_to_receiever = False,
            pub_date=datetime.datetime.now())
        flash('Parcel info has been created')
        return redirect(url_for('parcels'))

    return render_template('create.html')

@app.route('/editparcel/<int:id>', methods=['GET', 'POST'])
def editparcel(id):

    parcel = get_object_or_404(Parcel, Parcel.id == id)
    form = ParcelForm(formdata=request.form, obj=parcel)
    form.is_received_at_destination.checked = parcel.is_received_at_destination
    form.is_delivered_to_receiever.checked = parcel.is_delivered_to_receiever
    if request.method == 'POST':

        parcel.is_received_at_destination = request.form.get('is_received_at_destination',False)
        parcel.is_delivered_to_receiever = request.form.get('is_delivered_to_receiever',False)
        parcel.save()
        return redirect(url_for('parcels', id=id))
    else:
        return render_template('update.html', form=form)

@app.route('/parcels/<parcelid>/')
def parcel_detail(parcelid):
    # using the "get_object_or_404" shortcut here to get a parcel with a valid
    # parcelid or short-circuit and display a 404 if no parcel exists in the db
    parcel = get_object_or_404(Parcel, Parcel.parcelnumber == parcelid)

    return jsonify(parcel.tojson())

@app.context_processor
def _inject_user():
    return {'current_user': get_current_user()}

# allow running from the command line
if __name__ == '__main__':
    create_tables()
    app.run(host="127.0.0.1", port=8000, debug=True)
