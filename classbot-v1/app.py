from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
import spacy
import psycopg2
from psycopg2.pool import SimpleConnectionPool
import re
from typing import Dict, Optional, List, Tuple
import random
from statistics import mean
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import re
from functools import wraps
import urllib.parse
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask import current_app
import secrets



# Encode the password properly
password = urllib.parse.quote_plus("password_of_database")  

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    from spacy.cli import download
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

app = Flask(__name__)  
#app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = 'your_secret_key_here'  # Change this to a secure secret key

# Serializer for generating tokens
app.config['SECRET_KEY'] = secrets.token_hex(32)
with app.app_context():
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://postgres:{password}@localhost:5432/your_database_name"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure mail settings in your app configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # e.g., 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'yourmail@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_password'

mail = Mail(app)

# User model for authentication
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)  # New field for email verification
# Connection pool for other database operations
DB_CONFIG = {
    "database": "your_database_name",
    "user": "your_username",
    "password": "your_password",
    "host": "localhost",
    "port": "5432"
}

pool = SimpleConnectionPool(1, 20, **DB_CONFIG)

class MarksQueryProcessor:
    def __init__(self):
        # Enhanced greeting patterns
        self.greeting_patterns = [
            r"(?i)^(hi|hello|hey|greetings|good morning|good afternoon|good evening).*",
            r"(?i).*\b(hi|hello|hey)\b.*",
            r"(?i)^(yo|hiya|howdy|sup|what's up|whats up).*",
            r"(?i).*\b(start|begin|let's start)\b.*"
        ]
        
        self.farewell_patterns = [
            r"(?i)^(bye|goodbye|see you|farewell|exit|quit|end).*",
            r"(?i).*\b(bye|goodbye|see you|farewell)\b.*",
            r"(?i).*\b(thanks|thank you|done)\b.*\b(bye|goodbye|end)\b.*",
            r"(?i)^(stop|close|finish).*"
        ]
        
        self.help_patterns = [
            r"(?i)^(what|how) can you (do|help).*",
            r"(?i)^help.*",
            r"(?i).*\b(help|assist|guide)\b.*",
            r"(?i).*\b(commands|options|features|abilities)\b.*",
            r"(?i).*\b(how to|how do I|what should I)\b.*"
        ]

        # Enhanced patterns for subject-specific queries
        self.subject_query_patterns = [
            r"(?i)what (?:was|is|are) the (.+?) marks? (?:of|for) ([\w\d]+)",
            r"(?i)show (.+?) marks? (?:of|for) ([\w\d]+)",
            r"(?i)([\w\d]+)(?:'s)? (.+?) marks?",
            r"(?i)get (.+?) marks? (?:of|for) ([\w\d]+)",
            r"(?i)tell me (.+?) marks? (?:of|for) ([\w\d]+)",
            r"(?i)how (?:much|many) (?:did|has) ([\w\d]+) (?:get|score|achieve) in (.+?)",
            r"(?i)what (?:did|has) ([\w\d]+) (?:get|score|achieve) in (.+?)",
            r"(?i)display (.+?) marks? (?:of|for) ([\w\d]+)",
            r"(?i)check (.+?) marks? (?:of|for) ([\w\d]+)"
        ]

        # Enhanced patterns for average marks queries
        self.average_patterns = [
            r"(?i)(?:what is|show|get|tell me) (?:the )?average (?:marks? )?(?:in|of|for) (.+)",
            r"(?i)average (?:marks? )?(?:in|of|for) (.+)",
            r"(?i)class average (?:in|of|for) (.+)",
            r"(?i)how (?:is|was) the class (?:performance|doing) in (.+)",
            r"(?i)what's the mean (?:score|marks?) (?:in|of|for) (.+)",
            r"(?i)(?:show|display|tell) (?:me )?class (?:statistics|stats|performance) (?:for|in|of) (.+)"
        ]

        # Enhanced ranking patterns
        self.ranking_patterns = [
            r"(?i)who (?:got|scored|has|achieved) (?:the )?(?:highest|most|maximum|max|more|top|best) marks?(?: overall)?",
            r"(?i)who (?:got|scored|has|achieved) (?:the )?(?:lowest|least|minimum|min|less|bottom|worst) marks?(?: overall)?",
            r"(?i)who (?:got|scored|has|achieved) (?:the )?(?:highest|most|maximum|max|more|top|best) marks? in (.+?)\??",
            r"(?i)who (?:got|scored|has|achieved) (?:the )?(?:lowest|least|minimum|min|less|bottom|worst) marks? in (.+?)\??",
            r"(?i)show (?:top|highest|best) performer(?:s)?(?: in (.+?))?",
            r"(?i)show (?:lowest|worst) performer(?:s)?(?: in (.+?))?",
            r"(?i)top scorer(?:s)?(?: in (.+?))?",
            r"(?i)lowest scorer(?:s)?(?: in (.+?))?",
            r"(?i)who (?:is|are) (?:the )?(?:best|top|strongest) (?:student|performer)(?:s)?(?: in (.+?))?",
            r"(?i)who (?:is|are) (?:the )?(?:weakest|poorest) (?:student|performer)(?:s)?(?: in (.+?))?",
            r"(?i)display (?:top|best|highest) (\d+)? ?(?:student|performer)(?:s)?(?: in (.+?))?",
            r"(?i)list (?:all )?(?:top|best|highest) (?:student|performer)(?:s)?(?: in (.+?))?"
        ]
        
        # Enhanced ID patterns
        self.id_patterns = [
            r"(?i)show marks for (?:student )?(?:id[ :]*)?([\w\d]+)",
            r"(?i)get marks for (?:student )?(?:id[ :]*)?([\w\d]+)",
            r"(?i)marks of (?:student )?(?:id[ :]*)?([\w\d]+)",
            r"(?i)^(23cs\d{3})$",
            r"(?i)(23cs\d{3})",
            r"(?i)tell me about (23cs\d{3})",
            r"(?i)show me (23cs\d{3}) marks",
            r"(?i)how (?:is|was) (23cs\d{3}) (?:doing|performing)",
            r"(?i)display (?:all )?marks for (23cs\d{3})",
            r"(?i)check (?:status|performance) of (23cs\d{3})",
            r"(?i)what are the marks of student (23cs\d{3})",
            r"(?i)give me details about (23cs\d{3})"
        ]
        
        self.subject_keywords = {
            "data visualization": ["data viz", "visualization", "dv", "dataviz", "data vis", "viz", "data visualization", "visualization course"],
            "computer architecture": ["ca", "architecture", "comp arch", "computer arch", "comp architecture", "hardware arch", "system architecture"],
            "dsa": ["data structures", "algorithms", "ds", "data structure", "ds and algo", "data structures and algorithms", "algo"],
            "java": ["java programming", "java lang", "java language", "java", "core java", "advanced java", "java course"],
            "dbms": ["database", "db", "database management", "database systems", "db management", "database course", "sql"],
            "discrete maths": ["discrete mathematics", "discrete", "dm", "discrete math", "mathematics", "maths", "math"]
        }

        self.column_mapping = {
            "data visualization": "data_visualization",
            "computer architecture": "computer_architecture",
            "dsa": "dsa",
            "java": "java",
            "dbms": "dbms",
            "discrete maths": "discrete_maths"
        }

        self.greetings = [
            "Hello! I'm your marks assistant. How can I help you today? 😊",
            "Hi there! Ready to help you check academic performance! 📚",
            "Greetings! What information would you like about student marks? 📊",
            "Hello! Feel free to ask about any student's marks or performance! 🎓",
            "Hey! I'm here to help you with student performance analysis! 📈",
            "Welcome! Ask me anything about student marks and performance! 🌟",
            "Hi! Need help with academic records? I'm here to assist! 📝"
        ]


        self.farewells = [
            "Goodbye! Feel free to come back if you need more information! 👋",
            "See you later! Have a great day! 😊",
            "Bye! Don't hesitate to ask if you need more help! 🌟",
            "Take care! Come back anytime for more assistance! 🎓",
            "Farewell! Hope I was able to help! 📚",
            "Goodbye! Happy learning! 🌈",
            "See you soon! Stay curious! ⭐"
        ]

    def _normalize_subject(self, subject: str) -> Optional[str]:
        """Enhanced subject normalization with fuzzy matching."""
        if not subject:
            return None
            
        subject = subject.lower().strip()
        
        # Direct match
        if subject in self.subject_keywords:
            return subject
            
        # Check aliases
        for main_subject, aliases in self.subject_keywords.items():
            if subject in aliases or any(alias in subject for alias in aliases):
                return main_subject
            
        # Fuzzy matching for partial matches
        for main_subject, aliases in self.subject_keywords.items():
            if any(word in subject for word in main_subject.split()):
                return main_subject
                
        return None

    def _get_db_column_name(self, subject: str) -> str:
        """Convert normalized subject name to database column name."""
        return self.column_mapping.get(subject, subject.replace(" ", "_"))

    def get_average_marks(self, subject: str) -> str:
        """Get average marks for a specific subject."""
        normalized_subject = self._normalize_subject(subject)
        if not normalized_subject:
            return f"❌ Sorry, I couldn't recognize the subject: {subject}"

        conn = pool.getconn()
        try:
            with conn.cursor() as cursor:
                column_name = self._get_db_column_name(normalized_subject)
                cursor.execute(f"""
                    SELECT AVG({column_name}), MIN({column_name}), MAX({column_name})
                    FROM students
                """)
                avg, min_marks, max_marks = cursor.fetchone()
                
                return (f"📊 Statistics for {normalized_subject.title()}:\n"
                       f"Class Average: {avg:.2f}\n"
                       f"Highest Mark: {max_marks}\n"
                       f"Lowest Mark: {min_marks}")
        except Exception as e:
            return f"❌ Error calculating average: {str(e)}"
        finally:
            pool.putconn(conn)

    def process_query(self, query: str) -> str:
        """Process user query and return appropriate response."""
        query = query.strip()
        
        # Check for greetings
        for pattern in self.greeting_patterns:
            if re.match(pattern, query):
                return random.choice(self.greetings)

        # Check for farewells
        for pattern in self.farewell_patterns:
            if re.match(pattern, query):
                return random.choice(self.farewells)

        # Check for help
        for pattern in self.help_patterns:
            if re.match(pattern, query):
                return self.get_help_message()

        # Check for average marks query
        for pattern in self.average_patterns:
            match = re.search(pattern, query)
            if match:
                subject = match.group(1)
                return self.get_average_marks(subject)

        # Check for subject-specific marks query
        for pattern in self.subject_query_patterns:
            match = re.search(pattern, query)
            if match:
                if len(match.groups()) == 2:
                    subject = match.group(1)
                    student_id = match.group(2)
                    # Check if the groups are in correct order
                    if re.match(r'23cs\d{3}', subject):
                        student_id, subject = subject, student_id
                    return self.get_subject_marks(student_id, subject)

        # Check for student ID marks query
        for pattern in self.id_patterns:
            match = re.search(pattern, query)
            if match:
                student_id = match.group(1)
                return self.get_marks_by_id(student_id.lower())

        # Check for ranking queries
        for pattern in self.ranking_patterns:
            match = re.search(pattern, query)
            if match:
                subject = match.group(1) if match and len(match.groups()) >= 1 else None
                if 'highest' in query.lower() or 'top' in query.lower() or 'best' in query.lower():
                    return self.get_top_performer(subject)
                elif 'lowest' in query.lower() or 'worst' in query.lower() or 'bottom' in query.lower():
                    return self.get_bottom_performer(subject)

        return ("I'm not sure I understand. Could you please rephrase your question? 🤔\n"
                "You can ask about:\n"
                "• Student marks (e.g., 'Show marks for 23cs098')\n"
                "• Subject performance (e.g., 'What is the Java mark of 23cs098?')\n"
                "• Class averages (e.g., 'What's the average in DSA?')\n"
                "• Top performers (e.g., 'Who got the highest marks in Java?')")

    def get_subject_marks(self, student_id: str, subject: str) -> str:
        """Get marks for a specific subject and student."""
        normalized_subject = self._normalize_subject(subject)
        if not normalized_subject:
            return f"❌ Sorry, I couldn't recognize the subject: {subject}"

        conn = pool.getconn()
        try:
            with conn.cursor() as cursor:
                column_name = self._get_db_column_name(normalized_subject)
                query = f"""
                    SELECT id, name, {column_name}
                    FROM students
                    WHERE LOWER(id) = LOWER(%s)
                """
                cursor.execute(query, (student_id,))
                result = cursor.fetchone()
                
                if not result:
                    return f"📚 No records found for student ID: {student_id}"
                
                # Get class average for comparison
                cursor.execute(f"SELECT AVG({column_name}) FROM students")
                class_avg = cursor.fetchone()[0]
                
                performance = "above" if result[2] > class_avg else "below"
                
                return (f"📊 {normalized_subject.title()} marks for {result[1]} (ID: {result[0]}):\n"
                       f"Marks: {result[2]}\n"
                       f"Class Average: {class_avg:.2f}\n"
                       f"Performance: {performance} class average")
        except Exception as e:
            return f"❌ Error retrieving marks: {str(e)}"
        finally:
            pool.putconn(conn)

    def get_marks_by_id(self, student_id: str) -> str:
        """Get all marks for a specific student."""
        conn = pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, name, data_visualization, computer_architecture, 
                           dsa, java, dbms, discrete_maths 
                    FROM students 
                    WHERE LOWER(id) = LOWER(%s)
                """, (student_id,))
                result = cursor.fetchone()
                
                if not result:
                    return f"📚 No records found for student ID: {student_id}"
                
                marks_dict = {
                    "Data Visualization": result[2],
                    "Computer Architecture": result[3],
                    "DSA": result[4],
                    "Java": result[5],
                    "DBMS": result[6],
                    "Discrete Maths": result[7]
                }
                
                # Calculate statistics
                total_marks = sum(marks_dict.values())
                avg_marks = total_marks / len(marks_dict)
                highest_subject = max(marks_dict.items(), key=lambda x: x[1])
                lowest_subject = min(marks_dict.items(), key=lambda x: x[1])
                
                # Get class rank
                cursor.execute("""
                    SELECT COUNT(*) + 1 
                    FROM students 
                    WHERE (data_visualization + computer_architecture + 
                           dsa + java + dbms + discrete_maths) > 
                          (SELECT (data_visualization + computer_architecture + 
                                  dsa + java + dbms + discrete_maths)
                           FROM students 
                           WHERE LOWER(id) = LOWER(%s))
                """, (student_id,))
                rank = cursor.fetchone()[0]
                
                response = [
                    f"📊 Marks Report for {result[1]} (ID: {result[0]})",
                    "-" * 40
                ]
                
                # Add subject-wise marks
                for subject, marks in marks_dict.items():
                    response.append(f"{subject:<20}: {marks:>3}")
                
                # Add summary statistics
                response.extend([
                    "-" * 40,
                    f"📊 Total Marks: {total_marks}",
                    f"📈 Average: {avg_marks:.1f}",
                    f"🏆 Best Subject: {highest_subject[0]} ({highest_subject[1]})",
                    f"📉 Needs Improvement: {lowest_subject[0]} ({lowest_subject[1]})",
                    f"🎯 Class Rank: {rank}"
                ])
                
                return "\n".join(response)
        except Exception as e:
            return f"❌ Error retrieving marks: {str(e)}"
        finally:
            pool.putconn(conn)

    def get_top_performer(self, subject: Optional[str] = None) -> str:
        """Get top performer overall or in a specific subject."""
        conn = pool.getconn()
        try:
            with conn.cursor() as cursor:
                if subject:
                    normalized_subject = self._normalize_subject(subject)
                    if not normalized_subject:
                        return f"❌ Invalid subject: {subject}"
                    
                    column_name = self._get_db_column_name(normalized_subject)
                    cursor.execute(f"""
                        SELECT id, name, {column_name},
                               RANK() OVER (ORDER BY {column_name} DESC) as rank
                        FROM students
                        ORDER BY {column_name} DESC
                        LIMIT 3
                    """)
                    results = cursor.fetchall()
                    response = [f"🏆 Top performers in {normalized_subject.title()}:"]
                    for i, result in enumerate(results, 1):
                        response.append(f"{i}. {result[1]} (ID: {result[0]}) - {result[2]} marks")
                    return "\n".join(response)
                else:
                    cursor.execute("""
                        SELECT id, name, 
                               (data_visualization + computer_architecture + 
                                dsa + java + dbms + discrete_maths) as total,
                               RANK() OVER (ORDER BY 
                                (data_visualization + computer_architecture + 
                                 dsa + java + dbms + discrete_maths) DESC) as rank
                        FROM students
                        ORDER BY total DESC
                        LIMIT 3
                    """)
                    results = cursor.fetchall()
                    response = ["🏆 Overall top performers:"]
                    for i, result in enumerate(results, 1):
                        response.append(f"{i}. {result[1]} (ID: {result[0]}) - Total: {result[2]}")
                    return "\n".join(response)
        except Exception as e:
            return f"❌ Error finding top performer: {str(e)}"
        finally:
            pool.putconn(conn)

    def get_bottom_performer(self, subject: Optional[str] = None) -> str:
        """Get bottom performer overall or in a specific subject."""
        conn = pool.getconn()
        try:
            with conn.cursor() as cursor:
                if subject:
                    normalized_subject = self._normalize_subject(subject)
                    if not normalized_subject:
                        return f"❌ Invalid subject: {subject}"
                    
                    column_name = self._get_db_column_name(normalized_subject)
                    cursor.execute(f"""
                        SELECT id, name, {column_name},
                               RANK() OVER (ORDER BY {column_name}) as rank
                        FROM students
                        ORDER BY {column_name} ASC
                        LIMIT 3
                    """)
                    results = cursor.fetchall()
                    response = [f"📉 Students needing improvement in {normalized_subject.title()}:"]
                    for i, result in enumerate(results, 1):
                        response.append(f"{i}. {result[1]} (ID: {result[0]}) - {result[2]} marks")
                    return "\n".join(response)
                else:
                    cursor.execute("""
                        SELECT id, name, 
                               (data_visualization + computer_architecture + 
                                dsa + java + dbms + discrete_maths) as total,
                               RANK() OVER (ORDER BY 
                                (data_visualization + computer_architecture + 
                                 dsa + java + dbms + discrete_maths)) as rank
                        FROM students
                        ORDER BY total ASC
                        LIMIT 3
                    """)
                    results = cursor.fetchall()
                    response = ["📉 Students needing overall improvement:"]
                    for i, result in enumerate(results, 1):
                        response.append(f"{i}. {result[1]} (ID: {result[0]}) - Total: {result[2]}")
                    return "\n".join(response)
        except Exception as e:
            return f"❌ Error finding bottom performer: {str(e)}"
        finally:
            pool.putconn(conn)

    def get_help_message(self) -> str:
        """Get help message with available commands and examples."""
        return """🤖 Welcome to Student Marks Assistant!

