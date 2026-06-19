from typing import Dict, Any
from .base_node import ActionNode, NodeExecutionError
from .registry import register_node
from workflows.services.youtube_service import YouTubeService
from workflows.models import Credential

@register_node
class YouTubeNode(ActionNode):
    """
    YouTube Action Node.
    Supports Search, Get Video, Comment.
    """
    
    NODE_TYPE = "youtube"
    DISPLAY_NAME = "YouTube"
    DESCRIPTION = "Interact with YouTube (Search, Get Video, Comment)"
    CATEGORY = "social"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute YouTube operation.
        """
        config = self.config.copy()
        if params:
            config.update(params)
        params = config

        # 1. Resolve Credential
        credential_id = params.get('credential_id')
        if not credential_id:
             raise NodeExecutionError("YouTube node requires a Google Credential.")

        try:
            credential = Credential.objects.get(
                id=credential_id, 
                provider='google', 
                type='google_oauth'
            )
        except Exception as e:
            raise NodeExecutionError(f"Error resolving Google Credential: {str(e)}")
            
        # 1.5 Decrypt
        try:
            from workflows.services.credential_encryption import get_encryption_service
            svc = get_encryption_service()
            cred_data = credential.encrypted_data
            if svc and isinstance(cred_data, str):
                 cred_data = svc.decrypt_credential_str(cred_data)
                 if isinstance(cred_data, str):
                     import json
                     try: cred_data = json.loads(cred_data)
                     except: pass
        except Exception as e:
            raise NodeExecutionError(f"Failed to decrypt credential: {str(e)}")

        # 2. Init Service
        service = YouTubeService(cred_data)
        
        # 3. Resolve Inputs
        operation = params.get('operation', 'search')
        
        result = {}
        
        try:
            if operation == 'search':
                query = self._resolve_template(params.get('query', ''), input_data, context)
                max_results = int(params.get('max_results', 5))
                result = service.search_videos(query, max_results)
                
            elif operation == 'get_video':
                video_id = self._resolve_template(params.get('video_id', ''), input_data, context)
                if not video_id:
                     raise NodeExecutionError("Video ID required")
                result = service.get_video_details(video_id)
                
            elif operation == 'comment':
                video_id = self._resolve_template(params.get('video_id', ''), input_data, context)
                text = self._resolve_template(params.get('comment_text', ''), input_data, context)
                
                if not video_id or not text:
                     raise NodeExecutionError("Video ID and Comment Text required")
                     
                result = service.add_comment(video_id, text)
                
            else:
                raise NodeExecutionError(f"Unknown operation: {operation}")

            return {
                "success": True,
                "output": result
            }

        except Exception as e:
            self.logger.error(f"YouTube Node Execution Failed: {e}")
            raise NodeExecutionError(f"YouTube Error: {str(e)}")

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "credential_id": {
                    "type": "string",
                    "title": "Google Credential",
                    "widget": "credential_select",
                    "credential_type": "google_oauth"
                },
                "operation": {
                    "type": "string",
                    "title": "Operation",
                    "enum": ["search", "get_video", "comment"],
                    "default": "search"
                },
                "query": {
                    "type": "string",
                    "title": "Search Query",
                    "description": "e.g. 'python tutorials'"
                },
                "max_results": {
                    "type": "number",
                    "title": "Max Results",
                    "default": 5
                },
                "video_id": {
                    "type": "string",
                    "title": "Video ID",
                    "description": "ID of the video"
                },
                "comment_text": {
                    "type": "string",
                    "title": "Comment",
                    "widget": "textarea"
                }
            },
            "required": ["credential_id", "operation"]
        }
