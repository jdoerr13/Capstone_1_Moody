import requests
import os
from flask import Flask, render_template, request, flash, redirect, session, g, jsonify, url_for
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
# from sqlalchemy import or_
from forms import LoginForm, SignupForm, MoodSymptomAssessmentForm, ProfileEditForm, JournalEntryForm
from models import db, connect_db, User, Diagnosis, UserHistory, Weather, Mood, Symptoms, CopingSolution, Group, GroupPost, JournalEntry
from datetime import datetime, timedelta  # Import the datetime module
from flask_bcrypt import Bcrypt
# from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
# from flask_wtf.csrf import CSRFProtect

CURR_USER_KEY = "curr_user"
app = Flask(__name__)

app.secret_key = 'your_secret_key_here'


# Initialize Flask-Migrate- USED WITH ANY UPDATE TO THE MODELS FOR DB MOODY
migrate = Migrate(app, db)

app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ.get('DATABASE_URL', 'postgresql:///moody'))

# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# # Initialize SQLAlchemy
# db = SQLAlchemy(app)

app.config['SQLALCHEMY_ECHO'] = False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
app.config['SECRET_KEY'] = "JDOERR13"
toolbar = DebugToolbarExtension(app)

app.debug = True
# csrf = CSRFProtect(app)

connect_db(app)
app.app_context().push()
# db.drop_all()


db.create_all()

