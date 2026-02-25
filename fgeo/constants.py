"""Global constants and paths for fgeo."""

from pathlib import Path

# Global fgeo home — the IP-level content control center
FGEO_HOME = Path.home() / ".fgeo"
FGEO_CONFIG_FILE = FGEO_HOME / "config.yaml"
FGEO_SKILLS_DIR = FGEO_HOME / "skills"

# fcontext integration
FCONTEXT_DIR_NAME = ".fcontext"
FCONTEXT_TOPICS_DIR = "_topics"
FCONTEXT_CACHE_DIR = "_cache"
