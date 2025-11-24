#!/usr/bin/env python3
"""
Version information for UWB MQTT Publisher.
"""

__version__ = "1.4.5"
__version_info__ = (1, 4, 4)

# Git commit hash (will be updated on commit)
__git_hash__ = "3f70e4f"


def get_version():
    """Get the full version string with git hash."""
    if __git_hash__ and __git_hash__ != "dev":
        return f"{__version__}+{__git_hash__}"
    return __version__