I can help you with:
📊 Individual student marks:
  • "Show marks for 23cs098"
  • "What are the marks of 23cs082"

📚 Subject-specific marks:
  • "What was the Java mark of 23cs098?"
  • "Show DSA marks for 23cs082"

📈 Performance analysis:
  • "Who got the highest marks in Java?"
  • "Show top performer overall"
  • "Who got the lowest marks in DSA?"
  • "What's the average in Computer Architecture?"

Available subjects:
""" + "\n".join(f"• {subject.title()}" for subject in self.subject_keywords.keys()) + """

Just ask your question naturally and I'll help you find the information! 😊"""

# Login decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contactus.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Validate email domain
        if not email.endswith('@kpriet.ac.in'):
            flash('Please use your KPRIET email address')
            return redirect(url_for('signup'))
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('signup'))
        
        # Create new unverified user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_verified=False  # Mark as unverified initially
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            
            # Send verification email
            if send_verification_email(email):
                flash('Registration successful! A verification email has been sent. Please verify your email to log in.')
            else:
                db.session.rollback()
                flash('Unable to send verification email. Please try again.')

            return redirect(url_for('login'))
        
        except Exception as e:
            db.session.rollback()
            flash('An error occurred. Please try again.')
            return redirect(url_for('signup'))
    
    return render_template('signup.html')


