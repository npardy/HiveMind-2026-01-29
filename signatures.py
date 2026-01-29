"""
Email Signatures for Hive Mind
Provides HTML signatures with embedded logo for automated emails.
"""

import os
import logging
from config_loader import get_config

logger = logging.getLogger(__name__)


def _get_signatures_dir() -> str:
    """Get signatures directory from config."""
    try:
        cfg = get_config()
        sig_dir = cfg.signatures_folder
        logger.debug(f"Signatures directory from config: {sig_dir}")
        return sig_dir
    except Exception as e:
        logger.warning(f"Failed to get signatures folder from config: {e}")
        return r"H:\signatures"


def get_signature_html_body(signature_type: str) -> str:
    """
    Get the HTML body content for a signature.
    
    Args:
        signature_type: "claude" or "nick"
        
    Returns:
        HTML string for the signature, or empty string if not found
    """
    if signature_type.lower() == "claude":
        sig_file = os.path.join(_get_signatures_dir(), "claude_signature.html")
    elif signature_type.lower() == "nick":
        sig_file = os.path.join(_get_signatures_dir(), "nick_signature.html")
    else:
        return ""
    
    try:
        logger.info(f"Loading signature from: {sig_file}")
        with open(sig_file, 'r', encoding='utf-8') as f:
            content = f.read()
            logger.info(f"Loaded signature file, {len(content)} bytes")
            # Extract just the body content (between <body> tags)
            if '<body' in content and '</body>' in content:
                start = content.find('>', content.find('<body')) + 1
                end = content.find('</body>')
                body_content = content[start:end].strip()
                logger.info(f"Extracted body content, {len(body_content)} bytes")
                return body_content
            return content
    except FileNotFoundError:
        logger.error(f"Signature file not found: {sig_file}")
        return ""
    except Exception as e:
        logger.error(f"Error loading signature from {sig_file}: {e}")
        return ""


def get_signature_full_html(signature_type: str) -> str:
    """
    Get the complete HTML file for a signature.
    
    Args:
        signature_type: "claude" or "nick"
        
    Returns:
        Full HTML string, or empty string if not found
    """
    if signature_type.lower() == "claude":
        sig_file = os.path.join(_get_signatures_dir(), "claude_signature.html")
    elif signature_type.lower() == "nick":
        sig_file = os.path.join(_get_signatures_dir(), "nick_signature.html")
    else:
        return ""
    
    try:
        with open(sig_file, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except Exception as e:
        print(f"Error loading signature: {e}")
        return ""
