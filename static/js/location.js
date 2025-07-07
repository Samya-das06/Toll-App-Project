// static/js/location.js
document.addEventListener('DOMContentLoaded', (event) => {
    const statusDiv = document.getElementById('location-status');
    const coordsDiv = document.getElementById('location-coords');
    const lastUpdateDiv = document.getElementById('location-last-update');
    const updateInterval = 15000; // Send every 15 seconds (adjust as needed)
    let intervalId = null;

    function updateDisplay(message, className = '', coords = null, timestamp = null) {
        if (!statusDiv || !coordsDiv || !lastUpdateDiv) {
            // Elements might not exist if user navigates away quickly
            // console.warn("Location display elements not found.");
            return;
        }
        statusDiv.textContent = `Status: ${message}`;
        statusDiv.className = className; // Add error or success class if needed

        if (coords) {
            coordsDiv.textContent = `Coordinates: Lat=<span class="math-inline">\{coords\.latitude\.toFixed\(6\)\}, Lon\=</span>{coords.longitude.toFixed(6)}`;
        } else {
            // Don't clear coords on temporary errors like sending failures
            // coordsDiv.textContent = `Coordinates: Not available.`;
        }
        if (timestamp) {
            lastUpdateDiv.textContent = `Last Update Sent: ${new Date(timestamp).toLocaleTimeString()}`;
        }
    }

    function sendLocationToServer(position) {
        const { latitude, longitude } = position.coords;
        const timestamp = Date.now(); // Use current time for sending

        console.log(`Sending: Lat=<span class="math-inline">\{latitude\}, Lon\=</span>{longitude}`);
        // Update display optimistically before sending
        updateDisplay('Sending location...', '', { latitude, longitude }, null); // Don't update time until success

        // Send data to the Python Flask server's API endpoint
        fetch('/api/update_location', { // Use the new API endpoint
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // Flask-Login session cookie is usually sent automatically by browser
            },
            body: JSON.stringify({ latitude: latitude, longitude: longitude }),
        })
        .then(response => {
            // Check if response is ok (status in the range 200-299)
            if (!response.ok) {
                // Try to parse error message from server if available
                return response.json().then(errData => {
                     throw new Error(errData.message || `HTTP error! status: ${response.status}`);
                }).catch(() => {
                     // If parsing JSON fails, throw generic error
                     throw new Error(`HTTP error! status: ${response.status}`);
                });
            }
            return response.json(); // Parse JSON body of the response
        })
        .then(data => {
            if (data.status === 'success') {
                console.log('Server received location successfully:', data.message);
                updateDisplay('Location sent successfully. Monitoring...', 'text-success', { latitude, longitude }, timestamp);
            } else {
                // This case might not be reached if error handling above works correctly
                console.error('Server reported an error:', data.message);
                updateDisplay(`Server error: ${data.message}`, 'text-danger', { latitude, longitude }, null);
            }
        })
        .catch((error) => {
            console.error('Error sending location:', error);
            // Provide more specific feedback if possible
            let displayError = `Failed to send: ${error.message}`;
            if (error.message.includes('Failed to fetch')) {
                displayError = 'Network error. Cannot reach server.';
            }
            updateDisplay(displayError, 'text-danger', { latitude, longitude }, null);
        });
    }

    function handleLocationError(error) {
        let message = 'Unknown error';
        switch(error.code) {
            case error.PERMISSION_DENIED:
                message = "Location permission denied.";
                break;
            case error.POSITION_UNAVAILABLE:
                message = "Location information is unavailable.";
                break;
            case error.TIMEOUT:
                message = "Location request timed out.";
                break;
            // case error.UNKNOWN_ERROR: // Often redundant
            //     message = "An unknown error occurred.";
            //     break;
        }
        console.error('Geolocation error:', message);
        updateDisplay(`Geolocation error: ${message}`, 'text-danger');
        // Stop trying if permission is denied permanently
        if (error.code === error.PERMISSION_DENIED && intervalId) {
            clearInterval(intervalId);
            intervalId = null;
            updateDisplay(`Stopped updates: ${message}`, 'text-danger');
        }
    }

    function getLocationAndSend() {
        if (navigator.geolocation) {
            console.log('Requesting current position...');
            updateDisplay('Requesting location...');
            navigator.geolocation.getCurrentPosition(
                sendLocationToServer, // Success callback
                handleLocationError,   // Error callback
                { // Options
                    enableHighAccuracy: true, // Try for better accuracy
                    timeout: 10000,          // Max time (ms) to wait for location
                    maximumAge: 0            // Force fresh location
                }
            );
        } else {
            updateDisplay("Geolocation is not supported by this browser.", 'text-danger');
            if (intervalId) {
                clearInterval(intervalId);
                intervalId = null;
            }
        }
    }

    // --- Main Execution ---
    if (!navigator.geolocation) {
         updateDisplay("Geolocation not supported.", 'text-danger');
    } else {
        // Check permission status first for a better initial message
        navigator.permissions.query({name:'geolocation'}).then(function(permissionStatus) {
            if (permissionStatus.state === 'granted') {
                updateDisplay('Ready. Starting location updates...', 'text-info');
                getLocationAndSend(); // Call immediately
                intervalId = setInterval(getLocationAndSend, updateInterval); // Set interval
            } else if (permissionStatus.state === 'prompt') {
                updateDisplay('Ready. Waiting for location permission...', 'text-warning');
                // It will ask for permission on the first call to getCurrentPosition
                getLocationAndSend(); // Call immediately
                intervalId = setInterval(getLocationAndSend, updateInterval); // Set interval
            } else if (permissionStatus.state === 'denied') {
                updateDisplay('Location permission denied. Please enable in browser settings.', 'text-danger');
                // Do not start interval if denied
            }
            // Optional: Listen for changes in permission status
            permissionStatus.onchange = function() {
                 console.log('Geolocation permission state changed to: ' + this.state);
                 // You might want to restart/stop updates based on the new state here
            };
        });
    }
});