def send_verification_email(user_email):
    try:
        # Generate token
        token = s.dumps(user_email, salt='email-confirm')
        verify_url = url_for('verify_email', token=token, _external=True)
        
        msg = Message('Verify Your Email', sender='yourmail@gmail.com', recipients=[user_email])
        msg.body = f"Hello! Please verify your email by clicking the link: {verify_url}"
        
        mail.send(msg)
        return True
    except Exception as e:
        print("Error sending email:", e)
        return False

@app.route('/verify_email/<token>')
def verify_email(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=3600)  # Token valid for 1 hour
    except:
        flash('The verification link is invalid or has expired.')
        return redirect(url_for('signup'))
    
    # Find the user and set is_verified to True
    user = User.query.filter_by(email=email).first_or_404()
    if user:
        user.is_verified = True
        db.session.commit()
        flash('Your email has been verified! You can now log in.')
        return redirect(url_for('login'))
    else:
        flash('Verification failed. Please try signing up again.')
        return redirect(url_for('signup'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Find the user by email
        user = User.query.filter_by(email=email).first()
        
        # Check if user exists and password is correct
        if user and check_password_hash(user.password_hash, password):
            # Check if the user's email is verified
            if user.is_verified:
                # Store user info in session and redirect to chat interface
                session['user_id'] = user.id
                session['username'] = user.username
                return redirect(url_for('chat_interface'))
            else:
                # Notify user to verify their email
                flash('Please verify your email address to log in.')
                return redirect(url_for('login'))
        
        # Invalid credentials
        flash('Invalid email or password')
        return redirect(url_for('login'))
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/chat-interface')
@login_required
def chat_interface():
    return render_template('index7.html')

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    try:
        user_input = request.json['message']
        processor = MarksQueryProcessor()  # Your existing chat logic
        response = processor.process_query(user_input)
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'response': f"An error occurred: {str(e)}"})

# @app._got_first_request
# def create_tables():
#     db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
