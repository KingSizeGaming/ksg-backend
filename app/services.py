# Inside services.py
import os
from datetime import datetime
import dropbox
from config import Config
import pathlib
from flask import current_app, send_file, flash
from supabase import create_client, Client
from io import BytesIO
import re
from dropbox.exceptions import ApiError
from flask_login import current_user


def dropbox_connect():
    return dropbox.Dropbox(
        oauth2_refresh_token=current_app.config["DROPBOX_OAUTH2_REFRESH_TOKEN"],
        app_key=current_app.config["DROPBOX_APP_KEY"],
        app_secret=current_app.config["DROPBOX_APP_SECRET"],
    )


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


from flask import current_app, flash


def log_activity(supabase, user_email, action_type, asset_name, path):
    """Logs user activity to the Supabase table."""
    record = {
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
        "user1@kingsizegames.com",
        "user2@kingsizegames.com",
        "user3@kingsizegames.com",
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


def dropbox_upload_file(local_file_path, dropbox_folder_path):
    """Upload a file to Dropbox from a local path, modifying the filename to include a new timestamp if an old one exists and removing numbers potentially appended after an underscore."""
    dbx = dropbox_connect()
    print(f"Uploading {local_file_path} to Dropbox at {dropbox_folder_path}")
    base_name = pathlib.Path(local_file_path).stem
    extension = pathlib.Path(local_file_path).suffix

    # Regex to remove numbers in parentheses at the end of the file name
    # Updated to also remove underscore followed by one or more digits
    modified_name_regex = re.compile(r"(_\d{14}_\d+|_\d+)$")
    base_name = re.sub(modified_name_regex, "", base_name)

    # New timestamp for version control
    new_timestamp = datetime.now().strftime("_%Y%m%d%H%M%S")
    base_name += new_timestamp

    versioned_file_name = f"{base_name}{extension}"
    versioned_dropbox_path = os.path.join(
        dropbox_folder_path, versioned_file_name
    ).replace("\\", "/")

    try:
        with open(local_file_path, "rb") as f:
            file_data = f.read()
            dbx.files_upload(
                file_data, versioned_dropbox_path, mode=dropbox.files.WriteMode.add
            )
            print(
                f"Uploaded {versioned_file_name} to Dropbox at {versioned_dropbox_path}"
            )
            log_activity(
                get_supabase(),
                current_user.email,
                "upload",
                versioned_file_name,
                versioned_dropbox_path,
            )
            return True
    except ApiError as e:
        print(f"Dropbox API Error: {str(e)}")
        return False


def list_folders(dbx, path=""):
    """List all folders within the specified path."""

    try:
        folders = dbx.files_list_folder(path).entries
        folder_names = [
            folder.name
            for folder in folders
            if isinstance(folder, dropbox.files.FolderMetadata)
        ]
        return folder_names
    except Exception as e:
        print(f"Failed to list folders: {e}")
        return []


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


def download_file(dbx, file_path):
    print(file_path)

    try:
        _, res = dbx.files_download(file_path)
        return res.content
    except Exception as e:
        print(f"Failed to download file: {e}")
        return None


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

def list_folders_files(dbx, path):
    try:
        response = dbx.files_list_folder(path)
        items = [{'name': entry.name, 'path_lower': entry.path_lower, 'type': 'folder' if isinstance(entry, dropbox.files.FolderMetadata) else 'file'} for entry in response.entries]
        return items
    except dropbox.exceptions.ApiError as err:
        print(f"API Error: {err}")
        return []
