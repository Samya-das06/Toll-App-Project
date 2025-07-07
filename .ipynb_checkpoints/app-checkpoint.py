### START app.py ###
# app.py (Complete Corrected Version - 2025-04-12)
import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime
import logging

# Import database models and toll logic functions
# Ensure models.py and toll_logic.py are in the same directory or accessible
try:
    from models import db, User, TollRecord, Query
    import toll_logic
except ImportError as e:
    logging.error(f"Failed to import models or toll_logic: {e}")
    # Optionally exit or raise a more specific error if these are critical
    raise

# Load environment variables
load_dotenv()

# Basic logging configuration
# Configure root logger if not already done elsewhere (like basicConfig in toll_logic)
if not logging.getLogger().handlers:
     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Flask App Configuration ---
app = Flask(__name__)

# --- Context Processor for Year ---
@app.context_processor
def inject_current_year():
    """Injects the current year into all templates."""
    return {'current_year': datetime.utcnow().year}

# --- App Config ---
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a_very_secure_default_secret_key_CHANGE_ME') # Use env var or secure default
if not app.config['SECRET_KEY'] or app.config['SECRET_KEY'] == 'default-fallback-secret-key' or app.config['SECRET_KEY'] == 'a_very_secure_default_secret_key_CHANGE_ME':
     logger.warning("WARNING: SECRET_KEY is using a default or insecure value. Set a strong SECRET_KEY environment variable for production.")

# Using absolute path as workaround for relative path issues in this environment
# IMPORTANT: Ensure this path is correct for your machine
DB_PATH = 'C:\\Users\\KIIT\\Documents\\Mini Project\\toll_app\\instance\\database.db' # Check this path carefully
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
logger.info(f"Using database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")


# --- Initialize Extensions ---
try:
    db.init_app(app)
    migrate = Migrate(app, db)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login' # Redirect here if @login_required fails
    login_manager.login_message_category = 'info' # Flash message category
except Exception as e:
     logger.error(f"Error initializing Flask extensions: {e}", exc_info=True)
     raise

# --- User Loader for Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    """Loads user based on user_id stored in session."""
    logger.debug(f"Attempting to load user with ID: {user_id}")
    try:
        user = User.query.get(int(user_id))
        if user:
            logger.debug(f"User {user_id} loaded successfully.")
        else:
            logger.warning(f"User ID {user_id} not found in database.")
        return user
    except (TypeError, ValueError):
        logger.warning(f"Invalid user_id format received in session: {user_id}")
        return None
    except Exception as e:
         logger.error(f"Error loading user {user_id}: {e}", exc_info=True)
         return None


# --- Helper Function ---
def get_active_toll_entry(user_id):
    """Finds the most recent toll entry record for a user that hasn't been closed."""
    logger.debug(f"Getting active toll entry for user_id: {user_id}")
    try:
        return TollRecord.query.filter_by(user_id=user_id, is_entry_only=True).order_by(TollRecord.entry_timestamp.desc()).first()
    except Exception as e:
        logger.error(f"Error getting active toll entry for user {user_id}: {e}", exc_info=True)
        return None

