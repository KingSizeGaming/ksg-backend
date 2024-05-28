from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    url_for,
    session,
    send_file,
    jsonify,
    Flask,
    Response,
)
from flask_login import login_required, login_user, current_user, logout_user
from .services import (
    dropbox_upload_file,
    list_folders,
    dropbox_connect,
    get_supabase,
    list_files,
    download_file,
    get_activity_log,
    get_supabase,
    log_activity,
    get_comments_by_activity_id,
    add_comment_to_activity,
    get_image_url,
    add_assignment_to_database,
    get_assignments,
    get_versions_info,
    list_users,
    get_assignment_by_id,
    update_assignment_status,
    list_folders_files,
    update_dashboard_status,
    download_folder_as_zip,
    process_and_upload_file,
    process_and_upload_folder,
)
from .models import User
from werkzeug.utils import secure_filename
import os
from supabase import create_client, Client
from io import BytesIO
from urllib.parse import unquote
import dropbox
import zipfile
from datetime import datetime


def init_routes(app):
    @app.route("/")
    def index():
        return render_template("index.html", user=current_user)

    @app.route("/login")
    def login():
        return render_template("login.html")


    @app.route("/dashboard")
    @login_required
    def dashboard():
        supabase = get_supabase()
        activity_log = get_activity_log(supabase)
        attention_required = [
            log for log in activity_log if log["status"] == "Action Needed"
        ]
        completed = [log for log in activity_log if log["status"] == "Approved"]
        return render_template(
            "dashboard.html",
            activity_log=activity_log,
            attention_required=attention_required,
            completed=completed,
        )

    @app.route("/assignments", methods=["GET"])
    @app.route("/assignments/<path:asset_path>", methods=["GET"])
    @login_required
    def assignments(asset_path=None):
        supabase = get_supabase()
        assignments_data = get_assignments(supabase)
        user_data = list_users()

        return render_template(
            "assignments.html",
            assignments=assignments_data,
            users=user_data,
            asset_path=asset_path,
        )

    @app.route("/get_comments/<string:activity_id>")
    def get_comments(activity_id):

        supabase = get_supabase()
        comments = get_comments_by_activity_id(supabase, activity_id)
        print(comments)
        return jsonify(comments)

    @app.route("/add_comment", methods=["POST"])
    def add_comment():
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        print(data)
        activity_id = data.get("activity_log_id")
        comment = data.get("comment")
        user_email = current_user.email

        try:
            response = add_comment_to_activity(activity_id, user_email, comment)
            return jsonify(response), 200
        except Exception as e:
            print(f"Error adding comment: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/add_assignment", methods=["POST"])
    @login_required
    def add_assignment():
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400

        result = add_assignment_to_database(**data)
        if result["status"] == "error":
            return jsonify(result), 500
        return jsonify(result), 200

    @app.route("/approve_asset/<int:id>", methods=["POST"])
    def approve_asset(id):
        supabase = get_supabase()
        if request.method == "POST":
            # Call the helper function to update the status
            update_dashboard_status(supabase, id)

            return jsonify({"message": "Asset approved successfully"})
        else:
            return jsonify({"error": "Invalid request method"})

    @app.route(
        "/submit_assignment/<int:assignment_id>/<path:asset_path>", methods=["POST"]
    )
    @login_required
    def submit_assignment(assignment_id, asset_path):
        supabase = get_supabase()
        assignment = get_assignment_by_id(supabase, assignment_id)
        print(assignment)
        if not assignment or assignment["completed"]:
            flash("Invalid or already completed assignment.", "error")
            return redirect(url_for("assignments"))

        uploaded_file = request.files.get("file")
        if uploaded_file and uploaded_file.filename:
            filename = secure_filename(uploaded_file.filename)
            temp_dir = os.path.join(current_app.root_path, "temp")
            os.makedirs(temp_dir, exist_ok=True)
            temp_file_path = os.path.join(temp_dir, filename)

            uploaded_file.save(temp_file_path)

            # Decode the URL-encoded file path and ensure it starts with '/'
            decoded_file_path = unquote(asset_path)
            dropbox_file_path = f"/{decoded_file_path}"  # Construct full Dropbox path
            if dropbox_upload_file(temp_file_path, dropbox_file_path):
                os.remove(temp_file_path)
                update_assignment_status(
                    supabase, assignment_id, True
                )  # Set assignment as completed
                print("Assignment submitted successfully.")

            else:
                os.remove(temp_file_path)
                print("Error uploading file to Dropbox.")
        else:
            flash("No file was uploaded.", "error")

        return redirect(url_for("assignments"))

    @app.route("/upload", methods=["GET", "POST"])
    @login_required
    def upload_file():
        dbx = dropbox_connect()
        folder_options = list_folders(dbx)
    
        if request.method == "POST":
            files = request.files.getlist("file")
            directory_files = request.files.getlist("directory")
            selected_folder = request.form.get("folder")
    
            if not files and not directory_files:
                return jsonify({'message': 'No files were uploaded.'}), 400
    
            # Ensure we process files and directories separately
            any_files_uploaded = False
    
            # Process single files
            if files and files[0].filename:
                any_files_uploaded = True
                for uploaded_file in files:
                    process_and_upload_file(uploaded_file, selected_folder, folder_options, dbx)
    
            # Process directory files
            if directory_files and directory_files[0].filename:
                any_files_uploaded = True
                process_and_upload_folder(directory_files, selected_folder, folder_options, dbx)
    
            if any_files_uploaded:
                return render_template("upload_success.html", message='Files uploaded successfully.')
            else:
                return jsonify({'message': 'No files were processed.'}), 400
    
        return render_template("upload.html", folder_options=folder_options)
    


    @app.route("/download", methods=["GET", "POST"])
    @login_required
    def download():
        path = ""  # Define your root Dropbox path
        dbx = dropbox_connect()
        games = list_folders(dbx, path)
        selected_game = request.form.get("game")
        assets = list_folders(dbx, f"{path}/{selected_game}") if selected_game else []
        selected_asset = request.form.get("asset") if "asset" in request.form else None

        versions_info = (
            get_versions_info(dbx, path, selected_game, selected_asset)
            if selected_asset
            else []
        )

        return render_template(
            "download.html",
            games=games,
            selected_game=selected_game,
            assets=assets,
            selected_asset=selected_asset,
            versions=versions_info,
        )

    # @app.route("/download_file/<path:file_path>")
    # def download_file_route(file_path):
    #     # Initialize Dropbox connection
    #     dbx = dropbox_connect()

    #     # Decode the URL-encoded file path and ensure it starts with '/'
    #     decoded_file_path = "/" + unquote(file_path).lstrip("/")
    #     print(f"Decoded file path: {decoded_file_path}")

    #     # Attempt to download the file from Dropbox
    #     try:
    #         _, res = dbx.files_download(decoded_file_path)
    #         if res.status_code == 200:
    #             print("File downloaded successfully")
    #             return send_file(
    #                 BytesIO(res.content),
    #                 as_attachment=True,
    #                 download_name=os.path.basename(file_path),
    #                 mimetype=None,  # Flask will guess the MIME type
    #             )

    #         else:
    #             print(f"Failed to download with status code: {res.status_code}")
    #             return "File not found", 404
    #     except Exception as e:
    #         print(f"Failed to download file: {e}")
    #         return f"An error occurred: {str(e)}", 500

    @app.route("/download_file_folder")
    def download_route():
        path = request.args.get("path")
        if not path:
            return "No path provided", 400

        dbx = dropbox_connect()
        decoded_path = "/" + unquote(path).lstrip("/")

        try:
            metadata = dbx.files_get_metadata(decoded_path)
            if isinstance(metadata, dropbox.files.FileMetadata):
                return download_file(dbx, decoded_path)
            elif isinstance(metadata, dropbox.files.FolderMetadata):
                return download_folder_as_zip(dbx, decoded_path, metadata.name)
            else:
                return "Unsupported metadata type", 400
        except dropbox.exceptions.ApiError as e:
            print(f"Dropbox API error: {e}")
            return f"An error occurred with Dropbox API: {str(e)}", 500
        except Exception as e:
            print(f"Unhandled error: {e}")
            return f"An error occurred: {str(e)}", 500

    @app.route("/supabase_login", methods=["GET", "POST"])
    def supabase_login():
        email = request.form["email"]
        password = request.form["password"]
        supabase: Client = (
            get_supabase()
        )  # Assuming this returns a supabase client instance

        try:
            u = supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            token = supabase.auth.get_session().access_token
            user_details = supabase.auth.get_user(token)
            x = user_details.user
            user_email = x.email
            user_id = x.id

            if u:
                user = User(user_id, user_email)

                login_user(user, remember=True)
                session["user_details"] = {"id": user_id, "email": user_email}
                response = redirect(url_for("dashboard"))
                response.set_cookie("auth", token)
                supabase.auth.sign_out()
                return response
            else:
                flash("Login failed, please try again.")
                return redirect(url_for("login"))
        except Exception as e:
            # Log the exception for debugging
            flash(str(e), "error")
            return redirect(url_for("login"))

    @app.route("/logout")
    def logout():
        logout_user()
        session.clear()  # Clear the session to remove any remaining data
        return redirect(url_for("index"))

    @app.route("/explorer")
    def explorer():
        dbx = dropbox_connect()
        return render_template("explorer.html", files=list_folders_files(dbx, ""))

    @app.route("/folder")
    def folder_contents():
        path = request.args.get("path", "")
        dbx = dropbox_connect()
        return jsonify(list_folders_files(dbx, path))

    @app.route("/preview_asset")
    @login_required
    def preview_asset():
        file_path = request.args.get("path")
        if not file_path:
            return jsonify({"error": "Path parameter is required"}), 400

        dbx = dropbox_connect()
        image_url = get_image_url(dbx, file_path)
        if image_url:
            return jsonify({"url": image_url})
        else:
            return jsonify({"error": "Failed to get image URL"}), 404

    @app.route('/reset', methods=['GET'])
    def reset():
        # Render the create password page; the token will be extracted by JavaScript
        return render_template('create_password.html')

    @app.route('/reset_password', methods=['POST'])
    def reset_password():
        data = request.json
        new_password = data.get('new_password')
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        print(data)
    
        if not new_password or not access_token or not refresh_token:
            return jsonify({'message': 'New password, access token, and refresh token are required'}), 400
    
        supabase = get_supabase()
        try:
            # Set the session using the access token and refresh token
            session_response = supabase.auth.set_session(access_token, refresh_token)
    
            if not session_response:
                return jsonify({'message': 'Failed to set session'}), 400
    
            # Update the password using the established session
            response = supabase.auth.update_user({"password": new_password})
    
            # Check if the response indicates success or failure
            if not response:
                return jsonify({'message': 'Failed to set password'}), 400
            else:
                return jsonify({'message': 'Password set successfully'}), 200
        except Exception as e:
            # Log the exception for debugging
            print(f"Exception occurred: {e}")
            return jsonify({'message': str(e)}), 500
    


    @app.route('/change_password', methods=['GET', 'POST'])
    def change_password():
        supabase = get_supabase()
        if request.method == 'GET':
            return render_template('change_password.html')

        data = request.json
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        user = current_user

        try:
            # Verify the current password by re-authenticating
            u = supabase.auth.sign_in_with_password(
                {"email": user.email, "password": current_password}
            )
            token = supabase.auth.get_session().access_token
            print(token)

            if u:
                # Update the password
                response = supabase.auth.update_user(
                    {"password": new_password, "access_token": token}
                )
                print(response)
                if response:
                    flash("Password changed successfully", "success")
                    return jsonify({'message': 'Password changed successfully'}), 200
                else:
                    flash("Failed to update password", "error")
                    return jsonify({'message': 'Failed to update password'}), 400
            else:
                flash("Current password is incorrect", "error")
                return jsonify({'message': 'Current password is incorrect'}), 400
        except Exception as e:
            # Log the exception for debugging
            flash(str(e), "error")
            return jsonify({'message': str(e)}), 500

