import logging
import io
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

class GoogleDriveService:
    """
    Service wrapper for Google Drive API interactions.
    """
    
    SCOPES = ['https://www.googleapis.com/auth/drive']

    def __init__(self, credentials_data: dict):
        """
        Initialize Google Drive Service.
        """
        self.creds = Credentials.from_authorized_user_info(credentials_data, self.SCOPES)
        self.service = build('drive', 'v3', credentials=self.creds)

    def list_files(self, query: str = None, page_size: int = 10):
        """
        List files matching query.
        """
        try:
            results = self.service.files().list(
                q=query,
                pageSize=page_size,
                fields="nextPageToken, files(id, name, mimeType, webViewLink, parents)"
            ).execute()
            files = results.get('files', [])
            logger.info(f"Listed {len(files)} files from Drive")
            return files
        except Exception as e:
            logger.error(f"Google Drive List Error: {e}")
            raise

    def upload_file(self, name: str, content: bytes, mime_type: str, parent_id: str = None):
        """
        Upload a file.
        """
        try:
            file_metadata = {'name': name}
            if parent_id:
                file_metadata['parents'] = [parent_id]
                
            media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=True)
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink'
            ).execute()
            
            logger.info(f"Uploaded file {name} (ID: {file.get('id')})")
            return file
        except Exception as e:
            logger.error(f"Google Drive Upload Error: {e}")
            raise
            
    def create_folder(self, name: str, parent_id: str = None):
        """
        Create a folder.
        """
        try:
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]
                
            file = self.service.files().create(
                body=file_metadata,
                fields='id, name, webViewLink'
            ).execute()
            
            logger.info(f"Created folder {name} (ID: {file.get('id')})")
            return file
        except Exception as e:
            logger.error(f"Google Drive Create Folder Error: {e}")
            raise

    def delete_file(self, file_id: str):
         """
         Delete a file by ID.
         """
         try:
             self.service.files().delete(fileId=file_id).execute()
             logger.info(f"Deleted file {file_id}")
             return True
         except Exception as e:
             logger.error(f"Google Drive Delete Error: {e}")
             raise
