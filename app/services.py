# Inside services.py
import os
from datetime import datetime
import dropbox
from config import Config
import pathlib
from flask import current_app, send_file, flash, redirect, url_for
from supabase import create_client, Client
from io import BytesIO
import re
from dropbox.exceptions import ApiError
from flask_login import current_user
from werkzeug.utils import secure_filename
import time
import requests
from dropbox.exceptions import HttpError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def dropbox_connect():
    return dropbox.Dropbox(
        oauth2_refresh_token=current_app.config["DROPBOX_OAUTH2_REFRESH_TOKEN"],
        app_key=current_app.config["DROPBOX_APP_KEY"],
        app_secret=current_app.config["DROPBOX_APP_SECRET"],
    )


def create_temp_dir(base_dir):
    temp_dir = os.path.join(base_dir, "temp", "upload")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def get_versions_info(dbx, path, game, asset):
    versions_paths = list_files(dbx, f"{path}/{game}/{asset}")
    versions_info = [
        {
            "filename": version_path.split("/")[-1],
            "filepath": version_path,
            "thumbnail_url": get_image_url(dbx, f"/{game}/{asset}/{version_path}"),
        }
        for version_path in versions_paths
    ]
    versions_info.reverse()  # Reverse to show newest first
    return versions_info


def get_image_url(dbx, file_path):

    full_path = f"/{file_path.lstrip('/')}"  # Ensure the path starts with '/'
    try:
        temp_link = dbx.files_get_temporary_link(full_path)
        return temp_link.link
    except dropbox.exceptions.ApiError as err:
        print(f"API error: {err}")
        return None


def get_supabase():
    url = current_app.config["SUPABASE_URL"]
    key = current_app.config["SUPABASE_KEY"]
    return create_client(url, key)


def register_user(email, password):
    supabase = get_supabase()
    user, error = supabase.auth.sign_up(email=email, password=password)
    if error:
        return None, str(error)
    return user, None


def log_activity(status, supabase, user_email, action_type, asset_name, path):
    """Logs user activity to the Supabase table."""
    record = {
        "status": status,
        "user_email": user_email,
        "action_type": action_type,
        "asset_name": asset_name,
        "path": path,
    }
    try:
        response = supabase.table("activity_log").insert(record).execute()
        return response
    except Exception as e:
        flash(f"Error logging activity: {e}")


