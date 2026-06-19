"""
Utility Nodes

Nodes for data transformation, ingestion, and debugging.
"""
from typing import Dict, Any
from .base_node import BaseNode, NodeExecutionError
from .registry import register_node
import json
import logging

logger = logging.getLogger(__name__)

@register_node
class MarkdownNode(BaseNode):
    """
    Markdown Transformer - Convert Markdown to HTML.
    """
    NODE_TYPE = "markdown"
    DISPLAY_NAME = "Markdown to HTML"
    DESCRIPTION = "Convert Markdown text to HTML"
    CATEGORY = "utility"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        markdown_text = params.get('content', '')
        resolved_text = self._resolve_template(markdown_text, input_data, context)
        
        try:
            import markdown
            html = markdown.markdown(str(resolved_text))
            return {**input_data, "html": html}
        except ImportError:
            raise NodeExecutionError("Markdown library not installed. Please install 'markdown' package.")
        except Exception as e:
            raise NodeExecutionError(f"Markdown conversion failed: {e}")

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "title": "Markdown Content",
                    "widget": "textarea",
                    "rows": 5
                }
            }
        }


@register_node
class RssNode(BaseNode):
    """
    RSS Reader - Fetch and Parse RSS Feed.
    """
    NODE_TYPE = "rss_read"
    DISPLAY_NAME = "RSS Reader"
    DESCRIPTION = "Fetch entries from an RSS feed"
    CATEGORY = "utility"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        url = params.get('url', '')
        resolved_url = self._resolve_template(url, input_data, context)
        
        try:
            import feedparser
            feed = feedparser.parse(resolved_url)
            
            entries = []
            for entry in feed.entries[:20]: # Limit to 20
                entries.append({
                    "title": entry.get('title'),
                    "link": entry.get('link'),
                    "published": entry.get('published'),
                    "summary": entry.get('summary'),
                    "id": entry.get('id')
                })
                
            return {
                **input_data,
                "feed_title": feed.feed.get('title'),
                "entries": entries,
                "count": len(entries)
            }
            
        except ImportError:
            raise NodeExecutionError("feedparser library not installed. Please install 'feedparser'.")
        except Exception as e:
            raise NodeExecutionError(f"Failed to fetch RSS feed: {e}")

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "title": "Feed URL"}
            }
        }


@register_node
class PayloadInspectorNode(BaseNode):
    """
    Debug Node - Inspect Payload.
    Just passes data through but logs it (and in future can show in UI).
    """
    NODE_TYPE = "inspector"
    DISPLAY_NAME = "Payload Inspector"
    DESCRIPTION = "Debug helper to inspect data"
    CATEGORY = "utility"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # Log to execution log
        try:
            logger.info(f"INSPECTOR [{context.get('current_node_id')}]: {json.dumps(input_data, default=str)[:1000]}")
        except:
             logger.info(f"INSPECTOR [{context.get('current_node_id')}]: <non-serializable data>")
             
        return input_data

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "description": "No configuration needed. Just connect to inspect data."
        }