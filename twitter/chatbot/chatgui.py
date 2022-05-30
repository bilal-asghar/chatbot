import nltk
from nltk.stem import WordNetLemmatizer
lemmatizer = WordNetLemmatizer()
import pickle
import numpy as np
import urllib.request
import requests
import json
from keras.models import load_model
model = load_model('chatbot_model.h5')
import json
import random
intents = json.loads(open('intents.json').read())
words = pickle.load(open('words.pkl','rb'))
classes = pickle.load(open('classes.pkl','rb'))


def getDeliveryDates():
    excluded = (6, 7)
    d = datetime.datetime.now() + datetime.timedelta(days=1)
    end = datetime.datetime.now() + datetime.timedelta(days=7)
    print("date: ", d)
    days = []
    session['chatlog'].append('please select date')
    while d <= end:
        if d.isoweekday() not in excluded:
            days.append(d.strftime('%m/%d/%Y'))
            # days = days + '1) ' + d.strftime('%m/%d/%Y') + '\n\n'
        d += datetime.timedelta(days=1)
    return days



def chatbot_response(msg):

    if(len(msg) == 6 and  session['schedulestep'] == 0):
        url = 'http://127.0.0.1:8000/parcels/653212'
        r = requests.get(url)
        print(json.loads(r.content))
        data = json.loads(r.content)
        print("sender name: ", data['sendername'])
        session['schedulestep'] = 1
        session['dates'] = getDeliveryDates()
        return 'order sent by :' + data['sendername']
        #return '1'

    if(session['isReceiver'] and session['schedulestep'] == 1):
        if(msg == 'pickup'):
          return  'Pickup parcel from Branch between 9AM to 10PM'
        elif(msg == 'delivery'):
            session['schedulestep'] = 2
            session['isdeliveryopted'] = True
            return 'Please enter your street number/name'
        else:
            return 'Please enter valid response'

    if (session['isReceiver'] and session['schedulestep'] == 2):
        if (msg.isnumeric()):
            session['schedulestep'] = 3
            session['street'] = msg
            return 'Please enter your office/house number'
        elif (len(msg) > 5):   #name validation atleast 6 characters in name
            session['schedulestep'] = 3
            session['street'] = msg
            return 'Please enter your office/house number'
        else:                  #validation failed
            return 'Please enter valid street number/name'

    if (session['isReceiver'] and session['schedulestep'] == 3):
        if (msg.isnumeric()):
            session['schedulestep'] = 4
            session['house'] = msg
            session['dates'] = getDeliveryDates()
            return 'Please select delivery date'
        else:  # validation failed
            return 'Please enter valid office/house number'


    return ""


#Creating GUI with tkinter


import datetime
from flask import Flask
from flask import g
from flask import jsonify
from flask import redirect
from flask import request
from flask import session
from flask import url_for, abort, render_template, flash

SECRET_KEY = 'hin6bab8ge25*r=x&amp;+5$0kn=-#log$pt^#@vrqjld!^2ci@g*b'

chatapp = Flask(__name__)
chatapp.config.from_object(__name__)

# get the parcel from the session
def get_parcel_number():
    if session.get('isValidParcel'):
        return session['parcelNumber']

# views -- these are the actual mappings of url to view function
@chatapp.route('/')
def homepage():
    # depending on whether the requesting user is logged in or not, show them
    # either the public timeline or their own private timeline
    if session.get('logged_in'):
        return "delivery chatbot"
    else:
        return "delivery chatbot"

@chatapp.route('/parcels/<parcelid>/')
def parcel_detail(parcelid):
    url = 'http://127.0.0.1:8000/parcels/'+parcelid
    r = requests.get(url)
    print(json.loads(r.content))
    data = json.loads(r.content)
    session['isValidParcel'] = True
    session['isReceiver'] = True
    session['parcelNumber'] = parcelid
    session['schedulestep'] = 0
    chatlog = ["Bot: your parcel is ready to deliver"]
    session['chatlog'] = chatlog
    session['schedulestep'] = 1
    session['chatlog'].append("Bot: you will pickup from branch or you need delivery?")
    print("sender name: ", data['sendername'])
    return render_template('chatui.html')
    #return 'order sent by :' + data['sendername']


@chatapp.route('/deliverydetails/', methods=['GET', 'POST'])
def deliverydetails():

    if request.method == 'POST' and request.form['message']:
      #  parcel = Parcel.create(
       #     sendername = request.form['message'],
       #     pub_date=datetime.datetime.now())
        last_log = session['chatlog']
        session['chatlog'].append("You: "+request.form['message'])
        res = chatbot_response(request.form['message'])
        session['chatlog'].append("Bot: " + res)

        #flash('Parcel delivery info has been updated')
        return render_template('chatui.html')
        #return redirect(url_for('user_detail', username=user.username))
    else:

     return render_template('chatui.html')


if __name__ == '__main__':
    chatapp.run()