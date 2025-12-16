from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime
import os

# --- Application and Database Configuration ---
app = Flask(__name__)
app.secret_key = 'your_secret_key_here_for_security'

# Set absolute path for the database file to prevent location errors
# CẤU HÌNH MỚI (PostgreSQL - Dùng biến môi trường)
# Đọc URL database từ biến môi trường của Render
# Đọc URL database từ biến môi trường
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # 1. Xử lý schema: thay thế 'postgres://' bằng 'postgresql://' (SQLAlchemy yêu cầu)
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    # 2. Xử lý SSL (QUAN TRỌNG: Khắc phục lỗi SSL error trên Render)
    # Thêm tham số truy vấn 'sslmode=require' để buộc kết nối SSL an toàn
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL + '?sslmode=require'
else:
    # Fallback cho môi trường phát triển cục bộ (local development)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reservations.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Đảm bảo bạn đã import os ở đầu file
import os

# --- FLASK-MAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.materes.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
# !!! REPLACE WITH YOUR SENDING EMAIL ADDRESS !!!
app.config['MAIL_USERNAME'] = 'contact@materes.com'
# !!! REPLACE WITH YOUR APP PASSWORD (highly recommended for Gmail) !!!
app.config['MAIL_PASSWORD'] = 'Chipchip_2017'
app.config['MAIL_DEFAULT_SENDER'] = 'contact@materes.com'

db = SQLAlchemy(app)
mail = Mail(app)


# --- Reservation Model Definition (FINAL) ---
class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)  # Required
    date = db.Column(db.String(10), nullable=False)
    time = db.Column(db.String(5), nullable=False)
    guests = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Pending', nullable=False)
    dietary_restrictions = db.Column(db.String(255), nullable=True)  # Checkbox data
    special_request = db.Column(db.Text, nullable=True)  # Text area data

    def __repr__(self):
        return f'<Reservation {self.id} - {self.name} - {self.date} {self.time}>'


# --- Create Database Tables if they don't exist ---
with app.app_context():
    db.create_all()


# --- ADMIN EMAIL NOTIFICATION FUNCTION ---
def send_admin_notification_email(reservation_data):
    subject = f'NEW RESERVATION PENDING #{reservation_data.id} - {reservation_data.name}'
    recipient = app.config['MAIL_USERNAME']

    diet_info = reservation_data.dietary_restrictions if reservation_data.dietary_restrictions else 'None'
    request_info = reservation_data.special_request if reservation_data.special_request else 'None'

    body = f"""
    Dear Manager,

    You have a new booking request that needs to be processed:
    Booking ID: {reservation_data.id}
    Customer Name: {reservation_data.name}
    Phone: {reservation_data.phone}
    Email: {reservation_data.email}
    Date/Time: {reservation_data.date} at {reservation_data.time}
    Number of Guests: {reservation_data.guests}
    Dietary Restrictions: {diet_info}
    Special Requests: {request_info}
    Status: PENDING

    Please visit the admin page to confirm: {url_for('admin', _external=True)}
    """

    try:
        msg = Message(subject, recipients=[recipient], body=body)
        mail.send(msg)
        print(f"DEBUG: Sent new booking notification email to manager.")
    except Exception as e:
        print(f"ERROR SENDING ADMIN EMAIL: {e}")


# --- CUSTOMER CONFIRMATION EMAIL FUNCTION ---
def send_confirmation_email_to_customer(reservation_data):
    if not reservation_data.email:
        print(f"DEBUG: Did not send confirmation email to customer #{reservation_data.id}. No email provided.")
        return

    subject = f'BOOKING CONFIRMED #{reservation_data.id} AT THE RESTAURANT'

    body = f"""
    Dear {reservation_data.name},

    Your reservation has been SUCCESSFULLY CONFIRMED!

    Booking Details:
    --------------------------------------------------
    Booking ID: {reservation_data.id}
    Date: {reservation_data.date}
    Time: {reservation_data.time}
    Number of Guests: {reservation_data.guests}
    Dietary Restrictions: {reservation_data.dietary_restrictions if reservation_data.dietary_restrictions else 'None'}
    Special Requests: {reservation_data.special_request if reservation_data.special_request else 'None'}
    Status: CONFIRMED
    --------------------------------------------------
    We look forward to welcoming you.
    """

    try:
        msg = Message(subject, recipients=[reservation_data.email], body=body)
        mail.send(msg)
        print(f"DEBUG: Sent confirmation email to customer {reservation_data.email}.")
    except Exception as e:
        print(f"ERROR SENDING CUSTOMER CONFIRMATION EMAIL: {e}")


