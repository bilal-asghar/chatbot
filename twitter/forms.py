from wtforms import Form, StringField, SelectField,DecimalField,BooleanField

class ParcelForm(Form):
    destination_branches = [('1', 'Saddar Branch Rawalpindi'),
                   ('2', 'Blue Area Branch Islamabad'),
                   ('3', 'Nazimabad Branch Karachi'),
                   ('4', 'City Branch Jhelum'),
                   ('5', 'Cantt Branch Multan'),
                   ]
    sendername = StringField('Sender Name', render_kw={'readonly': True})
    sendermobilenumber = StringField('Sender Mobile Number', render_kw={'readonly': True})
    senderaddress = StringField('Sender Address', render_kw={'readonly': True})
    receivername = StringField('Receiver Name', render_kw={'readonly': True})
    receivermobilenumber = StringField('Receiver Mobile Number', render_kw={'readonly': True})
    receiveraddress = StringField('Receiver Address', render_kw={'readonly': True})
    parcelweight = DecimalField('Weight', render_kw={'readonly': True})
    amount = DecimalField('Amount', render_kw={'readonly': True})
    is_received_at_destination= BooleanField = BooleanField('Received at Destination')
    is_delivered_to_receiever = BooleanField('Delivered to Receiver')
    destination_branch = SelectField('Destination Branch', choices=destination_branches, render_kw={'readonly': True})
