# Inside services.py
import os
from datetime import datetime
import dropbox
from config import Config  # This line is important
import pathlib
from flask import current_app, send_file, flash
from supabase import create_client, Client
from io import BytesIO


def dropbox_connect():
    return dropbox.Dropbox(
        oauth2_refresh_token=current_app.config['DROPBOX_OAUTH2_REFRESH_TOKEN'],
        app_key=current_app.config['DROPBOX_APP_KEY'],
        app_secret=current_app.config['DROPBOX_APP_SECRET']
    )

def get_image_url(file_path):
    dbx = dropbox_connect()
    full_path = f"/{file_path.lstrip('/')}"  # Ensure the path starts with '/'
    try:
        temp_link = dbx.files_get_temporary_link(full_path)
        return temp_link.link
    except dropbox.exceptions.ApiError as err:
        print(f"API error: {err}")
        return None




def get_supabase():
    url = current_app.config['SUPABASE_URL']
    key = current_app.config['SUPABASE_KEY']
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
    record = {
        "activity_log_id": activity_id,
        "author": user_email,
        "comment": comment
    }
    try:
        response = supabase.table("comments").insert(record).execute()
        if response.error:
            raise Exception(response.error.message)
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def get_activity_log(supabase):
    """Fetches the activity log from Supabase."""
    try:
        response = supabase.table("activity_log").select("*").order('created_at', desc=True).execute()
        return response.data
    except Exception as e:
        flash(f"Error fetching activity log: {e}")
        return None

def get_comments_by_activity_id(supabase, activity_id):
    """Fetches comments for a specific activity log entry from Supabase."""
    try:
        response = supabase.table("comments")\
            .select("*")\
            .eq("activity_log_id", activity_id)\
            .order('created_at', desc=True)\
            .execute()
        return response.data
    except Exception as e:
        flash(f"Error fetching comments: {e}")
        return None



def dropbox_upload_file(local_file_path, dropbox_folder_path):
        """Upload a file to Dropbox from a local path, with an attempt at versioning to avoid overwrites."""
        dbx = dropbox_connect()
        timestamp = datetime.now().strftime("_%Y%m%d%H%M%S")  # For version control
        # add a timestamp to the nd for versioning
        file_name = pathlib.Path(local_file_path).stem
        file_extension = pathlib.Path(local_file_path).suffix
        versioned_file_name = f"{file_name}{timestamp}{file_extension}"
        versioned_dropbox_path = f"{dropbox_folder_path}/{versioned_file_name}".replace(
            "\\", "/"
        )
        CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB chunk size
        file_size = os.path.getsize(local_file_path)
        try:
            with open(local_file_path, "rb") as f:
                if file_size <= CHUNK_SIZE:
                    # File is small enough to upload as a single chunk
                    meta = dbx.files_upload(f.read(), versioned_dropbox_path, mode=dropbox.files.WriteMode.add)
                else:
                    # Perform a chunked upload session
                    upload_session_start_result = dbx.files_upload_session_start(f.read(CHUNK_SIZE))
                    cursor = dropbox.files.UploadSessionCursor(session_id=upload_session_start_result.session_id, offset=f.tell())
                    commit = dropbox.files.CommitInfo(path=versioned_dropbox_path)

                    while f.tell() < file_size:
                        if (file_size - f.tell()) <= CHUNK_SIZE:
                            print(dbx.files_upload_session_finish(f.read(CHUNK_SIZE), cursor, commit))
                        else:
                            dbx.files_upload_session_append_v2(f.read(CHUNK_SIZE), cursor)
                            cursor.offset = f.tell()

                    meta = dbx.files_upload_session_finish(f.read(CHUNK_SIZE), cursor, commit)

                # st.success(f"File uploaded successfully to {versioned_dropbox_path}")
                # log_activity(supabase.auth.get_user(st.session_state['token']).user.email, "upload", file_name)
                return meta
        except Exception as e:
            # st.error(f"Error uploading file to Dropbox: {e}")
            return None 

def list_folders(path=""):
    """List all folders within the specified path."""
    dbx = dropbox_connect()
    try:
        folders = dbx.files_list_folder(path).entries
        folder_names = [folder.name for folder in folders if isinstance(folder, dropbox.files.FolderMetadata)]
        return folder_names
    except Exception as e:
        print(f"Failed to list folders: {e}")
        return []



def list_files(path):
        """List all files within the specified path."""
        dbx = dropbox_connect()
        try:
            files = dbx.files_list_folder(path).entries
            file_names = [
                file.name for file in files if isinstance(file, dropbox.files.FileMetadata)
            ]
            return file_names
        except Exception as e:
            
            return []
        
def download_file(file_path):
    print(file_path)
    dbx = dropbox_connect()

    try:
        _, res = dbx.files_download(file_path)
        return res.content
    except Exception as e:
        print(f"Failed to download file: {e}")
        return None