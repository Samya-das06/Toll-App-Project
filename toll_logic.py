### START toll_logic.py ###
# toll_logic.py (Complete Corrected Version - 2025-04-12 v2)
import pandas as pd
import googlemaps
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import logging
from datetime import datetime

# Load environment variables at the start
load_dotenv()

# --- Configuration ---
# Ensure this matches the variable name in your .env file
# Using Maps_API_KEY for consistency with app.py examples
API_KEY = os.getenv('Maps_API_KEY')
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587)) # Use default if not set
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TOLL_DATA_FILE = 'final_toll_data.csv'
TOLL_RATE_PER_KM = 3.0 # Example rate

# --- Setup ---
logger = logging.getLogger(__name__)
# Configure root logger if not already done by Flask/basicConfig
# Avoid duplicate handlers if Flask already configures logging
# CORRECT line:
if not logging.getLogger().handlers: # Check only if root handlers are already set # Check both root and app logger
     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# Initialize Google Maps client safely
gmaps = None
if not API_KEY:
    # Use logger for critical errors
    logger.critical("CRITICAL: Google Maps API Key not found in environment variables (Maps_API_KEY). Geocoding/Distance will fail.")
else:
    try:
        gmaps = googlemaps.Client(key=API_KEY)
        logger.info("Google Maps client initialized successfully.")
    except Exception as e:
        logger.critical(f"CRITICAL: Failed to initialize Google Maps client: {e}", exc_info=True)
        # gmaps remains None

# --- IMPORTANT: Verify this section matches your CSV ---
# Define the column name from your CSV file that holds the toll identifiers
# >>>>>>>>>>>>>> !!! CHECK AND CHANGE THIS VALUE IF NEEDED !!! <<<<<<<<<<<<<<<<
CSV_IDENTIFIER_COLUMN = 'formatted_address'
# E.g., change to: CSV_IDENTIFIER_COLUMN = 'Toll_Plaza_Name'
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>><<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

TOLL_ZONE_IDENTIFIERS = set() # Initialize as empty set

try:
    logger.info(f"Attempting to load toll data from: {TOLL_DATA_FILE}")
    toll_zones_df = pd.read_csv(TOLL_DATA_FILE)
    logger.info(f"Successfully loaded CSV. Columns found: {list(toll_zones_df.columns)}")

    if CSV_IDENTIFIER_COLUMN in toll_zones_df.columns:
         # Load identifiers, convert to string, strip whitespace, store in a set
         # Handle potential NaN values before converting to string
         valid_identifiers = toll_zones_df[CSV_IDENTIFIER_COLUMN].dropna().astype(str).str.strip()
         # Filter out any potential empty strings after stripping
         TOLL_ZONE_IDENTIFIERS = set(valid_identifiers[valid_identifiers != ""].tolist())

         if not TOLL_ZONE_IDENTIFIERS:
              logger.warning(f"Column '{CSV_IDENTIFIER_COLUMN}' found, but contained no valid identifiers after processing in {TOLL_DATA_FILE}.")
         else:
              logger.info(f"Loaded {len(TOLL_ZONE_IDENTIFIERS)} unique, non-empty toll zone identifiers from column '{CSV_IDENTIFIER_COLUMN}'.")
              # Log the first few identifiers for verification (use debug level ideally)
              logger.debug(f"Sample identifiers: {list(TOLL_ZONE_IDENTIFIERS)[:5]}")
    else:
         # This is critical, use ERROR or CRITICAL level
         logger.critical(f"CRITICAL: Column '{CSV_IDENTIFIER_COLUMN}' not found in {TOLL_DATA_FILE}. Toll zone checking WILL FAIL.")

except FileNotFoundError:
    logger.critical(f"CRITICAL: Toll data file '{TOLL_DATA_FILE}' not found. Toll zone checking disabled.")
except pd.errors.EmptyDataError:
    logger.critical(f"CRITICAL: Toll data file '{TOLL_DATA_FILE}' is empty. Toll zone checking disabled.")
except Exception as e:
    logger.critical(f"CRITICAL: Error loading or processing toll data from '{TOLL_DATA_FILE}': {e}", exc_info=True)
# --- End CSV Verification Section ---


# --- Functions ---