def add_comment_to_activity(activity_id, user_email, comment):
    supabase = get_supabase()
    record = {"activity_log_id": activity_id, "author": user_email, "comment": comment}
    try:
        response = supabase.table("comments").insert(record).execute()
        if response.error:
            raise Exception(response.error.message)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def add_assignment_to_database(
    assigned_to,
    assigned_by,
    asset_path,
    upload_path,
    assignment_details,
    to_be_completed_by,
    completed,
):
    supabase = get_supabase()
    record = {
        "assigned_to": assigned_to,
        "assigned_by": assigned_by,
        "asset_path": asset_path,
        "upload_path": upload_path,
        "details": assignment_details,
        "to_be_completed_by": to_be_completed_by,
        "completed": completed,
    }
    try:
        response = supabase.table("assignments").insert(record).execute()
        if response.error:
            raise Exception(response.error.message)
        return {"status": "success", "message": "Assignment added successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def list_users():
    # Hardcoded list of user emails
    data = [
        "aburden@kingsizegames.com",
        "ddewaal@kingsizegames.com",
        "jerico@kingsizegames.com",
        "jul@kingsizegames.com",
        "kwilcox@kingsizegames.com",
        "marc@kingsizegames.com",
        "math@kingsizegames.com",
        "mc@kingsizegames.com",
        "mitz@kingsizegames.com",
        "prince@kingsizegames.com",
        "ruth@kingsizegames.com",
        "whavenga@kingsizegames.com",
    ]
    return data


def get_activity_log(supabase):
    """Fetches the activity log from Supabase."""
    try:
        response = (
            supabase.table("activity_log")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return response.data
    except Exception as e:
        flash(f"Error fetching activity log: {e}")
        return None


def get_assignments(supabase):
    """Fetches the assignments from Supabase."""
    try:
        response = (
            supabase.table("assignments")
            .select("*")
            .order("to_be_completed_by", desc=False)
            .execute()
        )
        return response.data
    except Exception as e:
        flash(f"Error fetching assignments: {e}")
        return None


def get_assignment_by_id(supabase, assignment_id):
    """Fetches a specific assignment by ID from Supabase."""
    try:
        response = (
            supabase.table("assignments")
            .select("*")
            .eq("id", assignment_id)
            .single()
            .execute()
        )
        return response.data
    except Exception as e:
        flash(f"Error fetching assignment: {e}")
        return None


def update_dashboard_status(supabase, id):

    try:
        # Update the assignment status to completed
        response = (
            supabase.table("activity_log")
            .update({"status": "Approved"})
            .eq("id", id)
            .execute()
        )

        print("Entry status updated successfully.")
    except Exception as e:
        print(f"Error updating entry status: {str(e)}")


def update_assignment_status(supabase, assignment_id, completed):

    try:
        # Update the assignment status to completed
        response = (
            supabase.table("assignments")
            .update({"completed": True})
            .eq("id", assignment_id)
            .execute()
        )

        print("Assignment status updated successfully.")
    except Exception as e:
        print(f"Error updating assignment status: {str(e)}")


def get_comments_by_activity_id(supabase, activity_id):
    """Fetches comments for a specific activity log entry from Supabase."""
    try:
        response = (
            supabase.table("comments")
            .select("*")
            .eq("activity_log_id", activity_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data
    except Exception as e:
        flash(f"Error fetching comments: {e}")
        return None


def dropbox_upload_file(
    local_path, dropbox_path, chunk_size=100 * 1024 * 1024, max_retries=5, retry_delay=2
):
    dbx = dropbox_connect()
    file_size = os.path.getsize(local_path)

    with open(local_path, "rb") as f:
        if file_size <= chunk_size:
            return attempt_upload(dbx, f, dropbox_path, max_retries, retry_delay)
        else:
            return upload_large_file_in_chunks(
                dbx, f, dropbox_path, file_size, chunk_size, max_retries, retry_delay
            )


def attempt_upload(dbx, file_handle, dropbox_path, max_retries, retry_delay):
    for attempt in range(max_retries):
        try:
            dbx.files_upload(file_handle.read(), dropbox_path, mute=True)
            logger.info(f"Successfully uploaded file to Dropbox: {dropbox_path}")
            return True
        except (ApiError, HttpError, requests.exceptions.ConnectionError) as err:
            logger.error(
                f"Attempt {attempt + 1} failed to upload {dropbox_path}: {err}"
            )
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(
                    f"Failed to upload {dropbox_path} after {max_retries} attempts."
                )
                return False


def upload_large_file_in_chunks(
    dbx, file_handle, dropbox_path, file_size, chunk_size, max_retries, retry_delay
):
    try:
        if file_size <= chunk_size:
            upload_session_start_result = dbx.files_upload_session_start(
                file_handle.read()
            )
            cursor = dropbox.files.UploadSessionCursor(
                session_id=upload_session_start_result.session_id,
                offset=file_handle.tell(),
            )
            commit = dropbox.files.CommitInfo(path=dropbox_path)
            dbx.files_upload_session_finish(file_handle.read(), cursor, commit)
            return True
        else:
            upload_session_start_result = dbx.files_upload_session_start(
                file_handle.read(chunk_size)
            )
            cursor = dropbox.files.UploadSessionCursor(
                session_id=upload_session_start_result.session_id,
                offset=file_handle.tell(),
            )
            commit = dropbox.files.CommitInfo(path=dropbox_path)

            while file_handle.tell() < file_size:
                if (file_size - file_handle.tell()) <= chunk_size:
                    attempt_upload_session_finish(
                        dbx,
                        file_handle.read(chunk_size),
                        cursor,
                        commit,
                        max_retries,
                        retry_delay,
                    )
                else:
                    attempt_upload_session_append(
                        dbx,
                        file_handle.read(chunk_size),
                        cursor,
                        max_retries,
                        retry_delay,
                    )
                    cursor.offset = file_handle.tell()
            return True
    except Exception as err:
        logger.error(f"Failed to start or continue upload session: {err}")
        return False


def attempt_upload_session_append(dbx, data, cursor, max_retries, retry_delay):
    for attempt in range(max_retries):
        try:
            dbx.files_upload_session_append_v2(data, cursor)
            return
        except (ApiError, HttpError, requests.exceptions.ConnectionError) as err:
            logger.error(f"Attempt {attempt + 1} failed during session append: {err}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(
                    f"Failed to append to upload session after {max_retries} attempts."
                )
                raise


def attempt_upload_session_finish(dbx, data, cursor, commit, max_retries, retry_delay):
    for attempt in range(max_retries):
        try:
            dbx.files_upload_session_finish(data, cursor, commit)
            return
        except (ApiError, HttpError, requests.exceptions.ConnectionError) as err:
            logger.error(f"Attempt {attempt + 1} failed during session finish: {err}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(
                    f"Failed to finish upload session after {max_retries} attempts."
                )
                raise


def list_folders(dbx, path=""):
    try:
        folders = dbx.files_list_folder(path).entries
        folder_names = [
            folder.name
            for folder in folders
            if isinstance(folder, dropbox.files.FolderMetadata)
        ]
        return folder_names
    except Exception as e:
        logger.error(f"Failed to list folders: {e}")
        return []


def remove_existing_timestamp(filename):
    pattern = re.compile(r"_\d{8}_\d{6}$")
    name, ext = os.path.splitext(filename)
    name = re.sub(pattern, "", name)
    return f"{name}{ext}"


def process_and_upload_file(uploaded_file, selected_folder, folder_options, dbx):
    filename = secure_filename(uploaded_file.filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = remove_existing_timestamp(filename)
    filename = f"{filename.rsplit('.', 1)[0]}_{timestamp}.{filename.rsplit('.', 1)[1]}"
    temp_dir = create_temp_dir(current_app.root_path)
    temp_file_path = os.path.join(temp_dir, filename)

    try:
        uploaded_file.save(temp_file_path)  # Save the file to the temporary directory
        logger.info(f"Saved file to temporary path: {temp_file_path}")

        if selected_folder in folder_options:
            dropbox_file_path = f"/{selected_folder}/{filename}"
            success = upload_file_with_retries(temp_file_path, dropbox_file_path, dbx)

            if success:
                log_activity(
                    "Action Needed",
                    get_supabase(),
                    current_user.email,
                    "upload",
                    filename,
                    dropbox_file_path,
                )
            else:
                flash("Error uploading file to Dropbox.", "error")
                log_activity(
                    "failure",
                    get_supabase(),
                    current_user.email,
                    "upload",
                    filename,
                    dropbox_file_path,
                )
    finally:
        os.remove(temp_file_path)  # Clean up the temporary file after upload


def process_and_upload_folder(directory_files, selected_folder, folder_options, dbx):
    temp_dir = create_temp_dir(current_app.root_path)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    original_folder_name = directory_files[0].filename.split("/")[0]
    original_folder_name = remove_existing_timestamp(original_folder_name)

    new_folder_name = f"{original_folder_name}_{timestamp}"

    for directory_file in directory_files:
        if directory_file.filename:
            relative_path = directory_file.filename.replace(
                original_folder_name, new_folder_name, 1
            )
            file_path = os.path.join(temp_dir, relative_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            directory_file.save(file_path)

    all_success = True
    for root, _, files in os.walk(temp_dir):
        for file in files:
            local_file_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_file_path, temp_dir)
            dropbox_path = (
                f"/{selected_folder}/{relative_path.replace(os.path.sep, '/')}"
            )
            success = upload_file_with_retries(local_file_path, dropbox_path, dbx)
            if not success:
                all_success = False

    cleanup_temp_dir(temp_dir)

    if all_success:
        log_activity(
            "Action Needed",
            get_supabase(),
            current_user.email,
            "upload",
            new_folder_name,
            f"/{selected_folder}/{new_folder_name}",
        )
    else:
        log_activity(
            "failure",
            get_supabase(),
            current_user.email,
            "upload",
            new_folder_name,
            f"/{selected_folder}/{new_folder_name}",
        )


def upload_file_with_retries(local_file_path, dropbox_path, dbx, retries=5):
    for attempt in range(retries):
        try:
            success = dropbox_upload_file(local_file_path, dropbox_path)
            if success:
                flash(f"Successfully uploaded file to Dropbox: {dropbox_path}")
                return True
        except Exception as e:
            flash(f"Attempt {attempt + 1} failed to upload {dropbox_path}: {e}")
            if attempt < retries - 1:
                flash(
                    f"Retrying upload for {dropbox_path} (attempt {attempt + 2}/{retries})"
                )
                time.sleep(2**attempt)  # Exponential backoff
    return False


def cleanup_temp_dir(temp_dir):
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(temp_dir)


def list_files(dbx, path):
    """List all files within the specified path."""

    try:
        files = dbx.files_list_folder(path).entries
        file_names = [
            file.name for file in files if isinstance(file, dropbox.files.FileMetadata)
        ]
        return file_names
    except Exception as e:

        return []


def download_file(dbx, path):
    try:
        _, res = dbx.files_download(path)
        if res.status_code == 200:
            return send_file(
                BytesIO(res.content),
                as_attachment=True,
                download_name=os.path.basename(path),
                mimetype=None,
            )
        else:
            print(f"Failed to download file with status code: {res.status_code}")
            return "File not found", 404
    except Exception as e:
        print(f"Error downloading file: {e}")
        return "Error downloading file", 500


def download_folder_as_zip(dbx, path, folder_name):
    try:
        _, res = dbx.files_download_zip(path)
        if res.status_code == 200:
            zip_buffer = BytesIO(res.content)
            zip_buffer.seek(0)
            return send_file(
                zip_buffer,
                as_attachment=True,
                download_name=f"{folder_name}",
                mimetype="application/zip",
            )
        else:
            print(f"Failed to download folder with status code: {res.status_code}")
            return "Folder not found", 404
    except Exception as e:
        print(f"Error downloading folder: {e}")
        return "Error downloading folder", 500


def list_folders_files(dbx, path):
    try:
        response = dbx.files_list_folder(path)
        items = [
            {
                "name": entry.name,
                "path_lower": entry.path_lower,
                "type": (
                    "folder"
                    if isinstance(entry, dropbox.files.FolderMetadata)
                    else "file"
                ),
            }
            for entry in response.entries
        ]
        return items
    except dropbox.exceptions.ApiError as err:
        print(f"API Error: {err}")
        return []
