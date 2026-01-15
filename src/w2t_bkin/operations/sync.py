import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from w2t_bkin import sync, utils
from w2t_bkin.ingest import bpod as bpod_ingest
from w2t_bkin.ingest import events as ttl_ingest
from w2t_bkin.ingest import pose as pose_ingest
from w2t_bkin.models import BpodData, PoseData, SessionInfo, TrialAlignment, TTLData

logger = logging.getLogger(__name__)
