document.addEventListener('DOMContentLoaded', function() {
    const attendanceForm = document.getElementById('attendance-form');
    const gpsButton = document.getElementById('get-gps');

    gpsButton.addEventListener('click', function() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(function(position) {
                const latitude = position.coords.latitude;
                const longitude = position.coords.longitude;

                document.getElementById('latitude').value = latitude;
                document.getElementById('longitude').value = longitude;
                alert('GPS location captured: ' + latitude + ', ' + longitude);
            }, function() {
                alert('Unable to retrieve your location.');
            });
        } else {
            alert('Geolocation is not supported by this browser.');
        }
    });

    attendanceForm.addEventListener('submit', function(event) {
        // Add any additional validation or processing before form submission
        alert('Attendance form submitted!');
    });
});