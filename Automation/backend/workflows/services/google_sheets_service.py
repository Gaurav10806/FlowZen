import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    """
    Service wrapper for Google Sheets API interactions.
    """
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    def __init__(self, credentials_data: dict):
        """
        Initialize Google Sheets Service with credential dictionary.
        
        Args:
            credentials_data: Dict containing token, refresh_token, etc.
        """
        self.creds = Credentials.from_authorized_user_info(credentials_data, self.SCOPES)
        self.service = build('sheets', 'v4', credentials=self.creds)

    def append_values(self, spreadsheet_id: str, range_name: str, values: list, value_input_option: str = "USER_ENTERED"):
        """
        Append values to a sheet.
        """
        try:
            body = {
                'values': values
            }
            result = self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body
            ).execute()
            
            logger.info(f"Appended {result.get('updates', {}).get('updatedCells')} cells to {spreadsheet_id}")
            return result
        except Exception as e:
            logger.error(f"Google Sheets Append Error: {e}")
            raise

    def get_values(self, spreadsheet_id: str, range_name: str):
        """
        Read values from a sheet.
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id, range=range_name
            ).execute()
            rows = result.get('values', [])
            logger.info(f"Retrieved {len(rows)} rows from {spreadsheet_id}")
            return rows
        except Exception as e:
            logger.error(f"Google Sheets Get Error: {e}")
            raise

    def update_values(self, spreadsheet_id: str, range_name: str, values: list, value_input_option: str = "USER_ENTERED"):
        """
        Update values in a specific range.
        """
        try:
            body = {
                'values': values
            }
            result = self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body
            ).execute()
            logger.info(f"Updated {result.get('updatedCells')} cells in {spreadsheet_id}")
            return result
        except Exception as e:
            logger.error(f"Google Sheets Update Error: {e}")
            raise

    def clear_values(self, spreadsheet_id: str, range_name: str):
        """
        Clear values from a specific range.
        """
        try:
            result = self.service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            logger.info(f"Cleared range {range_name} in {spreadsheet_id}")
            return result
        except Exception as e:
            logger.error(f"Google Sheets Clear Error: {e}")
            raise

    def find_row(self, spreadsheet_id: str, sheet_name: str, column: str, value: str):
        """
        Find row number where column matches value.
        Basic implementation: Fetches column, searches in memory.
        """
        try:
            # Fetch the specific column (e.g. 'Sheet1!A:A')
            range_name = f"{sheet_name}!{column}:{column}"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id, range=range_name
            ).execute()
            
            rows = result.get('values', [])
            target = str(value).lower().strip()
            
            for index, row in enumerate(rows):
                if row and str(row[0]).lower().strip() == target:
                    # Return 1-based row index
                    return index + 1
                    
            return None
            
        except Exception as e:
            logger.error(f"Google Sheets Lookup Error: {e}")
            raise