def reverse_geocode(lat, lng):
    """Performs reverse geocoding using Google Maps API."""
    if not gmaps:
        logger.error("Google Maps client not initialized for reverse_geocode.")
        return None, "Geocoding Service Unavailable"
    try:
        logger.debug(f"Performing reverse geocode for ({lat}, {lng})")
        reverse_geocode_result = gmaps.reverse_geocode((lat, lng))
        if reverse_geocode_result:
            # Use the first result's formatted address
            formatted_address = reverse_geocode_result[0].get('formatted_address')
            if formatted_address:
                 logger.debug(f"Reverse geocode success for ({lat}, {lng}): '{formatted_address}'")
                 return formatted_address.strip(), None # Return stripped address and no error
            else:
                 logger.warning(f"Reverse geocoding result found, but 'formatted_address' key missing for ({lat}, {lng}). Result: {reverse_geocode_result[0]}")
                 return None, "Address format error"
        else:
            logger.warning(f"Reverse geocoding returned no results for ({lat}, {lng})")
            return None, "No address found"
    except googlemaps.exceptions.ApiError as e:
        logger.error(f"Google Maps API error during reverse geocode for ({lat},{lng}): {e}")
        return None, f"API Error: {e}"
    except Exception as e:
        # Corrected log message here
        logger.error(f"Unexpected error during reverse geocode for ({lat},{lng}): {e}", exc_info=False)
        return None, f"Network or Server Error: {e}"

# --- calc_dist function (Complete and Corrected) ---
def calc_dist(origin_coords, destination_coords):
    """ Calculates driving distance between two points."""
    if not gmaps:
        logger.error("Google Maps client not initialized for calc_dist.")
        return None
    # Basic validation of input coordinates
    if not (isinstance(origin_coords, (tuple, list)) and len(origin_coords) == 2 and
            isinstance(destination_coords, (tuple, list)) and len(destination_coords) == 2):
        logger.error(f"Invalid coordinate format for distance calculation. Origin: {origin_coords}, Dest: {destination_coords}")
        return None
    # Further validation can be added (e.g., check if lat/lon are numbers within valid ranges)

    try:
        logger.debug(f"Calculating distance from {origin_coords} to {destination_coords}")
        distance_matrix = gmaps.distance_matrix([origin_coords], [destination_coords], mode='driving')
        logger.debug(f"Distance Matrix API response status: {distance_matrix.get('status', 'N/A')}")

        # Check the overall status and element status robustly
        if distance_matrix.get('status') == 'OK' and \
           distance_matrix.get('rows') and \
           distance_matrix['rows'][0].get('elements') and \
           distance_matrix['rows'][0]['elements'][0].get('status') == 'OK':

            # Safely access distance value
            distance_info = distance_matrix['rows'][0]['elements'][0].get('distance')
            if distance_info and 'value' in distance_info:
                distance_value_meters = distance_info['value']
                # Handle potential non-numeric value although API usually guarantees int
                if isinstance(distance_value_meters, (int, float)):
                    distance_km = round(distance_value_meters / 1000.0, 2)
                    logger.info(f"Distance calculated: {distance_km} km")
                    return distance_km
                else:
                    logger.error(f"Distance value received is not numeric: {distance_value_meters}. Full element: {distance_matrix['rows'][0]['elements'][0]}")
                    return None
            else:
                logger.warning(f"Distance Matrix OK, but 'distance' or 'value' missing in element. Response Element: {distance_matrix['rows'][0]['elements'][0]}")
                return None
        else:
            # Log more detailed failure info
            error_status = distance_matrix.get('status', 'UNKNOWN_API')
            element_status = "N/A"
            if distance_matrix.get('rows') and distance_matrix['rows'][0].get('elements'):
                 element_status = distance_matrix['rows'][0]['elements'][0].get('status', 'UNKNOWN_ELEMENT')
            logger.warning(f"Distance matrix calculation failed. API Status: {error_status}, Element Status: {element_status}. Origin: {origin_coords}, Dest: {destination_coords}")
            return None

    # --- Added missing except blocks ---
    except googlemaps.exceptions.ApiError as e:
        logger.error(f"Google Maps API error during distance calculation for {origin_coords} -> {destination_coords}: {e}")
        return None
    except Exception as e:
        # Added colon and correct indentation for block below
        logger.error(f"Unexpected error during distance calculation for {origin_coords} -> {destination_coords}: {e}", exc_info=True)
        return None
    # --- End calc_dist function ---