# --- Routes ---
@app.route('/')
def index():
    """Redirects to dashboard if logged in, otherwise to login."""
    logger.debug(f"Accessing index route. User authenticated: {current_user.is_authenticated}")
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        logger.debug("User already authenticated, redirecting to dashboard.")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        logger.debug(f"Login attempt for username: {username}")

        if not username or not password:
             flash('Username and password are required.', 'warning')
             return redirect(url_for('login'))

        try:
            # Use lowercase comparison for username if desired (optional)
            # user = User.query.filter(db.func.lower(User.username) == username.lower()).first()
            user = User.query.filter_by(username=username).first()

            if not user or not check_password_hash(user.password_hash, password):
                logger.warning(f"Failed login attempt for username: {username}")
                flash('Please check your login details and try again.', 'danger')
                return redirect(url_for('login'))

            login_user(user, remember=remember)
            flash(f'Welcome back, {user.username}!', 'success')
            logger.info(f"User {user.username} logged in successfully.")
            next_page = request.args.get('next')
            # TODO: Add validation for next_page to prevent open redirect vulnerabilities
            if next_page:
                 logger.debug(f"Redirecting logged in user to originally requested page: {next_page}")
                 return redirect(next_page)
            else:
                 logger.debug("Redirecting logged in user to dashboard.")
                 return redirect(url_for('dashboard'))

        except Exception as e:
             logger.error(f"Error during login process for user {username}: {e}", exc_info=True)
             flash('An internal error occurred during login. Please try again.', 'danger')
             return redirect(url_for('login'))

    # Handle GET request
    logger.debug("Serving login page.")
    return render_template('login.html', title="Login")

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles new user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        logger.info(f"Registration attempt for username: {username}, email: {email}")

        # Basic Validation
        if not all([username, email, password, confirm_password]):
            flash('All fields are required.', 'warning')
            return redirect(url_for('register'))
        if password != confirm_password:
            flash('Passwords do not match.', 'warning')
            return redirect(url_for('register'))
        if len(password) < 6:
             flash('Password must be at least 6 characters.', 'warning')
             return redirect(url_for('register'))
        # TODO: Add email format validation

        try:
            existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
            if existing_user:
                logger.warning(f"Registration failed: Username '{username}' or email '{email}' already exists.")
                flash('Username or email already exists.', 'warning')
                return redirect(url_for('register'))

            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = User(username=username, email=email, password_hash=hashed_password)

            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            logger.info(f"New user registered successfully: {username}")
            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error during registration for {username}: {e}", exc_info=True)
            flash('An error occurred during registration. Please try again.', 'danger')
            return redirect(url_for('register'))

    # Handle GET request
    return render_template('register.html', title="Register")

@app.route('/logout')
@login_required
def logout():
    """Logs the current user out."""
    logger.info(f"User {current_user.username} logging out.")
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- THIS IS THE DASHBOARD FUNCTION THE BuildError WAS COMPLAINING ABOUT ---
@app.route('/dashboard')
@login_required
def dashboard():
    """Displays the user dashboard with toll summaries."""
    logger.debug(f"Fetching dashboard data for user: {current_user.username} (ID: {current_user.id})")
    try:
        # Fetch ONLY unpaid tolls with exit points for the main display
        unpaid_tolls = TollRecord.query.filter_by(
            user_id=current_user.id,
            paid=False,
            is_entry_only=False # Ensure it's a completed trip record
        ).order_by(TollRecord.exit_timestamp.desc()).all()
        logger.debug(f"Found {len(unpaid_tolls)} unpaid toll records.")

        # Fetch recent paid tolls (optional)
        paid_tolls = TollRecord.query.filter_by(
            user_id=current_user.id,
            paid=True
        ).order_by(TollRecord.payment_timestamp.desc()).limit(10).all()
        logger.debug(f"Found {len(paid_tolls)} paid toll records (limit 10).")


        # Calculate total due from unpaid records
        total_due = sum(toll.amount_due for toll in unpaid_tolls if toll.amount_due)
        # Calculate total distance from those same unpaid records
        total_unpaid_distance = sum(toll.distance_km for toll in unpaid_tolls if toll.distance_km)
        logger.debug(f"Calculated total_due: {total_due}, total_unpaid_distance: {total_unpaid_distance}")

    except Exception as e:
         logger.error(f"Error fetching dashboard data for user {current_user.username}: {e}", exc_info=True)
         flash('Could not load dashboard data. Please try again later.', 'danger')
         unpaid_tolls = []
         paid_tolls = []
         total_due = 0
         total_unpaid_distance = 0

    return render_template('dashboard.html', title="Dashboard",
                           unpaid_tolls=unpaid_tolls,
                           paid_tolls=paid_tolls,
                           total_due=total_due,
                           total_unpaid_distance=total_unpaid_distance
                           )
# --- END OF DASHBOARD FUNCTION ---

@app.route('/map_test')
@login_required
def map_test():
    """Serves the map testing page."""
    logger.debug(f"Serving map test page for user: {current_user.username}")
    return render_template('map_test.html', title="Map Testing")

@app.route('/payment')
@login_required
def payment():
     """Displays a separate payment page."""
     logger.debug(f"Fetching payment page data for user: {current_user.username}")
     try:
         unpaid_tolls = TollRecord.query.filter_by(user_id=current_user.id, paid=False, is_entry_only=False).order_by(TollRecord.exit_timestamp.desc()).all()
         total_due = sum(toll.amount_due for toll in unpaid_tolls if toll.amount_due)
     except Exception as e:
         logger.error(f"Error fetching payment data for user {current_user.username}: {e}", exc_info=True)
         flash('Could not load payment data. Please try again later.', 'danger')
         unpaid_tolls = []
         total_due = 0
     return render_template('payment.html', title="Make Payment", unpaid_tolls=unpaid_tolls, total_due=total_due)

