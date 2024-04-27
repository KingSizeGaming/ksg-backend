from flask import render_template, request, redirect, url_for, flash, current_app, url_for, session, send_file, jsonify, Flask, Response
from flask_login import login_required, login_user, current_user, logout_user
from .services import dropbox_upload_file, list_folders, dropbox_connect, get_supabase, list_files, download_file, get_activity_log, get_supabase, log_activity, get_comments_by_activity_id, add_comment_to_activity, get_image_url, add_assignment_to_database, get_assignments, get_versions_info
from .models import User
from werkzeug.utils import secure_filename
import os
from supabase import create_client, Client
from io import BytesIO
from urllib.parse import unquote


def init_routes(app):
    @app.route('/')
    def index():
        return render_template('index.html', user=current_user)

    @app.route('/login')
    def login():
        return render_template('login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        supabase = get_supabase()
        if request.method == 'POST':
            password = request.form.get('password')
            confirm_password = request.form.get('confirmPassword')
            token = request.form.get('registrationToken') 
            print(token)

            if password != confirm_password:
                flash("Passwords do not match!", 'error')
                return redirect(url_for('register'))

            if not token:
                flash("No registration token provided!", 'error')
                return redirect(url_for('register'))

            try:

                result = supabase.auth.sign_up(email=None, password=password)
                if result.error:
                    flash(f"Registration failed: {result.error.message}", 'error')
                    return redirect(url_for('register'))
                flash('Registration successful!', 'success')
                return redirect(url_for('login'))  # Redirect to login page after successful registration
            except Exception as e:
                flash(f"An error occurred: {str(e)}", 'error')
                return redirect(url_for('register'))

        # Serve the registration page
        return render_template('register.html')

    @app.route('/dashboard')
    @login_required
    def dashboard():
        supabase = get_supabase()
        activity_log = get_activity_log(supabase)
        return render_template('dashboard.html', activity_log=activity_log)
    
    @app.route('/assignments')
    @login_required
    def assignments():
        supabase = get_supabase()
        assignments_data = get_assignments(supabase)
        return render_template('assignments.html', assignments=assignments_data)

    @app.route('/get_comments/<string:activity_id>')
    def get_comments(activity_id):

        supabase = get_supabase()
        comments = get_comments_by_activity_id(supabase, activity_id)
        return jsonify(comments)
    
    @app.route('/add_comment', methods=['POST'])
    def add_comment():
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
    
        activity_id = data.get('activity_log_id')
        comment = data.get('comment')
        user_email = current_user.email  # Make sure current_user is authenticated
    
        response = add_comment_to_activity(activity_id, user_email, comment)
        return jsonify(response), 200
    
    @app.route('/add_assignment', methods=['POST'])
    @login_required
    def add_assignment():
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400

        result = add_assignment_to_database(**data)
        if result['status'] == 'error':
            return jsonify(result), 500
        return jsonify(result), 200

    
    @app.route('/upload', methods=['GET', 'POST'])
    @login_required
    def upload_file():
        dbx = dropbox_connect()
        folder_options = list_folders(dbx) 

        if request.method == 'POST':
            uploaded_file = request.files.get('file')
            selected_folder = request.form.get('folder')

            if uploaded_file and uploaded_file.filename:
                filename = secure_filename(uploaded_file.filename)
                temp_dir = os.path.join(current_app.root_path, 'temp')
                os.makedirs(temp_dir, exist_ok=True)  # Ensure the directory exists
                temp_file_path = os.path.join(temp_dir, filename)

                uploaded_file.save(temp_file_path)  # Save the file to the temporary directory

                if selected_folder in folder_options:
                    dropbox_file_path = f"/{selected_folder}/{filename}"
                    success = dropbox_upload_file(temp_file_path, dropbox_file_path)

                    os.remove(temp_file_path)  # Clean up the temporary file after upload

                    if success:
                        flash('File uploaded successfully.')
                        log_activity(get_supabase(), current_user.email, 'upload', filename, dropbox_file_path)

                    else:
                        flash('Error uploading file to Dropbox.')
                else:
                    flash('Invalid folder selected.', 'error')
            else:
                flash('No file was uploaded.', 'error')

            return redirect(url_for('upload_file'))

        return render_template('upload.html', folder_options=folder_options)
    
    @app.route('/download', methods=['GET', 'POST'])
    @login_required

    def download():
        path = ""  # Define your root Dropbox path
        dbx = dropbox_connect()
        games = list_folders(dbx, path)
        selected_game = request.form.get('game')
        assets = list_folders(dbx, f"{path}/{selected_game}") if selected_game else []
        selected_asset = request.form.get('asset') if 'asset' in request.form else None

        versions_info = get_versions_info(dbx, path, selected_game, selected_asset) if selected_asset else []

        return render_template('download.html', games=games, selected_game=selected_game,
                               assets=assets, selected_asset=selected_asset,
                               versions=versions_info)
    
    @app.route('/download_file/<path:file_path>')
    def download_file_route(file_path):
        # Initialize Dropbox connection
        dbx = dropbox_connect()

        # Decode the URL-encoded file path and ensure it starts with '/'
        decoded_file_path = '/' + unquote(file_path).lstrip('/')
        print(f"Decoded file path: {decoded_file_path}")

        # Attempt to download the file from Dropbox
        try:
            _, res = dbx.files_download(decoded_file_path)
            if res.status_code == 200:
                print("File downloaded successfully")
                return send_file(BytesIO(res.content), attachment_filename=os.path.basename(decoded_file_path), as_attachment=True)
            else:
                print(f"Failed to download with status code: {res.status_code}")
                return "File not found", 404
        except Exception as e:
            app.logger.error(f"Failed to download file: {e}")
            return f"An error occurred: {str(e)}", 500

    @app.route('/supabase_login', methods=['GET', 'POST'])
    def supabase_login():
        email = request.form['email']
        password = request.form['password']
        supabase: Client = get_supabase()  # Assuming this returns a supabase client instance

        try:
            u = supabase.auth.sign_in_with_password({'email': email, "password": password})
            token = supabase.auth.get_session().access_token
            user_details = supabase.auth.get_user(token)
            x= user_details.user
            user_email = x.email
            user_id = x.id
            
            if u:
                user = User(user_id, user_email)
                
                login_user(user, remember=True)
                session['user_details'] = {'id': user_id, 'email': user_email}
                response = redirect(url_for('dashboard'))
                response.set_cookie('auth', token)
                supabase.auth.sign_out()
                return response
            else:
                flash("Login failed, please try again.")
                return redirect(url_for('login'))
        except Exception as e:
            # Log the exception for debugging
            flash(str(e), 'error')
            return redirect(url_for('login'))
        
    @app.route('/logout')
    def logout():
        logout_user()
        session.clear()  # Clear the session to remove any remaining data
        return redirect(url_for('index'))

    # @app.route('/register', methods=['GET', 'POST'])
    # def register():
    #     if request.method == 'POST':
    #         email = request.form['email']
    #         password = request.form['password']
    #         user, error = register_user(email, password)
    #         if error:
    #             flash(error)
    #         else:
    #             flash('Registration successful! Please log in.')
    #             return redirect(url_for('login'))
    #     return render_template('register.html')