# --- is_in_toll_zone function WITH DEBUG PRINTS ADDED ---
def is_in_toll_zone(lat, lng):
    """ Checks if the given coordinates fall within a known toll zone. """
    print(f"\n--- Checking is_in_toll_zone for ({lat}, {lng}) ---") # Using print for explicit debug step

    # Check upfront if identifiers loaded correctly
    if not TOLL_ZONE_IDENTIFIERS:
         print("DEBUG: is_in_toll_zone returning False (TOLL_ZONE_IDENTIFIERS set is empty or not loaded!)")
         return False

    # Print sample for verification during debugging
    print(f"DEBUG: Known Toll Zone Identifiers (sample): {list(TOLL_ZONE_IDENTIFIERS)[:5]}")
    print(f"DEBUG: Total known identifiers: {len(TOLL_ZONE_IDENTIFIERS)}")

    address, error = reverse_geocode(lat, lng)

    # Print geocoding result clearly
    print(f"DEBUG: Reverse geocode result: Address='{address}', Error='{error}'")

    if error:
        print(f"DEBUG: Geocoding error encountered: {error}")
        print(f"--- is_in_toll_zone returning False (due to geocode error) ---")
        return False

    if not address:
        print(f"DEBUG: No address returned by reverse geocode.")
        print(f"--- is_in_toll_zone returning False (no address found) ---")
        return False

    # Perform the check using exact match (strip whitespace from both sides)
    address = address.strip()
    print(f"DEBUG: Checking if Address '{address}' is in the known identifiers set.")
    # Check against the loaded set
    in_zone = address in TOLL_ZONE_IDENTIFIERS

    # --- Optional: Lenient check (uncomment if needed) ---
    if not in_zone:
        print(f"DEBUG: Exact match failed for '{address}'. Trying partial match...")
        partial_match_found = False
        for zone_id in TOLL_ZONE_IDENTIFIERS:
            # Ensure zone_id is not empty before checking 'in'
            if zone_id and zone_id in address:
                partial_match_found = True
                print(f"DEBUG: PARTIAL match found: Zone ID '{zone_id}' is IN Address '{address}'")
                break # Stop after first partial match
        if partial_match_found:
              in_zone = True
        else:
              print(f"DEBUG: Partial match also failed.")
    # --- End Optional Check ---

    print(f"--- is_in_toll_zone returning: {in_zone} ---")
    return in_zone
# --- End is_in_toll_zone function ---


# --- send_toll_bill_email function ---
def send_toll_bill_email(recipient_email, subject, entry_details, exit_details, distance_km, amount_due):
    """ Sends the toll bill email. """
    # Check for essential email config first
    if not all([EMAIL_ADDRESS, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT]):
        logger.error("Email configuration missing in .env file (EMAIL_ADDRESS, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT). Cannot send email.")
        print("ERROR: Email configuration missing in .env file.") # Also print for visibility
        return False
    if not recipient_email:
        logger.warning("send_toll_bill_email called with no recipient_email.")
        print("WARN: Attempted to send email with no recipient.")
        return False

    # Format body carefully, handling None values gracefully
    entry_addr = entry_details.get('address', 'N/A') if entry_details else 'N/A'
    entry_time = entry_details.get('timestamp', 'N/A') if entry_details else 'N/A'
    exit_addr = exit_details.get('address', 'N/A') if exit_details else 'N/A'
    exit_time = exit_details.get('timestamp', 'N/A') if exit_details else 'N/A'
    dist_str = f"{distance_km:.2f}" if distance_km is not None else "N/A"
    amount_str = f"{amount_due:.2f}" if amount_due is not None else "N/A"
    rate_str = f"{TOLL_RATE_PER_KM:.2f}" if TOLL_RATE_PER_KM is not None else "N/A"

    body = f"""Dear User,

A new toll charge has been calculated for your recent trip.

Entry Point: {entry_addr}
Entry Time: {entry_time}

Exit Point: {exit_addr}
Exit Time: {exit_time}

Distance Travelled: {dist_str} km
Toll Amount Due: INR {amount_str} (Rate: INR {rate_str}/km)

Please log in to the portal to view details and make payment.

Thank you,
Toll Road Authority
"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        logger.info(f"Attempting to send email to {recipient_email} via {SMTP_SERVER}:{SMTP_PORT}")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            # server.set_debuglevel(1) # Uncomment for detailed SMTP logs if needed
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, recipient_email, msg.as_string())
        logger.info(f"Toll bill email sent successfully to {recipient_email}")
        print(f"INFO: Toll bill email sent successfully to {recipient_email}") # Also print
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(f"SMTP Authentication Error for {EMAIL_ADDRESS}. Check credentials/settings (e.g., App Password for Gmail).")
        print(f"ERROR: SMTP Authentication Error for {EMAIL_ADDRESS}.")
        return False
    except Exception as e:
        logger.error(f"Error sending toll bill email to {recipient_email}: {e}", exc_info=True)
        print(f"ERROR: Error sending email to {recipient_email}: {e}")
        return False
# --- End send_toll_bill_email function ---


# --- calculate_toll function ---
def calculate_toll(distance_km):
    """Calculates toll based on distance and rate."""
    if distance_km is None or distance_km < 0:
        logger.warning(f"Calculating toll with invalid distance: {distance_km}. Returning 0.")
        return 0.0
    if TOLL_RATE_PER_KM is None:
        logger.error("TOLL_RATE_PER_KM is not set. Cannot calculate toll.")
        return 0.0
    # Ensure rate is numeric before multiplying
    try:
        rate = float(TOLL_RATE_PER_KM)
        return round(float(distance_km) * rate, 2)
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating toll. Invalid distance or rate. Distance: {distance_km}, Rate: {TOLL_RATE_PER_KM}. Error: {e}")
        return 0.0
# --- End calculate_toll function ---

### END toll_logic.py ###
