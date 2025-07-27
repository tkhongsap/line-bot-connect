import logging
import signal
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    """Custom timeout exception for file operations"""
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")


class FileProcessor:
    """Utility for downloading files from LINE"""

    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

    def download_file_from_line(self, line_bot_api, message_id: str, timeout_seconds: int = 10) -> Optional[Dict]:
        """Download a file from LINE using the message ID"""
        try:
            logger.info(f"Downloading file with message_id: {message_id} (timeout: {timeout_seconds}s)")

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)

            try:
                file_content = line_bot_api.get_message_content(message_id)
                file_data = b"".join(chunk for chunk in file_content.iter_content())
            finally:
                signal.alarm(0)

            if len(file_data) > self.MAX_FILE_SIZE:
                logger.warning(f"File too large: {len(file_data)} bytes > {self.MAX_FILE_SIZE}")
                return {
                    "success": False,
                    "error": "File too large (max 20MB)",
                    "error_code": "FILE_TOO_LARGE",
                }

            return {"success": True, "file_data": file_data, "size": len(file_data)}
        except TimeoutError:
            logger.error(f"Timeout downloading file {message_id}")
            return {
                "success": False,
                "error": f"File download timed out after {timeout_seconds} seconds",
                "error_code": "DOWNLOAD_TIMEOUT",
            }
        except Exception as e:
            logger.error(f"Error downloading file {message_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to download file: {str(e)}",
                "error_code": "DOWNLOAD_FAILED",
            }