##############################################################################
# User signup/login/logout
@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global.""" 
    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])
    else:
        g.user = None

def do_login(user):
    """Log in user."""
    session[CURR_USER_KEY] = user.user_id

def do_logout():
    """Logout user."""
    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                email=form.email.data,
                password=form.password.data,
                registration_date=datetime.utcnow(),
            )
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Username or email already taken", 'danger')
            return render_template('signup.html', form=form)

        do_login(user)  # Log in the user using do_login
        flash('Welcome! You have successfully signed up.', 'success')
        return redirect('/')
    
    return render_template('signup.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        # Authenticate user
        user = User.authenticate(username, password)
        if user:
            do_login(user)  # Use the do_login function
            flash(f'Hello, {user.username}!', 'success')
            return redirect('/')
        else:
            flash('Invalid credentials. Please try again.', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    """Logout user."""
    try:
        session.pop(CURR_USER_KEY)
        flash("You have been logged out", "success")
    except KeyError:
        flash("You are not logged in", "danger")

    return redirect("/")



#_____________GETTING INFO FROM API_____________________________________
@app.route('/current', methods=['GET', 'POST'])
def current():
    current_weather_data = None

    if request.method == 'POST':
        location = request.form.get('location')
        current_weather_data = get_current_weather(location)

    # If no location has been submitted, set current_weather_data to None
    if not current_weather_data:
        current_weather_data = None

    return render_template('api/current.html', current_weather_data=current_weather_data, user=g.user)

def get_current_weather(location):
    url = "https://weatherapi-com.p.rapidapi.com/current.json"
    querystring = {"q": location}  # Use the user-provided location
    headers = {
        "X-RapidAPI-Key": "eb3fa9d2eamsh622acd4eaa00bf3p19fc73jsn647406a37c4e",
        "X-RapidAPI-Host": "weatherapi-com.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)

        if response.status_code == 200:
            return response.json()
        else:
            flash(f"Failed to fetch weather data for {location}. Please try again later.", 'error')
            return None
    except Exception as e:
        print("Error:", str(e))  # Add this line for debugging
        flash(f"An error occurred while fetching weather data for {location}. Please try again later.", 'error')
        return None
    
@app.route('/forecast', methods=['GET', 'POST'])
def forecast():
    forecast_data = None
    selected_date = None

    if request.method == 'POST':
        location = request.form.get('location')
        selected_date = request.form.get('date')  # Get the selected date
        forecast_data = get_today_weather(location, selected_date)

    return render_template('api/forecast.html', forecast_data=forecast_data, selected_date=selected_date, user=g.user)



def get_weather_forecast(location, date):
    url = "https://weatherapi-com.p.rapidapi.com/forecast.json"
    querystring = {"q": location, "days": "3"}
    headers = {
        "X-RapidAPI-Key": "eb3fa9d2eamsh622acd4eaa00bf3p19fc73jsn647406a37c4e",
        "X-RapidAPI-Host": "weatherapi-com.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)

        if response.status_code == 200:
            return response.json()
        else:
            flash(f"Failed to fetch weather forecast for {location}. Please try again later.", 'error')
            return None
    except Exception as e:
        print("Error:", str(e))  # Add this line for debugging
        flash(f"An error occurred while fetching weather forecast for {location}. Please try again later.", 'error')
        return None
    


@app.route('/history', methods=['GET', 'POST'])
def history():
    if request.method == 'POST':
        location = request.form.get('location')
        date = request.form.get('date')

        if location and date:
            historical_weather_data = get_historical_weather(location, date)
            if historical_weather_data:
                return render_template('history.html', historical_weather_data=historical_weather_data)
            else:
                flash("Failed to fetch historical weather data. Please try again later.", 'error')
        else:
            flash("Please enter both location and date.", 'error')

    return render_template('api/history.html', historical_weather_data=None, user=g.user)




def get_historical_weather(location, date):
    # Convert the date string to a datetime object (if needed)
    # Example format: 'YYYY-MM-DD'
    try:
        formatted_date = datetime.strptime(date, '%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError:
        flash("Invalid date format. Please use YYYY-MM-DD format.", 'error')
        return None

    url = "https://weatherapi-com.p.rapidapi.com/history.json"
    querystring = {
        "q": location,
        "dt": formatted_date,  # Use the formatted date
        "lang": "en"
    }

    headers = {
        "X-RapidAPI-Key": "eb3fa9d2eamsh622acd4eaa00bf3p19fc73jsn647406a37c4e",
        "X-RapidAPI-Host": "weatherapi-com.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)

        if response.status_code == 200:
            return response.json()
        else:
            flash(f"Failed to fetch historical weather data for {location}. Please try again later.", 'error')
            return None
    except Exception as e:
        print("Error:", str(e))  # Add this line for debugging
        flash(f"An error occurred while fetching historical weather data for {location}. Please try again later.", 'error')
        return None


@app.route('/astronomy', methods=['GET', 'POST'])
def astronomy():
    astronomy_data = None
    date = None  # Initialize date to None

    if request.method == 'POST':
        location = request.form.get('location')
        date = request.form.get('date')  # Get the date from the form
        astronomy_data = get_astronomy_data(location, date)

    return render_template('api/astronomy.html', astronomy_data=astronomy_data, date=date, user=g.user)


def get_astronomy_data(location, date):
    url = "https://weatherapi-com.p.rapidapi.com/astronomy.json"
    querystring = {"q": location, "dt": date}  # Include the date parameter if provided

    headers = {
        "X-RapidAPI-Key": "eb3fa9d2eamsh622acd4eaa00bf3p19fc73jsn647406a37c4e",
        "X-RapidAPI-Host": "weatherapi-com.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)

        if response.status_code == 200:
            return response.json()
        else:
            flash(f"Failed to fetch astronomy data for {location}. Please try again later.", 'error')
            return None
    except Exception as e:
        print("Error:", str(e))  # Add this line for debugging
        flash(f"An error occurred while fetching astronomy data for {location}. Please try again later.", 'error')
        return None
    

#______On home page- Live weather updates!
@app.route('/set_location', methods=['POST'])
def set_location():
    location = request.form.get('location')

    # Check if a location is provided
    if location:
        # Automatically fetch weather data for the user's location
        current_weather_data = get_current_weather(location)

        if current_weather_data:
            # Update the existing user's location and weather data
            if g.user:
                g.user.location = location
                g.user.current_weather = current_weather_data
                db.session.commit()
                flash('Location and weather data updated successfully!', 'success')
            else:
                flash('User not found. Please log in.', 'error')
        else:
            flash('Failed to retrieve weather data for the given location.', 'error')
    else:
        flash('Please provide a location to update.', 'error')

    return redirect(url_for('home'))


#________HOMEPAGE & USER PROFILES___________________

@app.route('/')
def homepage():
    if g.user:
        user_history = UserHistory.query.filter_by(user_id=g.user.user_id).all()
        
         # Retrieve user groups using the many-to-many relationship
        user_groups = g.user.groups  # This will give you the groups associated with the current user

        # information about friends (assuming you have a friends relationship)
        # friends = g.user.friends  # Modify this according to your model structure

        # Add the ProfileEditForm to the context and use it to set the location
        form = ProfileEditForm(request.form)
        
         # Check if the user has a location
        location = g.user.location
        current_weather_data = None

        # If the user has a location, fetch the current weather data
        if location:
            current_weather_data = get_current_weather(location)

        return render_template(
            'home.html',
            user_history=user_history,
            user_groups=user_groups,
            user=g.user,
            form=form,
            location=location,
            current_weather_data=current_weather_data  # Pass weather data to the template
        )
    else:
        return render_template('home-anon.html')
    

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if CURR_USER_KEY not in session:
        flash('You must be logged in to edit your profile.', 'warning')
        return redirect(url_for('login'))

    form = ProfileEditForm()

    if request.method == 'POST' and form.validate_on_submit():
        # Update the user's profile data in the database
        user = g.user  # Get the current user
        form.populate_obj(user)  # Populate the user object with form data
        db.session.commit()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('homepage'))

    # Populate the form with the user's data
    user = g.user
    form.process(obj=user)  # Populate the form fields with user data

    return render_template('edit_profile.html', form=form, user=user)



#_______Friends_________

@app.route('/friends_profile/<int:user_id>')
def friends_profile(user_id):
    # Find the user by user_id
    user = User.query.get(user_id)

    if user:
        # Retrieve the user's location (if available)
        location = user.location

        # Retrieve weather information for the user's location (if needed)
        # You can add your logic here.

        # Retrieve the groups the user is in
        user_groups = user.groups

        # Retrieve the user's friends
        friends = user.friends

        current_weather_data = None

        # If the user has a location, fetch the current weather data
        if location:
            current_weather_data = get_current_weather(location)
            
        return render_template('friends_profile.html', user=user, location=location, user_groups=user_groups, friends=friends, current_weather_data=current_weather_data)
    else:
        # Handle the case where the user is not found
        return "User not found"

@app.route('/send_friend_request/<int:user_id>', methods=['POST'])
def send_friend_request(user_id):
    if not g.user:
        # flash('Not logged in', 'error')
        return jsonify({'success': False, 'message': 'Not logged in'})

    if user_id == g.user.user_id:
        flash('Cannot send a friend request to yourself', 'error')
        return jsonify({'success': False, 'message': 'Cannot send a friend request to yourself'})

    recipient = User.query.get(user_id)

    if recipient:
        # Check if the recipient is already a friend
        if recipient in g.user.friends:
            # flash('You are already friends with this user', 'error')
            return jsonify({'success': False, 'message': 'You are already friends with this user'})

        # Check if the friend request already exists
        if g.user in recipient.friend_requests:
            # flash('Friend request already sent', 'error')
            return jsonify({'success': False, 'message': 'Friend request already sent'})

        # Add the sender to the recipient's friend requests
        recipient.friend_requests.append(g.user)
        db.session.commit()
        # flash('Friend request sent successfully', 'success')
        return jsonify({'success': True, 'message': 'Friend request sent successfully'})
    else:
        # flash('User not found', 'error')
        return jsonify({'success': False, 'message': 'User not found'})




@app.route('/accept_friend_request/<int:sender_id>', methods=['POST'])
def accept_friend_request(sender_id):
    if not g.user:
        return jsonify(success=False, message='Not logged in')

    sender = User.query.get(sender_id)

    if sender:
        # Check if the sender has sent a friend request to the current user
        if sender in g.user.friend_requests:
            # Remove the friend request
            g.user.friend_requests.remove(sender)
            # Add the sender to the current user's list of friends
            g.user.friends.append(sender)
            db.session.commit()
            return jsonify(success=True, message='Friend request accepted')
        else:
            return jsonify(success=False, message='Friend request not found')
    else:
        return jsonify(success=False, message='User not found')


# remove a friend
@app.route('/remove_friend/<int:friend_id>', methods=['POST'])
def remove_friend(friend_id):
    if not g.user:
        # Check if the user is logged in
        flash('Not logged in', 'error')
        return redirect(url_for('friends_groups')) 

    friend = User.query.get(friend_id)
    if friend:
        # Check if the friend exists
        if friend in g.user.friends:
            # Remove the friend from the user's friends list
            g.user.friends.remove(friend)
            db.session.commit()
            flash('Friend removed successfully', 'success')
        else:
            flash('User is not your friend', 'error')
    else:
        flash('Friend not found', 'error')

    return redirect(url_for('friends_groups'))  










#_______________________Assessments & Journal__________________________________
@app.route('/mood_symptom', methods=['GET', 'POST'])
def mood_symptom():
    form = MoodSymptomAssessmentForm()

    if form.validate_on_submit():
        # Process the form data here (e.g., save to a database)
        # Redirect to a success page or perform other actions
        return render_template('mood_symptom_form.html', form=form)

    return render_template('mood_symptom_form.html', form=form, user=g.user)


#View function for 


#_______________________Friends & Groups______________________________________
@app.route('/friends_groups', methods=['GET', 'POST'])
def friends_groups():
    # List all available groups
    groups = Group.query.all()

    # Initialize the users variable to None
    users = None

    # Fetch the user's friend requests received
    friend_requests_received = g.user.friend_requests  # Assuming you have a 'friend_requests' relationship

    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            # Use a case-insensitive filter to search for users by username
            users = User.query.filter(User.username.ilike(f'%{query}%')).all()

    # If no users are found, return all users
    if users is None:
        users = User.query.all()

    # Fetch the user's groups
    user_groups = g.user.groups

    # Create a dictionary to store whether the user is a member of each group
    group_membership = {group.group_id: g.user in group.members for group in groups}

    return render_template(
        'friends_groups/friends_groups.html',
        groups=groups,
        users=users,
        user=g.user,
        group_membership=group_membership,
        friend_requests_received=friend_requests_received  # Pass friend requests to the template
    )





@app.route('/join_group/<int:group_id>', methods=['GET', 'POST'])
def join_group(group_id):
    if not g.user:
        # Handle the case when the user is not logged in
        flash('You must be logged in to join a group.', 'warning')
        return jsonify(success=False, message='Not logged in')

    group = Group.query.get(group_id)

    if group:
        # Check if the user is already a member
        is_member = g.user in group.members

        if is_member:
            flash(f'Member: Let\'s chat with the group "{group.group_name}".', 'success')
        else:
            # Add the user to the group's members and save the relationship
            g.user.groups.append(group)
            db.session.commit()
            flash(f'Welcome to the group "{group.group_name}".', 'success')
            print(f'Joined group {group.group_name} with ID {group_id}')

        # Determine the message to send to the frontend
        message = 'Joined the group' if not is_member else 'Already a member'

        return jsonify(success=True, message=message, group_id=group_id, user=g.user)
    
    flash('Group not found', 'danger')
    return jsonify(success=False, message='Group not found')



@app.route('/leave_group/<int:group_id>', methods=['POST'])
def leave_group(group_id):
    if g.user:
        group = Group.query.get(group_id)
        if group:
            if g.user in group.members:
                group.members.remove(g.user)
                db.session.commit()
                return jsonify(success=True, message='Left the group', group_id=group_id)
    return jsonify(success=False, message='Failed to leave the group')


@app.route('/group/<int:group_id>', methods=['GET', 'POST'])
def group(group_id):
    group = Group.query.get(group_id)

    if request.method == 'POST':
        post_content = request.form.get('post_content')

        if post_content:
            current_user_id = 1  # Replace with your logic to get the current user's ID
            new_post = GroupPost(user_id=current_user_id, group=group, post_content=post_content)
            db.session.add(new_post)
            db.session.commit()
            
            return jsonify({
                'username': new_post.user.username,
                'content': new_post.post_content,
                'timestamp': new_post.timestamp,
                'post_id': new_post.id,
                'user_id': new_post.user_id
            })

    posts = GroupPost.query.filter_by(group=group).all()

    for post in posts:
    # Format the timestamp as a string
        post.timestamp_str = post.timestamp.strftime('%Y-%m-%d %H:%M:%S')

    return render_template('friends_groups/group.html', group=group, posts=posts, user=g.user)
# csrf_token=csrf.generate_csrf()



@app.route('/get_group_members/<int:group_id>', methods=['GET'])
def get_group_members(group_id):
    # Query the database to retrieve group members for the given group_id
    group = Group.query.get(group_id)

    if group is not None:
        members = group.members
        member_data = [{'username': member.username} for member in members]
        return jsonify(member_data)

    return jsonify([])  # Return an empty list if the group is not found




#_____GROUP POSTS_________
# Group creation, response creation, and post deletion routes
@app.route('/create_group_post/<int:group_id>', methods=['POST'])
def create_group_post(group_id):
    if g.user:
        post_content = request.form.get('post_content')
        if post_content:
            new_post = GroupPost(post_content=post_content, group_id=group_id, user_id=g.user.user_id)
            db.session.add(new_post)
            db.session.commit()
    return redirect(url_for('group', group_id=group_id))

@app.route('/create_response/<int:group_id>/<int:post_id>', methods=['POST'])
def create_response(group_id, post_id):
    if g.user:
        response_content = request.form.get('response_content')
        if response_content:
            new_response = GroupPost(response_content=response_content, group_id=group_id, user_id=g.user.user_id, parent_post_id=post_id)
            db.session.add(new_response)
            db.session.commit()
    return redirect(url_for('group', group_id=group_id))


@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    post = GroupPost.query.get(post_id)
    if post and g.user and post.user_id == g.user.user_id:
        db.session.delete(post)
        db.session.commit()
    return redirect(url_for('group', group_id=post.group_id))

#________________WELLNESS- JOURNAL__________________________________

@app.route('/wellness', methods=['GET', 'POST'])
def wellness():
    form = JournalEntryForm()

    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])
        user_id = g.user.user_id
    else:
        g.user = None
        user_id = None

    if form.validate_on_submit() and user_id:
        existing_entry = JournalEntry.query.filter_by(
            user_id=user_id,
            date=form.date.data,
        ).first()

        if existing_entry:
            existing_entry.entry = form.entry.data
        else:
            new_entry = JournalEntry(
                user_id=user_id,
                date=form.date.data,
                entry=form.entry.data,
            )
            db.session.add(new_entry)

        db.session.commit()

    user_journal_entries = []
    if user_id:
        user_journal_entries = JournalEntry.query.filter_by(user_id=user_id).all()

    # Fetch weather data for a week (adjust the date range as needed)
    start_date = datetime.now().date()
    end_date = start_date + timedelta(days=6)
    weather_data = {}

    current_date = start_date
    while current_date <= end_date:
        weather_data[current_date] = get_today_weather(g.user.location, current_date)
        current_date += timedelta(days=1)

    # Fetch weather data for the current date
    current_date = datetime.now().date()
    weather_data[current_date] = get_today_weather(g.user.location, current_date)

    return render_template('wellness.html', form=form, user_journal_entries=user_journal_entries, weather_data=weather_data)


# Define the get_today_weather function
def get_today_weather(location, selected_date):
    forecast_data = get_weather_forecast(location, selected_date)

    if forecast_data:
        # Extract data for the selected date
        for day in forecast_data['forecast']['forecastday']:
            if day['date'] == selected_date:
                return day
    else:
        return None


@app.route('/save_journal_entry', methods=['POST'])
def save_journal_entry():
    try:
        data = request.get_json()
        entry_text = data.get('entry')
        user_id = session.get(CURR_USER_KEY)

        new_entry = JournalEntry(
            user_id=user_id,
            date=datetime.utcnow().date(),
            entry=entry_text
        )

        db.session.add(new_entry)
        db.session.commit()

        return jsonify(success=True, message='Journal entry saved successfully')
    except Exception as e:
        print(str(e))
        db.session.rollback()
        return jsonify(success=False, message='Failed to save journal entry')
    
@app.route('/fetch_journal_entries', methods=['GET'])
def fetch_journal_entries():
    # Get the user ID (assuming it's stored in session)
    user_id = session.get(CURR_USER_KEY)

    # Fetch journal entries for today's date and the current user (if logged in)
    today = datetime.today().strftime('%Y-%m-%d')
    id=JournalEntry.id
    entries = JournalEntry.query.filter_by(date=today, user_id=user_id, id=id).all()

    # Return the journal entries as JSON
    return jsonify([entry.serialize() for entry in entries])

@app.route('/edit_journal_entry/<int:id>', methods=['GET', 'POST'])
def edit_journal_entry(id):
    # Get the user's ID
    user_id = session.get(CURR_USER_KEY)

    # Fetch the journal entry for the specified ID and user
    journal_entry = JournalEntry.query.get(id)

    if not journal_entry or journal_entry.user_id != user_id:
        # Handle the case where the entry doesn't exist or doesn't belong to the user
        flash("Journal entry not found or unauthorized access.", "danger")
        return redirect(url_for('wellness'))  # Redirect to the wellness page or show an error message

    form = JournalEntryForm(obj=journal_entry)

    if form.validate_on_submit():
        # Update the journal entry with the submitted data
        form.populate_obj(journal_entry)  # Update the journal entry from the form data
        db.session.commit()
        flash("Journal entry updated successfully.", "success")
        return redirect(url_for('wellness'))  # Redirect back to the wellness page after editing

    return render_template('edit_journal.html', form=form, id=journal_entry.id, date=journal_entry.date, entry=journal_entry)

                           
                   



@app.route('/delete_journal_entry/<int:id>', methods=['POST'])
def delete_journal_entry(id):
    if request.method == 'POST':
        entry_id = request.form.get('id')

        print(f"Deleting entry with id: {entry_id}")

        entry = JournalEntry.query.get(entry_id)
            
        if entry:
                # Check if the entry belongs to the logged-in user to prevent unauthorized deletion
            if entry.user_id == session.get(CURR_USER_KEY):
                    print("Entry found and user authorized for deletion.")
                    db.session.delete(entry)
                    db.session.commit()
                    print("Entry deleted.")
                    return redirect(url_for('wellness'))
            else:
                    print("User is not authorized for deletion.")
        else:
                print("Entry not found.")

    print("Invalid request or entry not deleted.")
    return redirect(url_for('wellness'))

#___________WELLNESS - CALENDAR_______________________