@app.route('/pay_bill/<int:toll_id>', methods=['POST'])
@login_required
def pay_bill(toll_id):
    """Simulates paying a specific toll bill."""
    logger.info(f"Processing payment attempt for toll ID {toll_id} by user {current_user.username}")
    try:
        # Ensure the toll record belongs to the current user and is unpaid
        toll_record = TollRecord.query.filter_by(id=toll_id, user_id=current_user.id, paid=False).first()
        if not toll_record:
            logger.warning(f"Payment attempt failed: Invalid or already paid toll record ID {toll_id} for user {current_user.username}")
            flash('Invalid toll record or already paid.', 'warning')
            return redirect(url_for('dashboard'))

        # --- SIMULATED PAYMENT ---
        toll_record.paid = True
        toll_record.payment_timestamp = datetime.utcnow()
        db.session.commit() # Commit the change
        logger.info(f"Toll record {toll_id} marked as paid for user {current_user.username}.")
        flash(f'Payment successful for toll record ID {toll_id}!', 'success')
        # -------------------------

    except Exception as e:
        db.session.rollback() # Rollback on error during payment processing
        logger.error(f"Error processing payment for toll record {toll_id}: {e}", exc_info=True)
        flash('An error occurred while processing payment.', 'danger')

    # Redirect back to dashboard after payment attempt
    return redirect(url_for('dashboard'))

