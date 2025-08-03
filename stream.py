import streamlit as st
import time
from datetime import datetime, time as dt_time
import RPi.GPIO as GPIO
import board
import adafruit_dht

# --- Page and Hardware Configuration ---

# Set up the Streamlit page with a modern look
st.set_page_config(
    page_title="HydroVerde Control",
    page_icon="🌿",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Define GPIO pins
RELAY_PIN = 17
DHT_PIN = board.D4  # This corresponds to GPIO 4

# --- Caching for Hardware Initialization ---

@st.cache_resource
def setup_gpio():
    """Initializes GPIO settings for the relay. Cached to run only once."""
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAY_PIN, GPIO.OUT)
    GPIO.output(RELAY_PIN, GPIO.HIGH)  # Default to OFF (HIGH signal)
    print("GPIO setup complete.")
    return RELAY_PIN

@st.cache_resource
def setup_dht_sensor():
    """Initializes the DHT11 sensor. Cached to run only once."""
    try:
        dht_device = adafruit_dht.DHT11(DHT_PIN)
        print("DHT11 Sensor setup complete.")
        return dht_device
    except Exception as e:
        st.error(f"Failed to initialize DHT sensor: {e}")
        return None

# Initialize hardware
RELAY_PIN = setup_gpio()
dht_device = setup_dht_sensor()

# --- Session State Initialization ---

if "relay_state" not in st.session_state:
    st.session_state.relay_state = {
        "start_time": dt_time(5, 30),
        "end_time": dt_time(9, 30),
        "status": "OFF"
    }
if "sensor_data" not in st.session_state:
    st.session_state.sensor_data = {
        "temperature": "N/A",
        "humidity": "N/A"
    }
# Add state for manual override
if "manual_override" not in st.session_state:
    st.session_state.manual_override = False

# --- Core Logic Functions ---

def read_sensor_data():
    """Reads temperature and humidity from the DHT sensor and updates session state."""
    if dht_device is None:
        return
    try:
        # Read from the sensor
        temperature = dht_device.temperature
        humidity = dht_device.humidity
        # Update state only if readings are valid
        if temperature is not None and humidity is not None:
            st.session_state.sensor_data["temperature"] = f"{temperature}°C"
            st.session_state.sensor_data["humidity"] = f"{humidity}%"
    except RuntimeError as error:
        # DHT sensors can be finicky. This handles read errors without crashing.
        print(f"DHT Sensor Read Error: {error.args[0]}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def check_and_control_relay():
    """Checks the current time against the schedule and controls the relay.
       This function is SKIPPED if manual override is active."""
    # If manual override is on, don't run the schedule logic
    if st.session_state.manual_override:
        return

    now = datetime.now().time()
    state = st.session_state.relay_state
    start, end = state["start_time"], state["end_time"]

    is_on_schedule = False
    # Case 1: Overnight schedule (e.g., 22:00 to 06:00)
    if start > end:
        if now >= start or now < end:
            is_on_schedule = True
    # Case 2: Same-day schedule (e.g., 09:00 to 17:00)
    else:
        if start <= now < end:
            is_on_schedule = True

    # Update GPIO and state if needed
    if is_on_schedule and state["status"] == "OFF":
        GPIO.output(RELAY_PIN, GPIO.LOW)  # Turn ON
        st.session_state.relay_state["status"] = "ON"
        print(f"Relay turned ON by schedule at {now.strftime('%H:%M:%S')}")

    elif not is_on_schedule and state["status"] == "ON":
        GPIO.output(RELAY_PIN, GPIO.HIGH)  # Turn OFF
        st.session_state.relay_state["status"] = "OFF"
        print(f"Relay turned OFF by schedule at {now.strftime('%H:%M:%S')}")

# --- Execute Logic on Each Rerun ---

read_sensor_data()
check_and_control_relay()

# --- Modern UI Display ---

st.title("HydroVerde Dashboard")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Main dashboard metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Temperature", st.session_state.sensor_data["temperature"])
with col2:
    st.metric("Humidity", st.session_state.sensor_data["humidity"])
with col3:
    # Use color to indicate relay status
    status = st.session_state.relay_state["status"]
    st.metric("Relay Status", status, delta="ON" if status == "ON" else "OFF",
              delta_color="normal" if status == "ON" else "inverse")

st.markdown("---")

# --- Manual Control Section ---
st.subheader("Manual Control")

# Show override status and button to resume schedule
if st.session_state.manual_override:
    st.warning("Manual override is active. The schedule is currently paused.")
    if st.button("✅ Resume Automated Schedule"):
        st.session_state.manual_override = False
        st.toast("Returning to automated schedule control!")
        time.sleep(1)  # Give toast time to show
        st.rerun()

# Manual ON/OFF buttons
m_col1, m_col2 = st.columns(2)
with m_col1:
    if st.button("Turn ON Now", type="primary", use_container_width=True,
                  disabled=st.session_state.relay_state["status"] == "ON"):
        GPIO.output(RELAY_PIN, GPIO.LOW)
        st.session_state.relay_state["status"] = "ON"
        st.session_state.manual_override = True
        st.toast("Relay manually turned ON.")
        time.sleep(1)
        st.rerun()
with m_col2:
    if st.button("Turn OFF Now", use_container_width=True,
                  disabled=st.session_state.relay_state["status"] == "OFF"):
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        st.session_state.relay_state["status"] = "OFF"
        st.session_state.manual_override = True
        st.toast("Relay manually turned OFF.")
        time.sleep(1)
        st.rerun()

st.markdown("---")


# Expander for schedule settings to keep the main view clean
with st.expander("⚙️ Schedule Settings", expanded=False):
    schedule = st.session_state.relay_state
    st.write(f"Current Schedule: **{schedule['start_time'].strftime('%H:%M')}** to **{schedule['end_time'].strftime('%H:%M')}**")

    c1, c2 = st.columns(2)
    with c1:
        start_time_input = st.time_input(
            "Start Time (ON)",
            value=schedule["start_time"],
            key="start_time"
        )
    with c2:
        end_time_input = st.time_input(
            "End Time (OFF)",
            value=schedule["end_time"],
            key="end_time"
        )

    if st.button("Update Schedule"):
        st.session_state.relay_state["start_time"] = start_time_input
        st.session_state.relay_state["end_time"] = end_time_input
        # If manual override was on, updating the schedule returns to schedule mode
        if st.session_state.manual_override:
            st.session_state.manual_override = False
            st.toast("Schedule updated! Resuming automated control. ✅")
        else:
            st.toast("Schedule updated successfully! ✅")
        
        # Immediately re-check the relay status after updating the schedule
        check_and_control_relay()
        # Short sleep to allow toast message to be seen before rerun
        time.sleep(2)
        st.rerun()

# --- Auto-Refresh Mechanism ---
# A 5-second interval is a good balance between responsiveness and resource usage.
time.sleep(5)
st.rerun()