import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

class YouTubeService:
    """
    Service wrapper for YouTube Data API interactions.
    """
    
    SCOPES = ['https://www.googleapis.com/auth/youtube']

    def __init__(self, credentials_data: dict):
        """
        Initialize YouTube Service.
        """
        self.creds = Credentials.from_authorized_user_info(credentials_data, self.SCOPES)
        self.service = build('youtube', 'v3', credentials=self.creds)

    def search_videos(self, query: str, max_results: int = 5):
        """
        Search for videos by query.
        """
        try:
            request = self.service.search().list(
                part="snippet",
                maxResults=max_results,
                q=query,
                type="video"
            )
            response = request.execute()
            items = response.get('items', [])
            logger.info(f"Found {len(items)} videos for query '{query}'")
            return items
        except Exception as e:
            logger.error(f"YouTube Search Error: {e}")
            raise

    def get_video_details(self, video_id: str):
        """
        Get details for a specific video.
        """
        try:
            request = self.service.videos().list(
                part="snippet,statistics",
                id=video_id
            )
            response = request.execute()
            items = response.get('items', [])
            if items:
                return items[0]
            return None
        except Exception as e:
            logger.error(f"YouTube Get Video Error: {e}")
            raise

    def add_comment(self, video_id: str, text: str):
        """
        Add a top-level comment to a video.
        """
        try:
            request = self.service.commentThreads().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "topLevelComment": {
                            "snippet": {
                                "textOriginal": text
                            }
                        }
                    }
                }
            )
            response = request.execute()
            logger.info(f"Added comment to video {video_id}")
            return response
        except Exception as e:
            logger.error(f"YouTube Add Comment Error: {e}")
            raise
