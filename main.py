"""
Mysterious AI - Cinematic YouTube Shorts Auto Pipeline (v2)

Flow:
 1. Gemini  -> JSON (title, SEO description, tags, hook, 6-8 scenes with image keywords)
 2. Pixabay -> one relevant image PER scene (not one image for the whole video)
 3. Edge-TTS (neural voice, gTTS fallback) -> one voice clip per scene (perfect sync)
 4. Cinematic Ken-Burns zoom/pan + vignette + color grade + dip transitions
 5. Word-by-word style captions (3 words at a time, big, yellow/white, outlined)
 6. Generated dark ambient drone + heartbeat music (no download needed)
 7. Upload to YouTube with SEO title/description/hashtags/tags + engagement comment
"""

import os
import re
import json
import time
import random
import asyncio
import shutil
import wave
import traceback
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from gtts import gTTS

from moviepy import (
    VideoClip,