# --- CUSTOMER DENIAL EMAIL FUNCTION (HÀM MỚI) ---
def send_denial_email_to_customer(reservation_data):
    if not reservation_data.email:
        print(f"DEBUG: Did not send denial email to customer #{reservation_data.id}. No email provided.")
        return

    subject = f'IMPORTANT: RESERVATION #{reservation_data.id} UPDATE'

    body = f"""
    Dear {reservation_data.name},

    We regret to inform you that your reservation request (ID: #{reservation_data.id}) 
    for {reservation_data.date} at {reservation_data.time} has been DENIED.

    This may be due to the restaurant being fully booked at that specific time, 
    or issues with the submitted details.

    You are welcome to submit a new reservation request for a different date or time.

    Thank you for your understanding.
    """

    try:
        msg = Message(subject, recipients=[reservation_data.email], body=body)
        mail.send(msg)
        print(f"DEBUG: Sent denial email to customer {reservation_data.email}.")
    except Exception as e:
        print(f"ERROR SENDING CUSTOMER DENIAL EMAIL: {e}")


# --- Reservation Handling Route (GET/POST) ---
@app.route('/', methods=['GET', 'POST'])
def reservation():
    if request.method == 'POST':
        try:
            name = request.form['name']
            phone = request.form['phone']
            email = request.form['email']
            date = request.form['date']
            time = request.form['time']
            guests = int(request.form['guests'])

            diet_list = request.form.getlist('diet')
            diet_restrictions = ", ".join(diet_list)

            special_request = request.form.get('special_request')

            # Validation: All required fields must be present
            if not (name and phone and email and date and time and guests > 0):
                flash('Please fill in all required fields completely and correctly.', 'error')
                return redirect(url_for('reservation'))

            # Save to database
            new_reservation = Reservation(
                name=name,
                phone=phone,
                email=email,
                date=date,
                time=time,
                guests=guests,
                dietary_restrictions=diet_restrictions,
                special_request=special_request
            )

            db.session.add(new_reservation)
            db.session.commit()

            # Send admin notification email
            send_admin_notification_email(new_reservation)

            flash(
                f'Booking successful! Booking ID: #{new_reservation.id}. Please check your email for confirmation later.',
                'success')

            return redirect(url_for('reservation'))

        except Exception as e:
            db.session.rollback()
            flash(f'A system error occurred: {e}', 'error')
            return redirect(url_for('reservation'))

    return render_template('reservation.html')


# --- Admin Route ---
@app.route('/admin')
def admin():
    all_reservations = Reservation.query.order_by(Reservation.id.desc()).all()
    return render_template('admin.html', reservations=all_reservations)


# --- CONFIRM BOOKING Route ---
@app.route('/confirm/<int:res_id>', methods=['POST'])
def confirm_reservation(res_id):
    reservation_to_confirm = Reservation.query.get_or_404(res_id)

    if reservation_to_confirm.status == 'Confirmed':
        flash(f'Booking ID #{res_id} has already been confirmed.', 'warning')
        return redirect(url_for('admin'))

    try:
        # 1. Update status in database
        reservation_to_confirm.status = 'Confirmed'
        db.session.commit()

        # 2. Send confirmation email to customer
        send_confirmation_email_to_customer(reservation_to_confirm)

        flash(f'Successfully CONFIRMED booking ID #{res_id} and sent notification email to the customer.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error confirming booking ID #{res_id}: {e}', 'error')

    return redirect(url_for('admin'))


# --- Delete Booking Route (POST) ---
@app.route('/delete/<int:res_id>', methods=['POST'])
def delete_reservation(res_id):
    reservation_to_delete = Reservation.query.get_or_404(res_id)

    try:
        db.session.delete(reservation_to_delete)
        db.session.commit()
        flash(f'Booking ID #{res_id} successfully deleted.', 'success')
    except:
        db.session.rollback()
        flash('Could not delete the booking.', 'error')

    return redirect(url_for('admin'))


# ... (Phần trên không đổi) ...

# --- DENY BOOKING Route (HÀM MỚI) ---
@app.route('/deny/<int:res_id>', methods=['POST'])
def deny_reservation(res_id):
    reservation_to_deny = Reservation.query.get_or_404(res_id)

    if reservation_to_deny.status in ['Confirmed', 'Denied']:
        flash(f'Booking ID #{res_id} cannot be denied as its current status is "{reservation_to_deny.status}".',
              'warning')
        return redirect(url_for('admin'))

    try:
        # 1. Update status in database
        reservation_to_deny.status = 'Denied'
        db.session.commit()

        # 2. Send denial email to customer
        send_denial_email_to_customer(reservation_to_deny)

        flash(f'Successfully DENIED booking ID #{res_id} and sent notification email to the customer.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error denying booking ID #{res_id}: {e}', 'error')

    return redirect(url_for('admin'))


# ... (Các route khác không đổi) ...


if __name__ == '__main__':
    app.run()