@app.route('/query', methods=['GET', 'POST'])
@login_required
def query_page():
    """Handles user queries about tolls."""
    if request.method == 'POST':
        subject = request.form.get('subject')
        message = request.form.get('message')
        toll_record_id_str = request.form.get('toll_record_id')
        logger.info(f"Received query submission from user {current_user.username}. Subject: {subject}, Toll ID linked: {toll_record_id_str or 'None'}")

        if not subject or not message:
            flash('Please provide both subject and message for your query.', 'warning')
            return redirect(url_for('query_page'))

        # Optional: Validate toll_record_id if provided
        toll_record_id = None
        if toll_record_id_str:
            try:
                toll_record_id_check = int(toll_record_id_str)
                # Check if this toll_id actually belongs to the user and is valid
                record_exists = TollRecord.query.filter_by(id=toll_record_id_check, user_id=current_user.id).first()
                if record_exists:
                    toll_record_id = toll_record_id_check # Use the valid integer ID
                    logger.debug(f"Query linked to valid toll record ID: {toll_record_id}")
                else:
                    logger.warning(f"Query submitted with invalid/unowned toll record ID: {toll_record_id_str}")
                    flash('Invalid Toll Record ID selected.', 'warning')
                    # Don't link, but maybe still allow query submission? Or redirect?
                    # For now, just proceed without linking
            except ValueError:
                 flash('Invalid Toll Record ID format.', 'warning')
                 logger.warning(f"Query submitted with non-integer toll record ID: {toll_record_id_str}")
                 # Proceed without linking

        try:
            # Create query
            new_query = Query(user_id=current_user.id, subject=subject, message=message)
            # TODO: If your Query model has a toll_record_id field, set it here:
            # if toll_record_id:
            #    new_query.toll_record_id = toll_record_id

            db.session.add(new_query)
            db.session.commit()
            flash('Your query has been submitted successfully.', 'success')
            logger.info(f"Query submitted successfully by user {current_user.username} (Query ID: {new_query.id})")
            # TODO: Optionally send notification email to admin about the new query
            return redirect(url_for('dashboard'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving query for user {current_user.username}: {e}", exc_info=True)
            flash('An error occurred while submitting your query. Please try again.', 'danger')
            return redirect(url_for('query_page'))

    # GET request: Fetch user's unpaid tolls to optionally link query
    logger.debug(f"Serving query page for user: {current_user.username}")
    try:
        unpaid_tolls = TollRecord.query.filter_by(user_id=current_user.id, paid=False, is_entry_only=False).order_by(TollRecord.exit_timestamp.desc()).all()
    except Exception as e:
         logger.error(f"Error fetching unpaid tolls for query page for user {current_user.username}: {e}", exc_info=True)
         flash('Could not load toll records for query linking.', 'warning')
         unpaid_tolls = []
    return render_template('query.html', title="Submit Query", unpaid_tolls=unpaid_tolls)

# --- API Endpoint for Location Updates (WITH DEBUG PRINTS ADDED) ---
@app.route('/api/update_location', methods=['POST'])
@login_required
def api_update_location():
    """Receives location updates, processes toll logic."""
    data = request.get_json()
    if not data or 'latitude' not in data or 'longitude' not in data:
        logger.warning(f"Invalid location data received from user {current_user.username}: {data}")
        return jsonify({"status": "error", "message": "Invalid data format"}), 400

    try:
        lat = float(data.get('latitude'))
        lon = float(data.get('longitude'))
        timestamp = datetime.utcnow() # Use server time
    except (TypeError, ValueError) as e:
        logger.warning(f"Invalid lat/lon format received from user {current_user.username}: {data} - Error: {e}")
        return jsonify({"status": "error", "message": "Invalid latitude/longitude format"}), 400


    # --- DEBUG PRINTS START ---
    print("-" * 20) # Separator for easier reading
    print(f"DEBUG: Received location from user {current_user.username}: Lat={lat}, Lon={lon}")

    try:
        # Core Toll Logic Integration
        # The actual check happens inside is_in_toll_zone (which now has prints)
        current_location_is_toll = toll_logic.is_in_toll_zone(lat, lon)
        # Debug print for result is now inside toll_logic.is_in_toll_zone

        active_entry = get_active_toll_entry(current_user.id)
        print(f"DEBUG: Active entry found in DB: {active_entry.id if active_entry else None}")

        if current_location_is_toll and not active_entry:
            # --- User Entered Toll Zone ---
            print("DEBUG: Condition met: Entering toll zone.")
            entry_address, geo_error = toll_logic.reverse_geocode(lat, lon)
            print(f"DEBUG: Entry Reverse Geocode: Address='{entry_address}', Error='{geo_error}'")
            if geo_error:
                 logger.error(f"Geocoding error on entry for user {current_user.username}: {geo_error}")

            new_entry = TollRecord(
                user_id=current_user.id, entry_lat=lat, entry_lon=lon,
                entry_address=entry_address or "Address Unavailable",
                entry_timestamp=timestamp, is_entry_only=True
            )
            db.session.add(new_entry)
            db.session.commit()
            # Check if id is populated after commit
            entry_id = new_entry.id if new_entry else 'N/A' # Should have ID after commit
            print(f"DEBUG: New entry record {entry_id} committed.")

        elif not current_location_is_toll and active_entry:
            # --- User Exited Toll Zone ---
            print("DEBUG: Condition met: Exiting toll zone.")
            # Check if entry coords exist before proceeding
            if active_entry.entry_lat is None or active_entry.entry_lon is None:
                 logger.error(f"Cannot calculate exit for record {active_entry.id}: Missing entry coordinates.")
                 print(f"ERROR: Cannot calculate exit for record {active_entry.id}: Missing entry coordinates.")
                 # Decide how to handle this - maybe mark as error? For now, just return success without processing exit.
                 return jsonify({"status": "success", "message": "Location processed, but cannot finalize exit due to missing entry data."})


            exit_address, geo_error = toll_logic.reverse_geocode(lat, lon)
            print(f"DEBUG: Exit Reverse Geocode: Address='{exit_address}', Error='{geo_error}'")
            if geo_error:
                logger.error(f"Geocoding error on exit for user {current_user.username}: {geo_error}")

            origin_coords = (active_entry.entry_lat, active_entry.entry_lon)
            destination_coords = (lat, lon)

            distance_km = toll_logic.calc_dist(origin_coords, destination_coords)
            amount_due = toll_logic.calculate_toll(distance_km)
            print(f"DEBUG: Calculated Distance: {distance_km} km, Amount: {amount_due} INR")

            # Update the existing entry record
            active_entry.exit_lat = lat
            active_entry.exit_lon = lon
            active_entry.exit_address = exit_address or "Address Unavailable"
            active_entry.exit_timestamp = timestamp
            active_entry.distance_km = distance_km if distance_km is not None else 0.0
            active_entry.amount_due = amount_due if amount_due is not None else 0.0
            active_entry.paid = False
            active_entry.is_entry_only = False # Mark as complete record
            db.session.commit()
            print(f"DEBUG: Finalized toll record {active_entry.id} committed.")

            # Send email bill (Ensure email details are correct in .env)
            try:
                entry_details = {
                    'address': active_entry.entry_address,
                    'timestamp': active_entry.entry_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') if active_entry.entry_timestamp else 'N/A'
                }
                exit_details = {
                    'address': active_entry.exit_address,
                    'timestamp': active_entry.exit_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') if active_entry.exit_timestamp else 'N/A'
                }
                subject = f"Toll Charge Notification - Record ID {active_entry.id}"
                # Ensure current_user has an email attribute
                recipient = current_user.email if hasattr(current_user, 'email') else None
                if recipient:
                     toll_logic.send_toll_bill_email(
                         recipient_email=recipient,
                         subject=subject,
                         entry_details=entry_details,
                         exit_details=exit_details,
                         distance_km=active_entry.distance_km or 0.0,
                         amount_due=active_entry.amount_due or 0.0
                     )
                else:
                     logger.warning(f"Cannot send email for record {active_entry.id}: User {current_user.id} has no email address.")
                     print(f"WARN: Cannot send email for record {active_entry.id}: User has no email address.")

            except Exception as mail_error:
                 # Log email errors but don't let them crash the request
                 logger.error(f"Failed to send toll bill email for record {active_entry.id}: {mail_error}", exc_info=True)
                 print(f"ERROR: Failed to send email: {mail_error}")

        else:
             # Condition where no state change occurs
             print(f"DEBUG: No state change detected. Still {'inside' if active_entry else 'outside'} zone ({'toll=True' if current_location_is_toll else 'toll=False'}).")

        return jsonify({"status": "success", "message": "Location processed"})
        # --- DEBUG PRINTS END ---

    except Exception as e:
        # Catch unexpected errors in the main processing block
        db.session.rollback() # Rollback DB changes on error
        logger.exception(f"CRITICAL Error processing location update for user {current_user.username}: {e}") # Log full exception
        print(f"ERROR: CRITICAL Exception during location update processing: {e}") # Print error too
        # Return a generic server error message to the client
        return jsonify({"status": "error", "message": "An internal server error occurred processing the location."}), 500

# --- CLI Command to Create User (Corrected Structure) ---
@app.cli.command("create-user")
def create_user():
    """Creates a default user for testing."""
    username = input("Enter username: ")
    email = input("Enter email: ")
    password = input("Enter password: ")
    confirm_password = input("Confirm password: ")

    if not all([username, email, password, confirm_password]):
        print("All fields are required.")
        return
    if password != confirm_password:
        print("Passwords do not match.")
        return

    # Check if user/email exists *before* proceeding
    try:
        existing = User.query.filter((User.username == username) | (User.email == email)).first()
    except Exception as e:
         print(f"Database error checking existing user: {e}")
         logger.error(f"DB error checking existing user {username}/{email}: {e}", exc_info=True)
         return # Exit if cannot query database

    if existing:
        print("Username or email already exists.")
        return

    # Hash password and create user object
    try:
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password_hash=hashed_password)

        # Add the user object ONCE
        db.session.add(new_user)

        # Now, immediately try to commit and handle errors
        db.session.commit()
        print(f"User {username} created successfully.")

    except Exception as e:
        # This block handles errors during hashing, add, or commit
        db.session.rollback() # Roll back changes on error
        print(f"Error creating user: {e}")
        logger.error(f"Error creating user {username}: {e}", exc_info=True)

# --- End create-user correction ---


# --- Run the App (for development) ---
if __name__ == '__main__':
    # The lines for creating instance folder and db.create_all() are removed/commented out

    # Run using Flask's built-in server (for development only!)
    # Note: Ensure FLASK_DEBUG is set in .env or pass debug=True directly if needed
    is_debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 't']
    logger.info(f"Starting Flask app (Debug Mode: {is_debug_mode})...")
    # Consider adding error handling around app.run if needed, though less common
    app.run(debug=is_debug_mode, host='0.0.0.0', port=5001)

### END app.py ###