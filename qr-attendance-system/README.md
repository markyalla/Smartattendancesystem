# QR Code Attendance System

This project is a QR code attendance system designed for educational institutions. It allows lecturers to register and log in, add course details, and enables students to fill out attendance forms with their information and GPS location.

## Features

- **User Registration and Login**: Lecturers can create accounts and log in to manage their courses.
- **Course Management**: Lecturers can add and manage course details.
- **Attendance Tracking**: Students can fill out attendance forms, which include their information and GPS location.
- **QR Code Generation**: Generate QR codes for courses to facilitate easy attendance marking.

## Technologies Used

- Flask: A lightweight WSGI web application framework.
- Flask-SQLAlchemy: An extension for Flask that adds support for SQLAlchemy.
- Flask-WTF: An extension that simplifies working with forms in Flask.
- Flask-Migrate: An extension that handles SQLAlchemy database migrations for Flask applications.
- HTML/CSS/JavaScript: For front-end development.

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd qr-attendance-system
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Configure the application:
   - Update the `instance/config.py` file with your database URI and secret key.

5. Initialize the database:
   ```
   flask db init
   flask db migrate
   flask db upgrade
   ```

## Running the Application

To run the application, execute the following command:
```
python run.py
```

The application will be available at `http://127.0.0.1:5000`.

## Usage

- Lecturers can register and log in to add courses.
- Students can access the attendance form via the QR code provided for each course.

## Contributing

Contributions are welcome! Please submit a pull request or open an issue for any suggestions or improvements.

## License

This project is licensed under the MIT License. See the LICENSE file for details.