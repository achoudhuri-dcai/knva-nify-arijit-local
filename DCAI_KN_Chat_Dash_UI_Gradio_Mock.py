# -*- coding: utf-8 -*-
"""
DCAI KN Chat - for NIF Kellanova assistant
Created on Mon May 20
@authors:
    Kristen McCaffrey
    Justin Replogle

###### HISTORY ######

2025-05-01 KM   Mock up using wireframe picture from Nolen
2025-09-29 JR   Being modifying for implementation. Using AWS LLMs (Claude & GPT-OSS) instead of Azure (GPT4o)
"""
#%% Contents
# -----------------------------------------------------------------------------------------------
# ### Framework
# 1. Startup & Imports
# 2. Initialize App (i.e., the web app)
# 3. Global Program Elements (e.g. read in data and prep it)
# 4. Layout (i.e, the UI layout)
# 5. Callbacks (functions that respond to UI)
# 6. Run App
# -----------------------------------------------------------------------------------------------

#%% 1. STARTUP & IMPORTS

# standard library packages (included with python and always available)
import os, sys, datetime as dt
import inspect
import base64
import re
import uuid
import threading
from typing import List, Tuple, Optional
from io import StringIO
from dotenv import find_dotenv, load_dotenv, dotenv_values
dotenv_loaded = load_dotenv()
dotenv_dict = dotenv_values()
if dotenv_loaded:
    print('> Environment file loaded.')
else:
    print('> Environment file is either empty or not found!')

# Langroid parses DEBUG as a strict boolean. Some shells set DEBUG to values
# like "release", which crashes startup before the app initializes.
debug_env_value = os.getenv("DEBUG")
if debug_env_value is not None:
    normalized_debug = debug_env_value.strip().lower()
    valid_debug_values = {
        "", "0", "1", "false", "true", "f", "t", "no", "yes", "n", "y", "off", "on"
    }
    if normalized_debug not in valid_debug_values:
        print(f"> WARNING: Invalid DEBUG={debug_env_value!r}; forcing DEBUG='false'.")
        os.environ["DEBUG"] = "false"

print(f"[{dt.datetime.now().strftime('%Y%m%d_%H%M%S.%f')[:19]}] Starting {__name__}")
print(f"[{dt.datetime.now().strftime('%Y%m%d_%H%M%S.%f')[:19]}] cwd = {os.getcwd()}")
print(f"[{dt.datetime.now().strftime('%Y%m%d_%H%M%S.%f')[:19]}] {sys.path[:2] = }")
print(f"[{dt.datetime.now().strftime('%Y%m%d_%H%M%S.%f')[:19]}] {sys.version = }")

# Third party packages (ie, those installed with pip )
from dash import  html, dcc, Input, Output, State, dash_table, ctx, callback, no_update
import dash
import dash_bootstrap_components as dbc
import dash_daq as daq
import dash_auth
import flask
from pathlib import Path
import urllib.parse
import shutil
import json
from datetime import datetime, timedelta
import sqlite3
import pandas as pd
import numpy as np

# private (fa) libraries
from lib.fa_dash_utils import instantiate_app
import lib.projects_lib as pr
import lib.knova_utils as utils
import lib.data_processing_utilities as dpu

# agent libraries
import langroid as lr
import langroid.language_models as lrlm
from langroid.language_models import Role, LLMMessage
from langroid.agent.task import Task
from langroid.agent.tools import RecipientTool, DoneTool, DonePassTool, AgentDoneTool
from langroid.mytypes import Entity
from langroid.utils.constants import DONE, NO_ANSWER
import langroid.utils.constants as lrc

#%% 2. INITIALIZE APP
###############################################################################################
# - App named here... if name is changed here, must also be changed elsewhere below
# - Either JupyterDash or just Dash for traditional .py program in Spyder. (Latter requires: 'from dash import Dash' above)
# - There are other dbc.themes (e.g. "SANDSTONE") and other options besides dash_bootstrap_components
###############################################################################################
#### Version Number
#!!! Add timestamp
# 2025-11-11: For SBX, version should reflect Module 3
version_number = '03/03/2026'

# 2025-11-11: For TEST, version should reflect Module 4/5 with updates from KNova feedback (0.2)
# version_number = 0.2

#### Toggle extra output for test / debug (True or False)
# Keep user UI clean by default; enable only when troubleshooting.
extra_output_bool = os.getenv("NIFTY_EXTRA_OUTPUT", "false").strip().lower() in {
    "1", "true", "t", "yes", "y", "on"
}

# NIF DB response mode:
# - legacy: keep prior markdown-only response behavior
# - enhanced: include markdown + structured table output
NIF_DB_OUTPUT_MODE = os.getenv("NIF_DB_OUTPUT_MODE", "enhanced").strip().lower()
if NIF_DB_OUTPUT_MODE not in {"legacy", "enhanced"}:
    print(
        f"> WARNING: Invalid NIF_DB_OUTPUT_MODE={NIF_DB_OUTPUT_MODE!r}; using 'enhanced'."
    )
    NIF_DB_OUTPUT_MODE = "enhanced"
NIF_DB_ENHANCED_OUTPUT = NIF_DB_OUTPUT_MODE == "enhanced"

# NIF DB SQL generation mode:
# - first_pass: force SQL tool-call in first response for database questions.
# - legacy: keep prior greeting/clarification-first behavior.
NIF_DB_SQL_GENERATION_MODE = os.getenv(
    "NIF_DB_SQL_GENERATION_MODE", "first_pass"
).strip().lower()
if NIF_DB_SQL_GENERATION_MODE not in {"first_pass", "legacy"}:
    print(
        f"> WARNING: Invalid NIF_DB_SQL_GENERATION_MODE={NIF_DB_SQL_GENERATION_MODE!r}; using 'first_pass'."
    )
    NIF_DB_SQL_GENERATION_MODE = "first_pass"
NIF_DB_FORCE_FIRST_PASS_SQL = NIF_DB_SQL_GENERATION_MODE == "first_pass"

_nif_db_first_pass_turns_raw = os.getenv("NIF_DB_FIRST_PASS_TURNS", "4").strip()
try:
    NIF_DB_FIRST_PASS_TURNS = max(1, int(_nif_db_first_pass_turns_raw))
except Exception:
    print(
        f"> WARNING: Invalid NIF_DB_FIRST_PASS_TURNS={_nif_db_first_pass_turns_raw!r}; using 4."
    )
    NIF_DB_FIRST_PASS_TURNS = 4

_nif_db_max_rows_raw = os.getenv("NIF_DB_MAX_ROWS", "2000").strip()
try:
    NIF_DB_MAX_ROWS = int(_nif_db_max_rows_raw)
except Exception:
    print(
        f"> WARNING: Invalid NIF_DB_MAX_ROWS={_nif_db_max_rows_raw!r}; using 2000."
    )
    NIF_DB_MAX_ROWS = 2000

# Hard cap to avoid oversized payloads in UI callback state.
NIF_DB_MAX_ROWS = max(1, min(NIF_DB_MAX_ROWS, 2000))

NIF_DB_TRACE_INCLUDE_ROWS = os.getenv("NIF_DB_TRACE_INCLUDE_ROWS", "true").strip().lower() in {
    "1", "true", "t", "yes", "y", "on"
}
NIF_DB_SHOW_SQL_TRACE = os.getenv("NIF_DB_SHOW_SQL_TRACE", "false").strip().lower() in {
    "1", "true", "t", "yes", "y", "on"
}
NIF_DB_SHOW_OUTPUT_RECORDS = os.getenv("NIF_DB_SHOW_OUTPUT_RECORDS", "false").strip().lower() in {
    "1", "true", "t", "yes", "y", "on"
}
_nif_db_trace_preview_rows_raw = os.getenv(
    "NIF_DB_TRACE_PREVIEW_ROWS", str(NIF_DB_MAX_ROWS)
).strip()
try:
    NIF_DB_TRACE_PREVIEW_ROWS = int(_nif_db_trace_preview_rows_raw)
except Exception:
    print(
        f"> WARNING: Invalid NIF_DB_TRACE_PREVIEW_ROWS={_nif_db_trace_preview_rows_raw!r}; "
        f"using {NIF_DB_MAX_ROWS}."
    )
    NIF_DB_TRACE_PREVIEW_ROWS = NIF_DB_MAX_ROWS
NIF_DB_TRACE_PREVIEW_ROWS = max(0, min(NIF_DB_TRACE_PREVIEW_ROWS, NIF_DB_MAX_ROWS))

_nif_db_prompt_max_abbr_raw = os.getenv("NIF_DB_PROMPT_MAX_ABBREVIATIONS", "20").strip()
try:
    NIF_DB_PROMPT_MAX_ABBREVIATIONS = int(_nif_db_prompt_max_abbr_raw)
except Exception:
    print(
        f"> WARNING: Invalid NIF_DB_PROMPT_MAX_ABBREVIATIONS={_nif_db_prompt_max_abbr_raw!r}; "
        "using 20."
    )
    NIF_DB_PROMPT_MAX_ABBREVIATIONS = 20
NIF_DB_PROMPT_MAX_ABBREVIATIONS = max(0, min(NIF_DB_PROMPT_MAX_ABBREVIATIONS, 200))

NIF_RESUME_VERBOSE_CONTEXT = os.getenv(
    "NIF_RESUME_VERBOSE_CONTEXT", "false"
).strip().lower() in {
    "1", "true", "t", "yes", "y", "on"
}

_nif_resume_summary_fields_raw = os.getenv("NIF_RESUME_SUMMARY_FIELDS", "6").strip()
try:
    NIF_RESUME_SUMMARY_FIELDS = int(_nif_resume_summary_fields_raw)
except Exception:
    print(
        f"> WARNING: Invalid NIF_RESUME_SUMMARY_FIELDS={_nif_resume_summary_fields_raw!r}; using 6."
    )
    NIF_RESUME_SUMMARY_FIELDS = 6
NIF_RESUME_SUMMARY_FIELDS = max(0, min(NIF_RESUME_SUMMARY_FIELDS, 20))

NIF_CHAT_ENGINE = "legacy"

NIF_GUIDE_PROMPT_MODE = os.getenv("NIF_GUIDE_PROMPT_MODE", "legacy").strip().lower()
if NIF_GUIDE_PROMPT_MODE not in {"legacy", "compact"}:
    print(
        f"> WARNING: Invalid NIF_GUIDE_PROMPT_MODE={NIF_GUIDE_PROMPT_MODE!r}; using 'legacy'."
    )
    NIF_GUIDE_PROMPT_MODE = "legacy"

_nif_guide_rule_window_raw = os.getenv("NIF_GUIDE_RULE_WINDOW", "2").strip()
try:
    NIF_GUIDE_RULE_WINDOW = int(_nif_guide_rule_window_raw)
except Exception:
    print(
        f"> WARNING: Invalid NIF_GUIDE_RULE_WINDOW={_nif_guide_rule_window_raw!r}; using 2."
    )
    NIF_GUIDE_RULE_WINDOW = 2
NIF_GUIDE_RULE_WINDOW = max(0, min(NIF_GUIDE_RULE_WINDOW, 5))

_nif_guide_max_glossary_terms_raw = os.getenv("NIF_GUIDE_MAX_GLOSSARY_TERMS", "18").strip()
try:
    NIF_GUIDE_MAX_GLOSSARY_TERMS = int(_nif_guide_max_glossary_terms_raw)
except Exception:
    print(
        f"> WARNING: Invalid NIF_GUIDE_MAX_GLOSSARY_TERMS={_nif_guide_max_glossary_terms_raw!r}; using 18."
    )
    NIF_GUIDE_MAX_GLOSSARY_TERMS = 18
NIF_GUIDE_MAX_GLOSSARY_TERMS = max(0, min(NIF_GUIDE_MAX_GLOSSARY_TERMS, 80))

_nif_guide_turns_per_submit_raw = os.getenv("NIF_GUIDE_TURNS_PER_SUBMIT", "4").strip()
try:
    NIF_GUIDE_TURNS_PER_SUBMIT = int(_nif_guide_turns_per_submit_raw)
except Exception:
    print(
        f"> WARNING: Invalid NIF_GUIDE_TURNS_PER_SUBMIT={_nif_guide_turns_per_submit_raw!r}; using 4."
    )
    NIF_GUIDE_TURNS_PER_SUBMIT = 4
NIF_GUIDE_TURNS_PER_SUBMIT = max(1, min(NIF_GUIDE_TURNS_PER_SUBMIT, 10))

_nif_backend_save_every_steps_raw = os.getenv("NIF_BACKEND_SAVE_EVERY_STEPS", "5").strip()
try:
    NIF_BACKEND_SAVE_EVERY_STEPS = int(_nif_backend_save_every_steps_raw)
except Exception:
    print(
        f"> WARNING: Invalid NIF_BACKEND_SAVE_EVERY_STEPS={_nif_backend_save_every_steps_raw!r}; using 5."
    )
    NIF_BACKEND_SAVE_EVERY_STEPS = 5
NIF_BACKEND_SAVE_EVERY_STEPS = max(1, min(NIF_BACKEND_SAVE_EVERY_STEPS, 50))

NIF_GUIDE_STRICT_OUTPUT_VALIDATION = os.getenv(
    "NIF_GUIDE_STRICT_OUTPUT_VALIDATION", "true"
).strip().lower() in {
    "1", "true", "t", "yes", "y", "on"
}

# For step-by-step legacy behavior parity with QA branch.
# - qa: preserve older NIF guide loop style (single run call, no compact prompt refresh)
# - current: use current tuned legacy behavior
NIF_GUIDE_LEGACY_SOURCE = os.getenv("NIF_GUIDE_LEGACY_SOURCE", "qa").strip().lower()
if NIF_GUIDE_LEGACY_SOURCE not in {"qa", "current"}:
    print(
        f"> WARNING: Invalid NIF_GUIDE_LEGACY_SOURCE={NIF_GUIDE_LEGACY_SOURCE!r}; using 'qa'."
    )
    NIF_GUIDE_LEGACY_SOURCE = "qa"

NIF_GUIDE_TRIM_HISTORY = os.getenv("NIF_GUIDE_TRIM_HISTORY", "true").strip().lower() in {
    "1", "true", "t", "yes", "y", "on"
}

_nif_guide_history_window_raw = os.getenv("NIF_GUIDE_HISTORY_WINDOW", "14").strip()
try:
    NIF_GUIDE_HISTORY_WINDOW = int(_nif_guide_history_window_raw)
except Exception:
    print(
        f"> WARNING: Invalid NIF_GUIDE_HISTORY_WINDOW={_nif_guide_history_window_raw!r}; using 14."
    )
    NIF_GUIDE_HISTORY_WINDOW = 14
NIF_GUIDE_HISTORY_WINDOW = max(4, min(NIF_GUIDE_HISTORY_WINDOW, 80))

NIF_HISTORY_TRIM_OTHER_TASKS = os.getenv(
    "NIF_HISTORY_TRIM_OTHER_TASKS", "false"
).strip().lower() in {
    "1", "true", "t", "yes", "y", "on"
}

_nif_other_task_history_window_raw = os.getenv("NIF_OTHER_TASK_HISTORY_WINDOW", "40").strip()
try:
    NIF_OTHER_TASK_HISTORY_WINDOW = int(_nif_other_task_history_window_raw)
except Exception:
    print(
        f"> WARNING: Invalid NIF_OTHER_TASK_HISTORY_WINDOW={_nif_other_task_history_window_raw!r}; using 40."
    )
    NIF_OTHER_TASK_HISTORY_WINDOW = 40
NIF_OTHER_TASK_HISTORY_WINDOW = max(8, min(NIF_OTHER_TASK_HISTORY_WINDOW, 200))

NIF_LONGTERM_HISTORY_DEDUP = os.getenv(
    "NIF_LONGTERM_HISTORY_DEDUP", "true"
).strip().lower() in {
    "1", "true", "t", "yes", "y", "on"
}

_nif_longterm_max_entries_raw = os.getenv("NIF_LONGTERM_MAX_ENTRIES", "12000").strip()
try:
    NIF_LONGTERM_MAX_ENTRIES = int(_nif_longterm_max_entries_raw)
except Exception:
    print(
        f"> WARNING: Invalid NIF_LONGTERM_MAX_ENTRIES={_nif_longterm_max_entries_raw!r}; using 12000."
    )
    NIF_LONGTERM_MAX_ENTRIES = 12000
NIF_LONGTERM_MAX_ENTRIES = max(0, min(NIF_LONGTERM_MAX_ENTRIES, 50000))

print(
    "> NIF_DB config:"
    f" chat_engine={NIF_CHAT_ENGINE},"
    f" mode={NIF_DB_SQL_GENERATION_MODE},"
    f" first_pass_turns={NIF_DB_FIRST_PASS_TURNS},"
    f" max_rows={NIF_DB_MAX_ROWS},"
    f" show_output_records={NIF_DB_SHOW_OUTPUT_RECORDS},"
    f" show_sql_trace={NIF_DB_SHOW_SQL_TRACE},"
    f" trace_include_rows={NIF_DB_TRACE_INCLUDE_ROWS},"
    f" trace_preview_rows={NIF_DB_TRACE_PREVIEW_ROWS},"
    f" prompt_max_abbr={NIF_DB_PROMPT_MAX_ABBREVIATIONS},"
    f" resume_verbose={NIF_RESUME_VERBOSE_CONTEXT},"
    f" resume_summary_fields={NIF_RESUME_SUMMARY_FIELDS},"
    f" guide_prompt_mode={NIF_GUIDE_PROMPT_MODE},"
    f" guide_rule_window={NIF_GUIDE_RULE_WINDOW},"
    f" guide_max_glossary_terms={NIF_GUIDE_MAX_GLOSSARY_TERMS},"
    f" guide_turns_per_submit={NIF_GUIDE_TURNS_PER_SUBMIT},"
    f" guide_trim_history={NIF_GUIDE_TRIM_HISTORY},"
    f" guide_history_window={NIF_GUIDE_HISTORY_WINDOW},"
    f" strict_guide_validation={NIF_GUIDE_STRICT_OUTPUT_VALIDATION},"
    f" trim_other_tasks={NIF_HISTORY_TRIM_OTHER_TASKS},"
    f" other_task_history_window={NIF_OTHER_TASK_HISTORY_WINDOW},"
    f" longterm_dedup={NIF_LONGTERM_HISTORY_DEDUP},"
    f" longterm_max_entries={NIF_LONGTERM_MAX_ENTRIES}"
)

APP_LLM_PROVIDER = utils.get_app_llm_provider()
if APP_LLM_PROVIDER == "openai":
    APP_LLM_MODEL = utils.get_openai_chat_model(task_kind="general")
    APP_LLM_AUTH_MODE = "api_key"
else:
    APP_LLM_MODEL = utils.get_bedrock_chat_model(task_kind="general")
    APP_LLM_AUTH_MODE = utils.get_bedrock_auth_mode()

print(
    "> APP_LLM config:"
    f" provider={APP_LLM_PROVIDER},"
    f" model={APP_LLM_MODEL},"
    f" auth_mode={APP_LLM_AUTH_MODE},"
    f" bedrock_region={utils.get_bedrock_region()}"
)
try:
    utils.validate_llm_env_or_raise(provider=APP_LLM_PROVIDER)
except Exception as llm_env_err:
    print(f"> WARNING: LLM environment validation failed at startup: {llm_env_err}")

APP_LLM_HEADER_TEXT = f"LLM: {APP_LLM_PROVIDER.upper()} | {APP_LLM_MODEL}"
if APP_LLM_PROVIDER == "bedrock":
    APP_LLM_HEADER_TEXT += f" | auth={APP_LLM_AUTH_MODE}"

_docsearch_results_per_collection_raw = os.getenv(
    "DOCSEARCH_RESULTS_PER_COLLECTION", "2"
).strip()
try:
    DOCSEARCH_RESULTS_PER_COLLECTION = int(_docsearch_results_per_collection_raw)
except Exception:
    print(
        f"> WARNING: Invalid DOCSEARCH_RESULTS_PER_COLLECTION={_docsearch_results_per_collection_raw!r}; "
        "using 2."
    )
    DOCSEARCH_RESULTS_PER_COLLECTION = 2
DOCSEARCH_RESULTS_PER_COLLECTION = max(1, min(DOCSEARCH_RESULTS_PER_COLLECTION, 8))

_docsearch_max_total_pages_raw = os.getenv("DOCSEARCH_MAX_TOTAL_PAGES", "4").strip()
try:
    DOCSEARCH_MAX_TOTAL_PAGES = int(_docsearch_max_total_pages_raw)
except Exception:
    print(
        f"> WARNING: Invalid DOCSEARCH_MAX_TOTAL_PAGES={_docsearch_max_total_pages_raw!r}; "
        "using 4."
    )
    DOCSEARCH_MAX_TOTAL_PAGES = 4
DOCSEARCH_MAX_TOTAL_PAGES = max(1, min(DOCSEARCH_MAX_TOTAL_PAGES, 12))

_docsearch_min_hits_raw = os.getenv("DOCSEARCH_MIN_HITS", "1").strip()
try:
    DOCSEARCH_MIN_HITS = int(_docsearch_min_hits_raw)
except Exception:
    print(
        f"> WARNING: Invalid DOCSEARCH_MIN_HITS={_docsearch_min_hits_raw!r}; using 1."
    )
    DOCSEARCH_MIN_HITS = 1
DOCSEARCH_MIN_HITS = max(1, min(DOCSEARCH_MIN_HITS, DOCSEARCH_MAX_TOTAL_PAGES))

_docsearch_max_distance_raw = os.getenv("DOCSEARCH_MAX_DISTANCE", "").strip()
DOCSEARCH_MAX_DISTANCE = None
if _docsearch_max_distance_raw:
    try:
        DOCSEARCH_MAX_DISTANCE = float(_docsearch_max_distance_raw)
    except Exception:
        print(
            f"> WARNING: Invalid DOCSEARCH_MAX_DISTANCE={_docsearch_max_distance_raw!r}; "
            "distance filtering disabled."
        )
        DOCSEARCH_MAX_DISTANCE = None

DOCSEARCH_STRICT_GROUNDING = os.getenv(
    "DOCSEARCH_STRICT_GROUNDING", "true"
).strip().lower() in {
    "1", "true", "t", "yes", "y", "on"
}

print(
    "> DOCSEARCH config:"
    f" per_collection={DOCSEARCH_RESULTS_PER_COLLECTION},"
    f" max_total_pages={DOCSEARCH_MAX_TOTAL_PAGES},"
    f" min_hits={DOCSEARCH_MIN_HITS},"
    f" max_distance={DOCSEARCH_MAX_DISTANCE},"
    f" strict_grounding={DOCSEARCH_STRICT_GROUNDING}"
)

REACT_NIF_STEP_ENHANCED = os.getenv(
    "REACT_NIF_STEP_ENHANCED", "true"
).strip().lower() in {"1", "true", "t", "yes", "y", "on"}
print(f"> REACT_NIF_STEP_ENHANCED={REACT_NIF_STEP_ENHANCED}")

# Feature flag for staged import of QA Dash-only UI behavior.
# Keep default off so existing UX remains unchanged unless explicitly enabled.
DASH_UI_QA_MERGE = os.getenv(
    "DASH_UI_QA_MERGE", "false"
).strip().lower() in {"1", "true", "t", "yes", "y", "on"}
print(f"> DASH_UI_QA_MERGE={DASH_UI_QA_MERGE}")

app_title = "Kellanova Project NIFTY"
external_stylesheets=[dbc.themes.BOOTSTRAP,
                      "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"]
flask_server, app = instantiate_app(
    app_title,
    external_stylesheets,
    external_scripts=['https://cdnjs.cloudflare.com/ajax/libs/markdown-it/13.0.2/markdown-it.js'],
    ) # dont change name "flask_server".  Gunicorn expects to find it

# Increase the timeout
app.server.config['TIMEOUT'] = 600      # In seconds

FADashChatbot = app  # an alias for app; the app name used within this program

FADashChatbot.config.suppress_callback_exceptions = True    # Use to remove warnings when assigning callbacks to components that are generated by other callbacks (and therefore not in the initial layout)

# ## USERNAMES AND PASSWORDS
# VALID_USERNAME_PASSWORD_PAIRS = {
#     dotenv_dict['DASH_USERNAME']:dotenv_dict['DASH_PASSWORD']
#     ,dotenv_dict['USER_1']:dotenv_dict['PASSWORD_1']
#     ,dotenv_dict['USER_2']:dotenv_dict['PASSWORD_2']
#     ,dotenv_dict['USER_3']:dotenv_dict['PASSWORD_3']
# }

# # BASIC AUTHORIZATION:  USERNAME:PASSWORD
# auth = dash_auth.BasicAuth(
#     FADashChatbot,
#     VALID_USERNAME_PASSWORD_PAIRS
#     )

# =============================================================================
#### AJIT's code for getting user info
# =============================================================================
import jwt
import requests
from flask import request, g

def b64url_decode_bytes(data: str) -> bytes:
    """Decodes a base64url string, adding padding if necessary."""
    data += "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data.encode())

def decode_jwt_parts(token: str):
    """Decodes the header and payload of a JWT without verifying the signature."""
    try:
        # JWT format: header.payload.signature
        _header_b64, payload_b64, _sig_b64 = token.split(".")

        # We only need the payload for user claims
        payload = json.loads(b64url_decode_bytes(payload_b64).decode("utf-8"))
        return payload
    except Exception as e:
        # print(f"JWT Decoding Error: {e}") # Optional: for debugging
        return None

def get_user_from_alb():
    """Extract user claims directly from the ALB OIDC token payload."""

    # 1. Get the OIDC token from the request headers
    token = request.headers.get("x-amzn-oidc-data")

    if not token:
        return None

    # 2. Decode the JWT payload using the helper function
    claims = decode_jwt_parts(token)

    if not claims:
        return None

    # 3. Return the clean user data dictionary
    return {
        "sub": claims.get("sub"),
        "email": claims.get("email"),
        "name": claims.get("name"),
        "upn": claims.get("preferred_username"),
        "roles": claims.get("roles"),
    }

# Convert email address for file system naming
def get_safe_user_id(user_email: str) -> str:
    safe_id = re.sub(r'[^a-zA-Z0-9_]', '_', user_email)
    return safe_id

#%% 3. GLOBAL PROGRAM ELEMENTS
###############################################################################################
# - Global variables and functions that aren't directly involved in the UI interactivity (Callbacks)
# - Typical example would be functions that read, store, and prep data to be used in the app
###############################################################################################
# =============================================================================
#### Initialize globals
# =============================================================================
# Don't use globals! Breaks with multiple users.
# global_socket_id = None

# =============================================================================
#### Read data from disk
# =============================================================================
# Define folder location
try:
    CURRENT_FOLDER_DASH_APP = os.path.dirname(os.path.realpath(__file__))     # Doesn't rely on working directory. Will throw NameError if run as a single line. Works only when running a cell or the whole file.
    print(f"> CURRENT_FOLDER_DASH_APP set to location of this file: {CURRENT_FOLDER_DASH_APP}")
except NameError:
    CURRENT_FOLDER_DASH_APP = os.getcwd()                      # Relies on working directory being set to this program.
    print(f"> CURRENT_FOLDER_DASH_APP set to current working directory: {CURRENT_FOLDER_DASH_APP}")

SOURCE_RAW_DOCS_FOLDER = os.path.join(CURRENT_FOLDER_DASH_APP ,'raw_docs')
ASSETS_FOLDER = os.path.join(CURRENT_FOLDER_DASH_APP ,'assets')
ASSETS_RAW_DOCS_FOLDER = os.path.join(ASSETS_FOLDER, 'raw_docs')
ASSETS_PAGE_IMAGES_FOLDER = os.path.join(ASSETS_FOLDER, 'doc_images_and_summaries')

# Define base paths for links to files
base_path_docs = '/assets/raw_docs'

# Create user files directory if it doesn't exist
USER_FILES_DIR = Path('./user_files')
USER_FILES_DIR.mkdir(exist_ok=True)

# Create admin feedback directory if it doesn't exist
ADMIN_FEEDBACK_DIR = Path('./admin_feedback')
ADMIN_FEEDBACK_DIR.mkdir(exist_ok=True)

# # Create history directory if it doesn't exist
# HISTORY_DIR = Path('./history')
# HISTORY_DIR.mkdir(exist_ok=True)

# # Create in-progress NIF directory if it doesn't exist
# INPROG_NIF_DIR = Path('./user_in_progress_nifs')
# INPROG_NIF_DIR.mkdir(exist_ok=True)

# Set history and in-progress NIF directories for each user
def get_user_history_dir(user_email: str) -> Path:
    safe_id = get_safe_user_id(user_email)
    user_base_dir = USER_FILES_DIR / safe_id
    user_history_dir = user_base_dir / 'history'

    # Ensure the directory structure exists
    user_history_dir.mkdir(parents=True, exist_ok=True)

    return user_history_dir

def get_user_nif_progress_dir(user_email: str) -> Path:
    safe_id = get_safe_user_id(user_email)
    user_base_dir = USER_FILES_DIR / safe_id
    user_inprog_nif_dir = user_base_dir / 'user_in_progress_nifs'

    # Ensure the directory structure exists
    user_inprog_nif_dir.mkdir(parents=True, exist_ok=True)

    return user_inprog_nif_dir




END_MSG = 'END$$$END'

# # Check and sync raw_docs folder in assets (used for webaddress links)
# def sync_files_in_existing_dirs():
#     source_files = {f for f in os.listdir(SOURCE_RAW_DOCS_FOLDER) if os.path.isfile(os.path.join(SOURCE_RAW_DOCS_FOLDER, f))}
#     destination_files = {f for f in os.listdir(ASSETS_RAW_DOCS_FOLDER) if os.path.isfile(os.path.join(ASSETS_RAW_DOCS_FOLDER, f))}

#     # Copy missing files from source to destination
#     for filename in source_files:
#         src_path = os.path.join(SOURCE_RAW_DOCS_FOLDER, filename)
#         dst_path = os.path.join(ASSETS_RAW_DOCS_FOLDER, filename)

#         if not os.path.exists(dst_path) or os.path.getmtime(src_path) > os.path.getmtime(dst_path):
#             try:
#                 shutil.copy2(src_path, dst_path) # copy2 preserves metadata like modification times
#                 pr.logit(f"Copied/Updated: '{filename}' from '{src_path}' to '{dst_path}'.")
#             except Exception as e:
#                 pr.logit(f"Error copying file '{filename}': {e}")

#         # # Loggin for debugging
#         # else:
#         #     pr.logit(f"Skipping '{filename}': already up-to-date in destination.")

#     # Remove files from destination that are no longer in source
#     for filename in destination_files:
#         src_path = os.path.join(SOURCE_RAW_DOCS_FOLDER, filename)
#         dst_path = os.path.join(ASSETS_RAW_DOCS_FOLDER, filename)
#         if not os.path.exists(src_path):
#             try:
#                 os.remove(dst_path)
#                 pr.logit(f"Removed extraneous file: '{filename}' from '{dst_path}'.")
#             except Exception as e:
#                 pr.logit(f"Error removing file '{filename}': {e}")

#     pr.logit("Document folder synchronization complete.")

# # Create the raw_docs in the assets folder if it doesn't exist. Make it match source folder
# if not os.path.exists(ASSETS_RAW_DOCS_FOLDER):
#     pr.logit(f"'{ASSETS_RAW_DOCS_FOLDER}' not found. Copying entire folder from '{SOURCE_RAW_DOCS_FOLDER}'.")
#     try:
#         shutil.copytree(SOURCE_RAW_DOCS_FOLDER, ASSETS_RAW_DOCS_FOLDER)
#         pr.logit(f"Successfully copied '{SOURCE_RAW_DOCS_FOLDER}' to '{ASSETS_RAW_DOCS_FOLDER}'.")
#     except shutil.Error as e:
#         pr.logit(f"Error copying directory: {e}")
#         pr.logit(f"It's possible '{ASSETS_RAW_DOCS_FOLDER}' already partially exists. Attempting file-by-file sync.")
#         # Fallback to file-by-file if copytree fails (e.g., due to partial existence)
#         sync_files_in_existing_dirs()
# else:
#     pr.logit(f"'{ASSETS_RAW_DOCS_FOLDER}' already exists. Syncing individual files.")
#     sync_files_in_existing_dirs()

# =============================================================================
#### POC elements to be updated
# =============================================================================
# NIF database
nif_database = os.path.join(utils.DATABASE_FOLDER, 'NIFS.db')
# Using the one with added columns for rejection reason and link to PDF.
# NOTE these are only populated for a few example NIFs.
# nif_database = os.path.join(utils.DATABASE_FOLDER, 'NIFS_with_reject_and_pdf.db')

# Brands database
brands_database = os.path.join(utils.DATABASE_FOLDER, 'KNV_Active_Brands.db')

# Trace holder for latest SQL submitted to NIF database tool.
last_nif_sql_query = None
last_nif_query_result = None

# Database abbreviations
db_abbreviations = pd.read_excel(
    os.path.join(utils.DOCUMENT_FOLDER, 'Glossary of Terms for NIFs.xlsx')
    ,sheet_name='db terms'
)
db_abbreviations = db_abbreviations.set_index(keys='description')      # Column to become dictionary keys
db_abbreviations_dict = dict(db_abbreviations['abbreviation'])

# Creating a smaller version of the abbreviations dictionary
# This is just for the demo
db_abbreviations_dict_small = {
    "poptart":"pop-tart"
    ,"rice krispie":"RKT"
    ,"cheezit":"cheez-it"
}

# Product Type: map abbreviations from online form to full names in NIF database
# Note product type in database is actually a combination of country, type, and subtype!
product_type_abbreviations = {
    "CS":"Straight Case"
    ,"BULK CS":"Bulk Case"
}

# Fields in NIF
nif_fields = pd.read_excel(os.path.join(utils.DOCUMENT_FOLDER, 'NIF Fields and Descriptions.xlsx'))
nif_fields = nif_fields.dropna(axis=0, subset='Field')  # Drop empty rows
nif_fields = nif_fields.set_index(keys='Field')      # Column to become dictionary keys
nif_fields_dict = dict(nif_fields['Description'])

# Trimmed NIF fields with ONLY those in the POC
nif_fields_small = pd.read_excel(os.path.join(utils.DOCUMENT_FOLDER, 'NIF Fields and Descriptions POC FIELDS ONLY.xlsx'))
nif_fields_small = nif_fields_small.set_index(keys='Field')      # Column to become dictionary keys
nif_fields_poc_dict = dict(nif_fields_small['Description'])

# Collected documentation and reference links
help_links = pd.read_excel(os.path.join(utils.DOCUMENT_FOLDER, 'Kellanova Help URLs.xlsx'))
help_links = help_links.set_index(keys='Name')      # Column to become dictionary keys
help_links_dict = dict(help_links['URL'])

# =============================================================================
#### Implementation Expert rules
# =============================================================================
# The file now contains rule logic for every field, not just product type.
# We are limiting the step by step guide to the Requestor Initiate section.
expert_system_rules = pd.read_excel(
    os.path.join(utils.CONTROL_FOLDER, 'Expert_System_Rules.xlsx')
    ,sheet_name='Implementation v1'
    ,header=1
)

# Drop rows where Question ID is missing (these are comments)
expert_system_rules = expert_system_rules.dropna(subset='Question ID')

# Drop Length column when present (some rule exports do not include it).
if 'Length' in list(expert_system_rules.columns):
    del expert_system_rules['Length']

# Drop START_REQ_INITIATE_Q as this will be auto-filled and it is confusing the bot
_autopop_question = (expert_system_rules['Question ID'] == 'START_REQ_INITIATE_Q')
expert_system_rules = expert_system_rules.loc[~ _autopop_question]

# Write to markdown for reading into LLM system message
expert_system_rules_md = expert_system_rules.to_markdown(index=False)
expert_system_rules = expert_system_rules.reset_index(drop=True)
expert_rule_question_ids = [
    str(qid).strip()
    for qid in expert_system_rules["Question ID"].tolist()
    if isinstance(qid, str) and qid.strip()
]
expert_rule_index_by_question_id = {
    qid: idx for idx, qid in enumerate(expert_rule_question_ids)
}

# =============================================================================
#### Implementation Dropdown Reference Lists
# =============================================================================
# LIM users
ddref_lim_users = pd.read_csv(
    os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'LIM_USERS.csv')
)
ddref_lim_users_md = ddref_lim_users.to_markdown(index=False)

# RDL Categories
ddref_rdl_categories = pd.read_excel(
    os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'RDL_Categories.xlsx')
)
ddref_rdl_categories_md = ddref_rdl_categories['Category'].to_markdown(index=False)

# Material Prefix
ddref_material_prefix = pd.read_excel(
    os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'MATERIAL_PREFIX.xlsx')
)
ddref_material_prefix_md = ddref_material_prefix[['COUNTRY', 'MATERIAL_PREFIX']].sort_values(by='COUNTRY').to_markdown(index=False)

# Additional Packaging Launch
ddref_addnl_packaging = pd.read_excel(
    os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'ADDITIONAL_PACKAGING_LAUNCH.xlsx')
)
ddref_addnl_packaging_md = ddref_addnl_packaging['Value'].to_markdown(index=False)

# Private Label Customers
ddref_private_label = pd.read_csv(
    os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'PRIVATE_LABEL.csv')
)
ddref_private_label_md = ddref_private_label.to_markdown(index=False)

# Designated Customer Name
ddref_desig_cust = pd.read_csv(
    os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'Designate Customer Name.csv')
)
ddref_desig_cust_md = ddref_desig_cust['DESIGNATED_CUST_NAME'].to_markdown(index=False)

nif_dropdown_reference_markdown = {
    "LIM_USERS": ddref_lim_users_md,
    "RDL_CATEGORIES": ddref_rdl_categories_md,
    "MATERIAL_PREFIX": ddref_material_prefix_md,
    "ADDITIONAL_PACKAGING_LAUNCH": ddref_addnl_packaging_md,
    "PRIVATE_LABEL": ddref_private_label_md,
    "DESIGNATED_CUSTOMER_NAME": ddref_desig_cust_md,
}

# =============================================================================
#### Implementation Field lookup and Glossary
# =============================================================================
nifty_definitions_excel = os.path.join(utils.CONTROL_FOLDER, 'NIFTY Definitions v1.xlsx')

# The Module 2 tab contains all field definitions
all_nif_fields = pd.read_excel(
    nifty_definitions_excel
    ,sheet_name='Module2-AI'
    ,header=2
)
all_nif_fields = dpu.cleancolnames(all_nif_fields)

# Create template for step by step table
# Subset to Requestor - Project Initiation
_req_proj_init = (all_nif_fields['field_section'].str.upper() == 'REQUESTOR - PROJECT INITIATION')

field_name_array = all_nif_fields.loc[_req_proj_init, 'field_name']
field_nbr_array = all_nif_fields.loc[_req_proj_init, 'field_number']
nif_fields_req_init_template = pd.DataFrame([field_name_array, field_nbr_array]).transpose()
nif_fields_req_init_template['field_name_and_number'] = \
    nif_fields_req_init_template['field_name'] + " (" + nif_fields_req_init_template['field_number'].astype(int).astype(str) + ")"

# The Glossary tab contains business terms AND database abbreviations
glossary_and_db_terms = pd.read_excel(
    nifty_definitions_excel
    ,sheet_name='glossary'
    ,header=0
)
glossary_and_db_terms = dpu.cleancolnames(glossary_and_db_terms)

# Create a dictionary
glossary_and_db_terms = glossary_and_db_terms.set_index(keys='term')      # Column to become dictionary keys
glossary_and_db_terms_dict = dict(glossary_and_db_terms['definition'])

nif_field_number_to_column = {
    int(row["field_number"]): row["field_name_and_number"]
    for _, row in nif_fields_req_init_template.iterrows()
}


def _build_dropdown_values_catalog_from_frames(dropdown_frames: dict) -> dict:
    """
    Normalize dropdown reference dataframes into list-of-string value catalogs.
    """

    def _series_values(series_obj):
        values = []
        seen = set()
        for value in list(series_obj):
            value_text = str(value).strip() if value is not None else ""
            if not value_text or value_text.lower() in {"nan", "none", "null"}:
                continue
            key = value_text.lower()
            if key in seen:
                continue
            seen.add(key)
            values.append(value_text)
        return values

    def _pick_value_column(df_obj):
        if df_obj is None or df_obj.empty:
            return None
        preferred_names = [
            "Value",
            "Category",
            "DESIGNATED_CUST_NAME",
            "MATERIAL_PREFIX",
            "LIM",
            "Name",
        ]
        for col in preferred_names:
            if col in list(df_obj.columns):
                return col
        # Otherwise use first non-empty column.
        for col in list(df_obj.columns):
            if df_obj[col].notna().any():
                return col
        return None

    dropdown_values = {}
    for ref_name, df_obj in dropdown_frames.items():
        col = _pick_value_column(df_obj)
        if col is None:
            dropdown_values[ref_name] = []
            continue
        dropdown_values[ref_name] = _series_values(df_obj[col])
    return dropdown_values


def _build_dropdown_values_catalog() -> dict:
    dropdown_frames = {
        "LIM_USERS": ddref_lim_users,
        "RDL_CATEGORIES": ddref_rdl_categories,
        "MATERIAL_PREFIX": ddref_material_prefix,
        "ADDITIONAL_PACKAGING_LAUNCH": ddref_addnl_packaging,
        "PRIVATE_LABEL": ddref_private_label,
        "DESIGNATED_CUSTOMER_NAME": ddref_desig_cust,
    }
    return _build_dropdown_values_catalog_from_frames(dropdown_frames)

# Legacy step-by-step flow source of truth:
# Expert_System_Rules.xlsx injected into <STEP_BY_STEP_RULES> prompt.
nif_backend_save_state = {}
nif_config_reload_lock = threading.Lock()


def reload_nif_runtime_configuration() -> dict:
    """
    Reload NIF rules/glossary/dropdown references from control_docs without restart.
    Rebuilds markdown caches for legacy step-by-step flow.
    """
    global expert_system_rules
    global expert_system_rules_md
    global expert_rule_question_ids
    global expert_rule_index_by_question_id
    global ddref_lim_users, ddref_lim_users_md
    global ddref_rdl_categories, ddref_rdl_categories_md
    global ddref_material_prefix, ddref_material_prefix_md
    global ddref_addnl_packaging, ddref_addnl_packaging_md
    global ddref_private_label, ddref_private_label_md
    global ddref_desig_cust, ddref_desig_cust_md
    global nif_dropdown_reference_markdown
    global all_nif_fields
    global nif_fields_req_init_template
    global glossary_and_db_terms
    global glossary_and_db_terms_dict
    global nif_field_number_to_column

    with nif_config_reload_lock:
        # 1) Reload rule source
        rules_local = pd.read_excel(
            os.path.join(utils.CONTROL_FOLDER, 'Expert_System_Rules.xlsx'),
            sheet_name='Implementation v1',
            header=1,
        )
        rules_local = rules_local.dropna(subset='Question ID')
        if 'Length' in list(rules_local.columns):
            del rules_local['Length']
        _autopop_question = (rules_local['Question ID'] == 'START_REQ_INITIATE_Q')
        rules_local = rules_local.loc[~ _autopop_question]
        rules_local = rules_local.reset_index(drop=True)
        rules_md_local = rules_local.to_markdown(index=False)
        rule_ids_local = [
            str(qid).strip()
            for qid in rules_local["Question ID"].tolist()
            if isinstance(qid, str) and qid.strip()
        ]
        rule_index_local = {qid: idx for idx, qid in enumerate(rule_ids_local)}

        # 2) Reload dropdown references
        dd_lim_local = pd.read_csv(
            os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'LIM_USERS.csv')
        )
        dd_rdl_local = pd.read_excel(
            os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'RDL_Categories.xlsx')
        )
        dd_pref_local = pd.read_excel(
            os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'MATERIAL_PREFIX.xlsx')
        )
        dd_add_local = pd.read_excel(
            os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'ADDITIONAL_PACKAGING_LAUNCH.xlsx')
        )
        dd_priv_local = pd.read_csv(
            os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'PRIVATE_LABEL.csv')
        )
        dd_cust_local = pd.read_csv(
            os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'Designate Customer Name.csv')
        )

        dd_lim_md_local = dd_lim_local.to_markdown(index=False)
        dd_rdl_md_local = dd_rdl_local['Category'].to_markdown(index=False)
        dd_pref_md_local = dd_pref_local[['COUNTRY', 'MATERIAL_PREFIX']].sort_values(
            by='COUNTRY'
        ).to_markdown(index=False)
        dd_add_md_local = dd_add_local['Value'].to_markdown(index=False)
        dd_priv_md_local = dd_priv_local.to_markdown(index=False)
        dd_cust_md_local = dd_cust_local['DESIGNATED_CUST_NAME'].to_markdown(index=False)

        dropdown_md_local = {
            "LIM_USERS": dd_lim_md_local,
            "RDL_CATEGORIES": dd_rdl_md_local,
            "MATERIAL_PREFIX": dd_pref_md_local,
            "ADDITIONAL_PACKAGING_LAUNCH": dd_add_md_local,
            "PRIVATE_LABEL": dd_priv_md_local,
            "DESIGNATED_CUSTOMER_NAME": dd_cust_md_local,
        }
        dropdown_values_local = _build_dropdown_values_catalog_from_frames(
            {
                "LIM_USERS": dd_lim_local,
                "RDL_CATEGORIES": dd_rdl_local,
                "MATERIAL_PREFIX": dd_pref_local,
                "ADDITIONAL_PACKAGING_LAUNCH": dd_add_local,
                "PRIVATE_LABEL": dd_priv_local,
                "DESIGNATED_CUSTOMER_NAME": dd_cust_local,
            }
        )

        # 3) Reload NIFTY definitions (template + glossary)
        defs_file = os.path.join(utils.CONTROL_FOLDER, 'NIFTY Definitions v1.xlsx')
        all_fields_local = pd.read_excel(defs_file, sheet_name='Module2-AI', header=2)
        all_fields_local = dpu.cleancolnames(all_fields_local)
        _req_proj_init = (all_fields_local['field_section'].str.upper() == 'REQUESTOR - PROJECT INITIATION')
        field_name_array = all_fields_local.loc[_req_proj_init, 'field_name']
        field_nbr_array = all_fields_local.loc[_req_proj_init, 'field_number']
        template_local = pd.DataFrame([field_name_array, field_nbr_array]).transpose()
        template_local['field_name_and_number'] = (
            template_local['field_name']
            + " ("
            + template_local['field_number'].astype(int).astype(str)
            + ")"
        )
        field_map_local = {
            int(row["field_number"]): row["field_name_and_number"]
            for _, row in template_local.iterrows()
        }

        glossary_local = pd.read_excel(defs_file, sheet_name='glossary', header=0)
        glossary_local = dpu.cleancolnames(glossary_local)
        glossary_local = glossary_local.set_index(keys='term')
        glossary_dict_local = dict(glossary_local['definition'])

        # 4) Commit to globals
        expert_system_rules = rules_local
        expert_system_rules_md = rules_md_local
        expert_rule_question_ids = rule_ids_local
        expert_rule_index_by_question_id = rule_index_local

        ddref_lim_users, ddref_lim_users_md = dd_lim_local, dd_lim_md_local
        ddref_rdl_categories, ddref_rdl_categories_md = dd_rdl_local, dd_rdl_md_local
        ddref_material_prefix, ddref_material_prefix_md = dd_pref_local, dd_pref_md_local
        ddref_addnl_packaging, ddref_addnl_packaging_md = dd_add_local, dd_add_md_local
        ddref_private_label, ddref_private_label_md = dd_priv_local, dd_priv_md_local
        ddref_desig_cust, ddref_desig_cust_md = dd_cust_local, dd_cust_md_local
        nif_dropdown_reference_markdown = dropdown_md_local

        all_nif_fields = all_fields_local
        nif_fields_req_init_template = template_local
        glossary_and_db_terms = glossary_local
        glossary_and_db_terms_dict = glossary_dict_local
        nif_field_number_to_column = field_map_local

        # 5) Refresh legacy task prompts

        refreshed_legacy_tasks = 0
        for (task_name, _sid), task_obj in list(session_tasks.items()):
            if task_name != "nifguide_task":
                continue
            try:
                task_df = task_obj.agent.get_dataframe() if hasattr(task_obj.agent, "get_dataframe") else None
                refresh_nifguide_task_prompt(
                    session_task=task_obj,
                    current_username="Unknown",
                    user_query="",
                    nif_progress_df=task_df,
                )
                refreshed_legacy_tasks += 1
            except Exception as task_err:
                print(f"> WARNING: Failed to refresh session nifguide task prompt: {task_err}")

        summary = {
            "rules_count": len(rule_ids_local),
            "glossary_count": len(glossary_dict_local),
            "dropdown_lists": len(dropdown_values_local),
            "legacy_tasks_refreshed": refreshed_legacy_tasks,
        }
        return summary

# =============================================================================
#### Define Styles
# =============================================================================
# Purple styling
HEADING_STYLE = {
    "color":"#8401FF",
    "font-weight": "bold",
    }
BUTTON_STYLE = {
    "background-color": "#8401FF",
    "border-color": "#8401FF",
    "font-weight": "bold",
}

# Image shadow
nifty_img_style = {'height': "70px",
                   'filter': 'drop-shadow(0 6px 12px rgba(132, 1, 255, 0.4))'
                   }

# Container headings
sample_questions_heading_style = HEADING_STYLE
ai_reponse_heading_style = HEADING_STYLE
human_text_heading_style = HEADING_STYLE

# Button style
submit_button_style = BUTTON_STYLE
hist_collapse_button_style = BUTTON_STYLE
hist_clear_button_style = BUTTON_STYLE

# Branding heading
kellanova_branding_heading_style = {'background-color': '#8401FF'}
kellanova_img = '/assets/Kellanova_logo_white.png'
nifty_heading_text_style = {"padding": "0",
                            "margin-bottom":"0rem !important",
                            "color":"#FFFFFF",
                            "font-weight":"bold"
                            }
select_demo_questions_style_div_style = 'purple-radio-scheme'
color_scheme_toggle_style = {'color':'white'}

# =============================================================================
#### Text and constants
# =============================================================================

# Demo question options
demo_questions = [{'label': i, 'value': i, 'disabled': False} for i in ["Get started on training resources",
                                                                        "NIF step by step",
                                                                        "NIF field question",
                                                                        "Search NIF",
                                                                        ]]

GUIDANCE_QUESTION = 'NIF step by step'

# Define the new options for the Guidance NIF Menu
NIF_MENU_OPTIONS = [
    {'label': 'New NIF chat session', 'value': 'NEW_NIF_CHAT'},
    {'label': 'Home', 'value': 'BACK_TO_LANDING'},
    {'label': 'Load NIF from prior chat', 'value': 'LOAD_NIF'},
]

NO_USER_NIFS_MESSAGE = '<User has no saved NIFs>'
RESET_NIF_SELECTION = 'RESET_NIF_SELECTION'

# Legal Language
legal_language = "This Chatbot can be used to query data from the Kellanova Nifty database. \
    Always review the accuracy of the Chatbot responses as they may be incorrect. \
    All content copyright ©2025 Demand Chain AI Inc. \
    All rights reserved. \
    No reproduction, transmission or display is permitted without the written permission of Demand Chain AI Inc.\
    "

# =============================================================================
#### Functions and Definitions
# =============================================================================
# Get username of user logged in
# https://community.plotly.com/t/dah-auth-user-name-extraction/76025/2
# UPDATE: no longer using this function. Using get_user_from_alb() instead.
def get_username():
    header = flask.request.headers.get('Authorization', None)
    if not header:
        return None
    username_password = base64.b64decode(header.split('Basic ')[1])
    username_password_utf8 = username_password.decode('utf-8')
    username, password = username_password_utf8.split(':', 1)
    return username

# Define session ID
def generate_session_id():
    # Create random UUID
    SID = str(uuid.uuid4())[:8]
    return SID

# Store session-specific task instances
# Task cloning breaks the functionality of Langroid subtasks. Refactoring this to use task-generating functions.
#!!! Read long-term chat history and add to agent
session_tasks = {}     # Initialize
def get_session_task(
        TASK_NAME:str       # The name of a Langroid task() that has a create() function
        ,SESSION_ID:str     # Unique session ID
        ,CURRENT_USERNAME:str   # Name of the current user
    ):
    """
    Get or create a task for a user session.
    """
    key = (TASK_NAME, SESSION_ID)    # Key is a tuple

    # If this session does not have that task, create it
    if key not in session_tasks:
        try:
            # Create a task for this session using the creation function
            exec(f"{TASK_NAME}_{SESSION_ID} = create_{TASK_NAME}('{CURRENT_USERNAME}')")
            
            # Save the created task to session_tasks
            exec(f"session_tasks[{key}] = {TASK_NAME}_{SESSION_ID}")
            
        except Exception as e:
            print(f"get_session_task error: {e}")
        
    # Return the session task
    return session_tasks[key]

# Define LLM Message for chat history reference
class LLMMessage:
    def __init__(self, role, content, timestamp=None):
        self.role = role
        self.content = content
        self.timestamp = timestamp if timestamp is not None else datetime.now()

    def to_dict(self):
        """Converts the LLMMessage object to a dictionary for JSON serialization."""
        return {
            "role": self.role.value if isinstance(self.role, Role) else self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data):
        """Creates an LLMMessage object from a dictionary (e.g., loaded from JSON)."""
        role_value = data["role"]
        # Convert role string back to Role enum if necessary
        role = Role[role_value.upper()] if hasattr(Role, role_value.upper()) else role_value

        timestamp = datetime.now() # Default if not found or parse fails
        if "timestamp" in data:
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
            except ValueError:
                print(f"Warning: Could not parse timestamp '{data['timestamp']}'. Using current time.")
        return cls(role=role, content=data["content"], timestamp=timestamp)

# This function will generate the correct web path for documents inside assets/raw_docs/
def get_web_url(filename):
    encoded_filename = urllib.parse.quote(filename)
    return f"/assets/raw_docs/{encoded_filename}"

# This function creates the html link to open in a new tab
def get_html_link_new_tab(filename, display_name):
    # Ensure filename is URL-encoded for spaces and special characters
    # Extract just the filename from the path if filename includes path (e.g., from vectorstore)
    clean_filename = os.path.basename(filename)
    encoded_filename = urllib.parse.quote(clean_filename)

    # The web URL should include the subfolder 'raw_docs' inside 'assets'
    web_url = f"/assets/raw_docs/{encoded_filename}"

    # Return a complete HTML anchor tag string with target="_blank"
    return f'<a href="{web_url}" target="_blank">{display_name}</a>'

# Function to get available files
def get_available_files(DIR):
    if not os.path.exists(DIR):
        return []
    files = [f for f in os.listdir(DIR) if os.path.isfile(os.path.join(DIR, f))]
    # Filter for supported formats
    # supported_extensions = ['.csv', '.xlsx', '.json', '.parquet']
    # files = [f for f in files if any(f.endswith(ext) for ext in supported_extensions)]
    return sorted(files, reverse=True)  # Most recent first

def remove_tool_calls(text):
    """
    Remove TOOL calls in either format:
    - 'TOOL: function_name { ... }'
    - 'TOOL: { ... }'
    Handles multi-line JSON objects within tool calls.
    """
    raw_text = str(text or "")

    # Remove balanced JSON payload forms after TOOL: with or without function name.
    pattern = r'TOOL:\s*(?:\w+\s*)?\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    cleaned_text = re.sub(pattern, '', raw_text)

    # Remove any remaining TOOL lines defensively.
    cleaned_text = re.sub(r'(?im)^\s*TOOL:\s*.*$', '', cleaned_text)

    # Clean up extra whitespace/newlines that may result
    cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text)

    return cleaned_text.strip()


def parse_function_arguments(function_arguments):
    """
    Normalize tool/function-call arguments into a dictionary when possible.
    """
    if isinstance(function_arguments, dict):
        return function_arguments
    if isinstance(function_arguments, str):
        function_arguments = function_arguments.strip()
        if not function_arguments:
            return None
        try:
            parsed = json.loads(function_arguments)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
    return None


def get_latest_sql_trace(agent):
    """
    Return the latest SQL query and latest SQL tool output from message history.
    """
    latest_sql = None
    latest_tool_output = None
    history = getattr(agent, "message_history", []) or []

    for msg in reversed(history):
        # Capture latest tool output text.
        if latest_tool_output is None:
            msg_content = getattr(msg, "content", None)
            msg_role = getattr(msg, "role", None)
            msg_role_value = msg_role.value if hasattr(msg_role, "value") else str(msg_role)
            if isinstance(msg_content, str) and msg_content.strip():
                msg_content_clean = msg_content.strip()
                if (
                    str(msg_role_value).lower() == "tool"
                    or msg_content_clean.startswith("Query returned ")
                    or msg_content_clean.startswith("Query executed successfully")
                    or msg_content_clean.startswith("SQL Operational Error:")
                    or msg_content_clean.startswith("Database Error:")
                    or msg_content_clean.startswith("Unexpected Error:")
                ):
                    latest_tool_output = msg_content_clean

        # Capture latest SQL from function_call.
        if latest_sql is None:
            function_call = getattr(msg, "function_call", None)
            function_args = parse_function_arguments(getattr(function_call, "arguments", None))
            if isinstance(function_args, dict):
                sql_query = function_args.get("SQL_QUERY")
                if isinstance(sql_query, str) and sql_query.strip():
                    latest_sql = sql_query.strip()

        # Some providers use tool_calls list rather than function_call.
        if latest_sql is None:
            tool_calls = getattr(msg, "tool_calls", None)
            if isinstance(tool_calls, list):
                for tool_call in tool_calls:
                    function_obj = getattr(tool_call, "function", None)
                    function_args = parse_function_arguments(getattr(function_obj, "arguments", None))
                    if isinstance(function_args, dict):
                        sql_query = function_args.get("SQL_QUERY")
                        if isinstance(sql_query, str) and sql_query.strip():
                            latest_sql = sql_query.strip()
                            break

        if latest_sql is not None and latest_tool_output is not None:
            break

    return latest_sql, latest_tool_output


def build_nif_llm_prompt_payload(session_task, user_prompt, session_id):
    """
    Capture the system+user prompt payload sent to NIFDatabaseAgent.
    """
    system_prompt = ""
    task_system_prompt = getattr(session_task, "system_message", None)
    agent_system_prompt = getattr(getattr(session_task, "agent", None), "system_message", None)
    for candidate in [task_system_prompt, agent_system_prompt]:
        if isinstance(candidate, str) and candidate.strip():
            system_prompt = candidate
            break

    return {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "session_id": str(session_id or ""),
        "system_prompt": system_prompt,
        "user_prompt": str(user_prompt or ""),
    }


def format_nif_llm_prompt_for_modal(prompt_payload):
    """
    Convert stored prompt payload into readable modal text.
    """
    if not isinstance(prompt_payload, dict):
        return "No NIFDatabaseAgent prompt has been captured yet."

    captured_at = str(prompt_payload.get("captured_at", "") or "")
    session_id = str(prompt_payload.get("session_id", "") or "")
    system_prompt = str(prompt_payload.get("system_prompt", "") or "")
    user_prompt = str(prompt_payload.get("user_prompt", "") or "")

    if not system_prompt.strip():
        system_prompt = "(System prompt not available for this run.)"
    if not user_prompt.strip():
        user_prompt = "(User prompt was empty.)"

    return (
        f"Captured At: {captured_at}\n"
        f"Session ID: {session_id}\n\n"
        "=== SYSTEM PROMPT ===\n"
        f"{system_prompt}\n\n"
        "=== USER MESSAGE ===\n"
        f"{user_prompt}\n"
    )


def _safe_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _extract_embedded_question_ids(text: str) -> List[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    ids = []
    for match in re.finditer(r"\b([A-Z][A-Z0-9_]*_Q)\b", text.upper()):
        qid = match.group(1).strip()
        if qid and qid in expert_rule_index_by_question_id and qid not in ids:
            ids.append(qid)
    return ids


def _extract_goto_question_ids(instruction_text: str) -> List[str]:
    if not isinstance(instruction_text, str) or not instruction_text.strip():
        return []
    targets = []
    for match in re.finditer(r"go to\s+([A-Z][A-Z0-9_]*_Q)\b", instruction_text, flags=re.IGNORECASE):
        qid = _safe_text(match.group(1)).upper()
        if qid and qid in expert_rule_index_by_question_id and qid not in targets:
            targets.append(qid)
    return targets


def _extract_reference_list_names(instruction_text: str) -> List[str]:
    if not isinstance(instruction_text, str) or not instruction_text.strip():
        return []
    names = []
    for match in re.finditer(
        r"reference list:\s*(?:PRL:\s*)?([A-Z_]+)",
        instruction_text,
        flags=re.IGNORECASE,
    ):
        ref_name = _safe_text(match.group(1)).upper()
        if ref_name in nif_dropdown_reference_markdown and ref_name not in names:
            names.append(ref_name)
    return names


def _get_last_nif_answer_state(nif_progress_df: Optional[pd.DataFrame]) -> Tuple[str, str]:
    if nif_progress_df is None or not isinstance(nif_progress_df, pd.DataFrame) or nif_progress_df.empty:
        return "", ""

    try:
        last_qid = _safe_text(nif_progress_df.get("_agentref_last_question_answered", pd.Series([""])).iloc[0]).upper()
    except Exception:
        last_qid = ""
    try:
        last_answer = _safe_text(nif_progress_df.get("_agentref_last_answer_given", pd.Series([""])).iloc[0])
    except Exception:
        last_answer = ""
    return last_qid, last_answer


def infer_expected_nif_question_id(
    nif_progress_df: Optional[pd.DataFrame],
    user_query: str = "",
) -> str:
    if not expert_rule_question_ids:
        return ""

    first_qid = expert_rule_question_ids[0]
    query_qids = _extract_embedded_question_ids(user_query)
    if query_qids:
        return query_qids[0]

    last_qid, last_answer = _get_last_nif_answer_state(nif_progress_df)
    if not last_qid or last_qid not in expert_rule_index_by_question_id:
        return first_qid

    idx = expert_rule_index_by_question_id[last_qid]
    row = expert_system_rules.iloc[idx]
    instructions = _safe_text(row.get("Instructions", ""))
    answer_lc = _safe_text(last_answer).lower()

    for line in instructions.splitlines():
        line_text = _safe_text(line)
        if not line_text:
            continue
        goto_ids = _extract_goto_question_ids(line_text)
        if not goto_ids:
            continue
        quoted_values = re.findall(r"'([^']+)'", line_text)
        if quoted_values and answer_lc:
            for token in quoted_values:
                token_lc = _safe_text(token).lower()
                if token_lc and (token_lc in answer_lc or answer_lc in token_lc):
                    return goto_ids[0]
        if not quoted_values:
            return goto_ids[0]

    goto_ids = _extract_goto_question_ids(instructions)
    if goto_ids:
        return goto_ids[0]

    next_idx = idx + 1
    if next_idx < len(expert_rule_question_ids):
        return expert_rule_question_ids[next_idx]
    return expert_rule_question_ids[-1]


def _build_nif_progress_snapshot(nif_progress_df: Optional[pd.DataFrame]) -> str:
    if nif_progress_df is None or not isinstance(nif_progress_df, pd.DataFrame) or nif_progress_df.empty:
        return "- (No active NIF progress dataframe found.)"

    placeholder_values = {"", "<NOT YET DETERMINED>", "<N/A>", "nan", "none"}
    last_qid, last_answer = _get_last_nif_answer_state(nif_progress_df)
    lines = []
    if last_qid:
        lines.append(f"- Last question answered: {last_qid}")
    if last_answer and last_answer.strip().lower() not in placeholder_values:
        lines.append(f"- Last answer given: {last_answer}")

    filled_fields = []
    for col_name in nif_progress_df.columns:
        if col_name.startswith("_agentref_"):
            continue
        try:
            value = _safe_text(nif_progress_df.iloc[0][col_name])
        except Exception:
            continue
        if not value:
            continue
        if value.strip().lower() in placeholder_values:
            continue
        filled_fields.append((col_name, value))
        if len(filled_fields) >= 8:
            break

    if filled_fields:
        lines.append("- Known field values:")
        for field_name, field_value in filled_fields:
            lines.append(f"  - {field_name}: {field_value}")
    else:
        lines.append("- Known field values: (none yet)")

    return "\n".join(lines)


def _select_nif_focus_rule_indices(expected_question_id: str, user_query: str) -> List[int]:
    if not expert_rule_question_ids:
        return []

    idxs = set()
    if expected_question_id in expert_rule_index_by_question_id:
        expected_idx = expert_rule_index_by_question_id[expected_question_id]
    else:
        expected_idx = 0

    for idx in range(
        max(0, expected_idx - NIF_GUIDE_RULE_WINDOW),
        min(len(expert_rule_question_ids), expected_idx + NIF_GUIDE_RULE_WINDOW + 1),
    ):
        idxs.add(idx)

    for query_qid in _extract_embedded_question_ids(user_query):
        qidx = expert_rule_index_by_question_id.get(query_qid)
        if qidx is not None:
            idxs.add(qidx)

    for idx in list(idxs):
        try:
            instructions = _safe_text(expert_system_rules.iloc[idx].get("Instructions", ""))
        except Exception:
            instructions = ""
        for goto_qid in _extract_goto_question_ids(instructions):
            goto_idx = expert_rule_index_by_question_id.get(goto_qid)
            if goto_idx is not None:
                idxs.add(goto_idx)

    return sorted(idxs)


def _build_nif_dropdown_reference_block(focus_rules_df: Optional[pd.DataFrame], include_all: bool) -> str:
    if include_all or focus_rules_df is None or focus_rules_df.empty:
        selected_refs = list(nif_dropdown_reference_markdown.keys())
    else:
        selected_refs = []
        for instr in focus_rules_df.get("Instructions", pd.Series(dtype=str)).tolist():
            for ref_name in _extract_reference_list_names(_safe_text(instr)):
                if ref_name not in selected_refs:
                    selected_refs.append(ref_name)

    if not selected_refs:
        return "(No dropdown reference list required for the current focused rules.)"

    blocks = []
    for ref_name in selected_refs:
        md_value = _safe_text(nif_dropdown_reference_markdown.get(ref_name, ""))
        if not md_value:
            continue
        blocks.append(f"<{ref_name}>\n{md_value}\n</{ref_name}>")

    return "\n\n".join(blocks) if blocks else "(No dropdown reference list content available.)"


def _build_nif_glossary_subset(user_query: str, max_items: int) -> dict:
    if max_items <= 0:
        return {}
    query_tokens = set(re.findall(r"[a-z0-9]+", _safe_text(user_query).lower()))
    if not query_tokens:
        return {}

    scored = []
    for term, definition in glossary_and_db_terms_dict.items():
        term_text = _safe_text(term)
        def_text = _safe_text(definition)
        if not term_text and not def_text:
            continue
        term_tokens = set(re.findall(r"[a-z0-9]+", term_text.lower()))
        def_tokens = set(re.findall(r"[a-z0-9]+", def_text.lower()))
        score = len(query_tokens.intersection(term_tokens)) * 3 + len(
            query_tokens.intersection(def_tokens)
        )
        if score > 0:
            scored.append((score, term_text.lower(), term_text, def_text))

    if not scored:
        return {}

    scored.sort(key=lambda item: (-item[0], item[1]))
    subset = {}
    for _, _, term_text, def_text in scored:
        subset[term_text] = def_text
        if len(subset) >= max_items:
            break
    return subset


def build_nifguide_fallback_message(expected_question_id: str) -> str:
    if expected_question_id in expert_rule_index_by_question_id:
        row = expert_system_rules.iloc[expert_rule_index_by_question_id[expected_question_id]]
        question_text = _safe_text(row.get("Question", ""))
        if question_text:
            return (
                f"Question {expected_question_id}: {question_text}\n\n"
                "Please provide your answer and I will record it before moving to the next step."
            )
    return "Please provide your next NIF answer, and I will continue one step at a time."


def enforce_nifguide_response_contract(response_text: str, expected_question_id: str) -> str:
    text = _safe_text(response_text)
    if not NIF_GUIDE_STRICT_OUTPUT_VALIDATION:
        return text

    if not text:
        return build_nifguide_fallback_message(expected_question_id)

    # Only block clear SQL-shaped content; do not block natural-language
    # guidance like "please select an option".
    looks_like_sql = bool(
        re.search(r"(?is)\bselect\b[\s\S]{0,600}\bfrom\b", text)
        or re.search(r"(?im)^\s*with\s+[a-z0-9_]+\s+as\s*\(", text)
        or re.search(r"(?im)^\s*(insert|update|delete|drop|alter)\b", text)
    )
    if "```sql" in text.lower() or looks_like_sql:
        return build_nifguide_fallback_message(expected_question_id)

    heading_pattern = re.compile(r"(?im)^\s*\*{0,2}\s*question\s+([A-Z0-9_]+)\s*:")
    heading_matches = list(heading_pattern.finditer(text))

    # Hard guard: when we know expected next question, require explicit
    # "Question <ID>:" in the assistant response. This prevents confirmation-only
    # replies like "You selected ... saved ..." from being shown without the next step.
    if expected_question_id and not heading_matches:
        return build_nifguide_fallback_message(expected_question_id)

    if len(heading_matches) > 1:
        text = text[: heading_matches[1].start()].strip()
        heading_matches = list(heading_pattern.finditer(text))

    if heading_matches:
        found_qid = _safe_text(heading_matches[0].group(1)).upper()
        if found_qid and found_qid not in expert_rule_index_by_question_id:
            return build_nifguide_fallback_message(expected_question_id)
        if expected_question_id and found_qid and found_qid != expected_question_id:
            text = heading_pattern.sub(
                f"Question {expected_question_id}:",
                text,
                count=1,
            )

    has_option_list = bool(re.search(r"(?m)^\s*(?:\d+\.|[-*])\s+\S+", text))
    if expected_question_id and "?" not in text and not has_option_list:
        completion_markers = (
            "completed",
            "complete",
            "all required",
            "saved",
            "done",
            "end_req_initiate_q",
        )
        if not any(marker in text.lower() for marker in completion_markers):
            return build_nifguide_fallback_message(expected_question_id)

    return text.strip()


def _extract_inline_choice_list(question_text: str) -> List[str]:
    text = _safe_text(question_text)
    if not text:
        return []
    normalized = (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("‘", "'")
    )
    match = re.search(r"\b(?:in|for)\s+(.+?)\?\s*$", normalized, flags=re.IGNORECASE)
    if not match:
        return []
    segment = match.group(1)
    segment = re.sub(r"\s+or\s+", ", ", segment, flags=re.IGNORECASE)
    segment = re.sub(r"\s+and\s+", ", ", segment, flags=re.IGNORECASE)

    options = []
    seen = set()
    for raw in segment.split(","):
        option = re.sub(r"\s+", " ", raw).strip(" '\"()")
        if not option:
            continue
        if len(option) > 48:
            continue
        key = option.lower()
        if key in seen:
            continue
        seen.add(key)
        options.append(option)
    if len(options) < 2 or len(options) > 15:
        return []
    return options


def _compact_question_for_options(question_text: str, options: List[str]) -> str:
    text = _safe_text(question_text)
    if not text or not options:
        return text
    text_lc = text.lower()
    first_idx = None
    for option in options:
        idx = text_lc.find(option.lower())
        if idx == -1:
            continue
        if first_idx is None or idx < first_idx:
            first_idx = idx
    if first_idx is None:
        return text
    prefix = text[:first_idx].rstrip(" ,;:-")
    if len(prefix) < 12:
        return text
    if not prefix.endswith("?"):
        prefix = prefix.rstrip(" ?") + "?"
    return prefix


def format_nifguide_choices_multiline(response_text: str) -> str:
    """
    For New/Load NIF responses: if question line contains inline comma-separated
    choices and no numbered list exists, convert choices to one-per-line.
    """
    text = _safe_text(response_text)
    if not text:
        return text

    # Collapse QA-style confirmation preamble into the next question block.
    # Example:
    # "You selected <...>. Let me save that now." + "Question ...".
    if re.search(r"(?im)^\s*(?:\*{0,2}\s*)?question\s+[A-Z0-9_\.:-]+\s*:", text):
        text = re.sub(
            r"(?is)^\s*you\s+selected\b.*?\blet\s+me\s+save\s+that\s+now\.?\s*",
            "",
            text,
        ).strip()

    if re.search(r"(?m)^\s*\d+\.\s+\S+", text):
        return text

    lines = text.splitlines()
    for i, line in enumerate(lines):
        line_text = _safe_text(line)
        if not line_text:
            continue
        if "?" not in line_text:
            continue
        # Fast skip: no inline list signal.
        if "," not in line_text and " or " not in line_text.lower():
            continue

        question_text = line_text
        prefix = ""

        # Case A: canonical "Question <ID>:" prefix
        match = re.match(r"(?is)^(\s*\*{0,2}\s*Question\s+[A-Z0-9_\.:-]+\s*:\s*)(.+)$", line_text)
        if match:
            prefix = str(match.group(1) or "")
            if not prefix.endswith(" "):
                prefix += " "
            question_text = _safe_text(match.group(2))
        else:
            # Case B: markdown bold prefix like "**Question:** ..."
            match2 = re.match(r"(?is)^(\s*\*{0,2}\s*Question\s*:\s*\*{0,2}\s*)(.+)$", line_text)
            if match2:
                prefix = str(match2.group(1) or "")
                if not prefix.endswith(" "):
                    prefix += " "
                question_text = _safe_text(match2.group(2))

        options = _extract_inline_choice_list(question_text)
        if not options:
            continue

        base_question = _compact_question_for_options(question_text, options)
        new_lines = lines[:]
        if prefix:
            new_lines[i] = f"{prefix}{base_question}"
        else:
            new_lines[i] = base_question

        insert_lines = [""]
        insert_lines.extend([f"{idx}. {option}" for idx, option in enumerate(options, start=1)])
        insert_lines.extend(["", "Reply with the option number or option text."])
        new_lines = new_lines[: i + 1] + insert_lines + new_lines[i + 1 :]
        return "\n".join(new_lines)

    return text


def build_nifguide_system_message(
    current_username: str,
    nif_progress_df: Optional[pd.DataFrame],
    user_query: str,
    prompt_mode: Optional[str] = None,
) -> str:
    mode = (prompt_mode or NIF_GUIDE_PROMPT_MODE).strip().lower()
    if mode not in {"legacy", "compact"}:
        mode = "compact"

    expected_question_id = infer_expected_nif_question_id(
        nif_progress_df=nif_progress_df,
        user_query=user_query,
    )
    progress_snapshot = _build_nif_progress_snapshot(nif_progress_df)

    include_all_rules = mode == "legacy"
    if include_all_rules:
        focused_rules_df = expert_system_rules.copy()
    else:
        focus_indices = _select_nif_focus_rule_indices(expected_question_id, user_query)
        focused_rules_df = (
            expert_system_rules.iloc[focus_indices].copy()
            if focus_indices
            else expert_system_rules.head(6).copy()
        )

    rules_markdown = focused_rules_df.to_markdown(index=False)
    dropdown_block = _build_nif_dropdown_reference_block(
        focused_rules_df,
        include_all=include_all_rules,
    )

    if include_all_rules:
        glossary_block = str(glossary_and_db_terms_dict)
    else:
        glossary_subset = _build_nif_glossary_subset(
            user_query=user_query,
            max_items=NIF_GUIDE_MAX_GLOSSARY_TERMS,
        )
        if glossary_subset:
            glossary_block = str(glossary_subset)
        else:
            glossary_block = "(No high-signal glossary terms matched this user turn.)"

    return f'''
            You are an expert in Kellanova's New Item Form (NIF). This form is used
            to specify new products or variations of existing products. Your role
            is to guide the user through the 'Requestor - Project Initiation'
            section of the NIF, which contains the PROJECT_INITIATION_FIELDS listed
            here:
                <PROJECT_INITIATION_FIELDS>
                {list(nif_fields_req_init_template['field_name_and_number'])}
                </PROJECT_INITIATION_FIELDS>

            {llm_instruction_scope_of_discussion}

            # SESSION CONTEXT
            - Current user: {current_username}
            - Prompt mode: {mode}
            - Expected question ID for this turn: {expected_question_id}

            <NIF_PROGRESS_SNAPSHOT>
            {progress_snapshot}
            </NIF_PROGRESS_SNAPSHOT>

            # STRICT ADHERENCE TO RULES
            You MUST follow these rules without exception:
            - Process EXACTLY ONE row from STEP_BY_STEP_RULES at a time
            - NEVER skip ahead or process multiple rows simultaneously
            - NEVER proceed to the next question until the current row is complete
            - ALWAYS follow the "Go to" instruction exactly as specified
            - Do NOT improvise or interpret instructions creatively - follow them literally
            - In compact prompt mode, treat EXPECTED question ID as authoritative for this turn.

            # INTERACTION WITH THE USER
            Begin with a simple greeting and state your role.

            You will be told at the start of the conversation whether the user is starting
            a new NIF or continuing an in-progress NIF.

            If the user is starting a new NIF, start with the first question in the
            STEP_BY_STEP_RULES.

            If the user is resuming a NIF in progress, use the latest user state in
            NIF_PROGRESS_SNAPSHOT and continue at the expected question ID.

            When proceeding, follow the QUESTION FLOW PROTOCOL:
            1. State the current Question ID (e.g., "**Question 2.1:**")
            2. Ask the question EXACTLY as written in the "Question" column
            3. Wait for the user's response - do not proceed without it
               - Exception: if the instructions say this question is not necessary, the user
                 can submit an empty string or the words "blank", "none", or similar.
            4. Execute instructions ONLY for the current Question ID
            5. Call update_nif_progress for each field update
            6. Only then proceed to the next question

            If the user asks to go back to a previous question, you may do so, but you must
            follow the instructions again one-at-a-time from that question. DO NOT ASSUME
            that the answers to subsequent questions are the same as before.

            If the user asks for clarification about a question, refer to the GLOSSARY and
            provide definitions of relevant terms.

            <STEP_BY_STEP_RULES>
            {rules_markdown}
            </STEP_BY_STEP_RULES>

            <GLOSSARY>
            {glossary_block}
            </GLOSSARY>

            ## PARSING INSTRUCTIONS (CRITICAL)
            For each instruction in the "Instructions" column:
            1. **No Question Required**: If "Question" column says 'None', execute instructions immediately.
            2. **List of Possible Values**: always show these as a numbered list with one item per line.
               - If question text itself contains inline comma-separated choices,
                 do NOT leave them inline; render those choices as numbered list
                 entries on new lines.
            3. **Dropdown Lists**: "Display dd: reference list [NAME]"
               - Look up [NAME] in DROPDOWN REFERENCE LISTS below
               - Display as numbered list, one item per line
               - Wait for user selection. If the user answers with a number,
                 use the item corresponding to that number in the list you provided.
            4. **Field Updates**: Formatted as "FIELD_NAME" (FIELD_NUMBER)
               - FIELD_NUMBER is the required parameter for update_nif_progress
            5. **Value Types**:
               - <'VALUE'>: Use this EXACT string (without angle brackets)
               - <FREEFORM>: Use user's literal answer after validation
            6. **Navigation**: "Go to [Question ID]"
               - This specifies your NEXT question
               - If conditional (if/then), follow the matching condition
               - If no "Go to", proceed to the next row in STEP_BY_STEP_RULES
            7. **Multiple Fields**:
               - Call update_nif_progress separately for EACH field
               - Process in order listed

            ### DROPDOWN REFERENCE LISTS
            {dropdown_block}

            ### FUNCTION CALLING REQUIREMENTS
            When calling update_nif_progress:
            - Call IMMEDIATELY after collecting each field value
            - Use parameters: LAST_QUESTION_ID, LAST_VALUE, and FIELD_NUMBER (only if specified)
            - Do NOT proceed until function returns successfully
            - Do NOT narrate backend persistence on every turn (avoid phrases like "Now saving ...")
            - LAST_VALUE format:
              * For <'VALUE'>: the exact value without angle brackets
              * For <FREEFORM>: user's validated literal answer

            # PROHIBITED BEHAVIORS
            You MUST NOT:
            - Summarize or skip steps
            - Ask multiple questions from different rows simultaneously
            - Assume answers or pre-fill fields
            - Deviate from "Go to" instructions
            - Proceed with invalid or unclear user responses

            # SELF-VERIFICATION BEFORE PROCEEDING
            Before each new question, verify:
            □ Asked question from current row?
            □ Received and validated user answer?
            □ Called update_nif_progress for all required fields?
            □ Identified correct next Question ID?

            If any item is unchecked, DO NOT PROCEED.
        '''


def refresh_nifguide_task_prompt(session_task, current_username, user_query, nif_progress_df):
    compact_prompt = build_nifguide_system_message(
        current_username=current_username,
        nif_progress_df=nif_progress_df,
        user_query=user_query,
        prompt_mode=NIF_GUIDE_PROMPT_MODE,
    )
    session_task.system_message = compact_prompt
    if getattr(session_task, "agent", None) is not None:
        session_task.agent.system_message = compact_prompt


def _message_role_value(msg) -> str:
    role = getattr(msg, "role", "")
    return role.value if hasattr(role, "value") else str(role)


def trim_session_agent_history(agent, max_messages: int) -> bool:
    """
    Keep latest system message plus latest non-system messages.
    Returns True when a trim occurred.
    """
    history = list(getattr(agent, "message_history", []) or [])
    if max_messages <= 0 or not history:
        return False

    system_messages = [msg for msg in history if _message_role_value(msg).lower() == "system"]
    non_system_messages = [msg for msg in history if _message_role_value(msg).lower() != "system"]

    if len(non_system_messages) <= max_messages:
        return False

    trimmed_non_system = non_system_messages[-max_messages:]
    if system_messages:
        trimmed_history = [system_messages[-1]] + trimmed_non_system
    else:
        trimmed_history = trimmed_non_system

    agent.message_history = trimmed_history
    return True


def trim_agent_history_for_task(agent, task_name: str) -> bool:
    if agent is None:
        return False
    task_name = _safe_text(task_name)
    if task_name == "nifguide_task":
        if not NIF_GUIDE_TRIM_HISTORY:
            return False
        return trim_session_agent_history(agent, NIF_GUIDE_HISTORY_WINDOW)
    if NIF_HISTORY_TRIM_OTHER_TASKS:
        return trim_session_agent_history(agent, NIF_OTHER_TASK_HISTORY_WINDOW)
    return False


def _history_entry_fingerprint(entry: dict) -> str:
    role = _safe_text(entry.get("role"))
    content = _safe_text(entry.get("content"))
    timestamp = _safe_text(entry.get("timestamp"))
    function_call = _safe_text(entry.get("function_call"))
    tool_calls = _safe_text(entry.get("tool_calls"))
    return "|".join([role, content, timestamp, function_call, tool_calls])


# =============================================================================
#### History management
# =============================================================================
#!!! These might need to be agent-specific!
# This will load either the SESSION_HISTORY_FILE or the LONGTERM_HISTORY_FILE
# depending on whether SESSION_ID is passed.
def load_chat_history(user_email, SESSION_ID=None, include_system=False):
    """Loads chat history from the HISTORY_FILE as a list of LLMMessage objects."""
    user_history_dir = get_user_history_dir(user_email)

    if SESSION_ID:
        HISTORY_FILE = user_history_dir / f"chat_history_{SESSION_ID}.json"
    else:
        HISTORY_FILE = user_history_dir / f"chat_history.json"

    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r') as f:
            history_data = json.load(f)
            # Convert each dictionary back to an LLMMessage object
            if include_system:
                return [LLMMessage.from_dict(item) for item in history_data]
            else:   # Exclude system instructions
                return [LLMMessage.from_dict(item) for item in history_data if item['role'] != 'system']
    except json.JSONDecodeError:
        print("Warning: History file is not valid JSON. Starting with empty history.")
        return []
    except Exception as e:
        print(f"Error loading chat history: {e}")
        return []

def save_chat_history(message_history, user_email, SESSION_ID):
    """Saves the current chat history to the user-specific HISTORY_FILE as a list of dictionaries."""
    user_history_dir = get_user_history_dir(user_email)

    # Create two files: one session-specific and one capturing all sessions for the user
    SESSION_HISTORY_FILE = user_history_dir / f"chat_history_{SESSION_ID}.json"
    LONGTERM_HISTORY_FILE = user_history_dir / f"chat_history.json"

    # Convert LLMMessage objects to dictionaries in the format you expect
    history_to_save = []
    for msg in message_history:
        try:
            # Not all LLMMessage objects have a function_call or tool_calls. If they exist, add them.
            try:
                function_call = str(msg.function_call)
            except:
                function_call = None
            try:
                tool_calls = str(msg.tool_calls)
            except:
                tool_calls = None

            # This mirrors the old system's structure for storing history
            history_to_save.append({
                "role": msg.role.value if isinstance(msg.role, Role) else msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "function_call":function_call,
                "tool_calls":tool_calls
            })
        except Exception as e:
            print(f"save_chat_history exception: {e}")

    # Write session history file
    with open(SESSION_HISTORY_FILE, 'w') as f:
        json.dump(history_to_save, f, indent=2)

    # Append to long-term history file
    # Read existing long term history if it exists
    if os.path.exists(LONGTERM_HISTORY_FILE):
        with open(LONGTERM_HISTORY_FILE, 'r') as f:
            try:
                history_array = json.load(f)
            except json.JSONDecodeError:
                print("Warning: History file is not valid JSON. Starting with empty history.")
                history_array = []
    else:
        history_array = []

    if NIF_LONGTERM_HISTORY_DEDUP:
        existing_fingerprints = set()
        for entry in history_array:
            if isinstance(entry, dict):
                existing_fingerprints.add(_history_entry_fingerprint(entry))

        incremental_entries = []
        for entry in history_to_save:
            if not isinstance(entry, dict):
                continue
            fp = _history_entry_fingerprint(entry)
            if fp in existing_fingerprints:
                continue
            incremental_entries.append(entry)
            existing_fingerprints.add(fp)

        history_array.extend(incremental_entries)
    else:
        history_array.extend(history_to_save)

    if NIF_LONGTERM_MAX_ENTRIES > 0 and len(history_array) > NIF_LONGTERM_MAX_ENTRIES:
        history_array = history_array[-NIF_LONGTERM_MAX_ENTRIES:]

    # Write back the entire array
    with open(LONGTERM_HISTORY_FILE, 'w') as f:
        json.dump(history_array, f, indent=2)

def cleanup_old_history_files(days_threshold=30):
    """
    Iterates through all user folders and deletes chat history files that are
    older than the specified number of days.
    """
    print(f"Starting cleanup of history files older than {days_threshold} days...")

    # Calculate the cutoff date
    cutoff_date = datetime.now() - timedelta(days=days_threshold)
    files_deleted_count = 0
    entries_deleted_count = 0

    # Iterate through all items in the base user files directory
    for user_id_folder in USER_FILES_DIR.iterdir():
        # Only process directories
        if user_id_folder.is_dir():
            # Construct the path to the user's history directory
            user_history_dir = user_id_folder / 'history'

            if user_history_dir.is_dir():
                print(f"Checking history for: {user_id_folder.name}")

                # Iterate through all files in the history directory
                for file_path in user_history_dir.iterdir():
                    if file_path.is_file():
                        try:
                            # Get the last modification time (timestamp) of the file
                            file_mod_timestamp = file_path.stat().st_mtime
                            file_mod_date = datetime.fromtimestamp(file_mod_timestamp)

                            # If the file is older than the cutoff date, delete
                            # This will delete all SESSION history files that are older than the cutoff
                            # This will also delete the LONG TERM history file if it has not been modified more recently
                            if file_mod_date < cutoff_date:
                                # Delete the file
                                os.remove(file_path)
                                files_deleted_count += 1
                                print(f"  -> Deleted: {file_path.name} (Modified: {file_mod_date.strftime('%Y-%m-%d')})")

                            # If the file has a modification date more recently, remove any entries that are older than the cutoff
                            # This will update the LONG TERM history file by removing older entries
                            else:
                                # Read file
                                with open(file_path, 'r') as f:
                                    try:
                                        history_data = json.load(f)
                                    except json.JSONDecodeError:
                                        print("Warning: History file is not valid JSON. Starting with empty history.")
                                        history_data = []

                                # Loop through entries
                                new_history_data = []   # Initialize
                                for entry in history_data:
                                    entry_timestamp = datetime.fromisoformat(entry['timestamp'])
                                    if entry_timestamp < cutoff_date:
                                        del entry
                                        entries_deleted_count += 1
                                    else:
                                        new_history_data.append(entry)

                                # Write back to file
                                try:
                                    with open(file_path, 'w') as f:
                                        json.dump(new_history_data, f, indent=2)
                                except Exception as e:
                                    print(f"Error writing updated history {file_path}: {e}")

                        except Exception as e:
                            print(f"Error processing file {file_path}: {e}")

    print(f"Cleanup complete. Total files deleted: {files_deleted_count}. Total entries deleted from long-term history: {entries_deleted_count}.")



# =============================================================================
#### First version: storing multiple NIFs in single table
# =============================================================================
def create_or_load_user_nif_progress_data(user_email, USERID:str):
    funcname = inspect.currentframe().f_code.co_name

    name_for_index = 'nifty_id'

    user_history_dir = get_user_history_dir(user_email)
    user_specific_progress_file = os.path.join(user_history_dir, f"nif_progress_{USERID}.csv")

    if os.path.isfile(user_specific_progress_file):
        print(f"<{funcname}> Loading existing NIF progress file: {user_specific_progress_file}")
        user_nif_progress_df = pd.read_csv(user_specific_progress_file, index_col=name_for_index)
    else:
        print(f"<{funcname}> User does not have a saved progress file. Creating a new dataframe.")
        default_id = f"{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"       # Default index: current datetime
        user_nif_progress_df = pd.DataFrame(
            columns=list(nif_fields_req_init_template['field_name_and_number'])
            ,index=[default_id]    # Index will be used to track multiple NIFs in progress
        ).rename_axis(name_for_index, axis='index')

        # Fill in placeholder values
        user_nif_progress_df = user_nif_progress_df.fillna('<NOT YET DETERMINED>')

    return user_nif_progress_df

def update_user_nif_progress_data(
        NIF_PROGRESS_DF:object      # Dataframe user_nif_progress_df created by create_or_load_user_nif_progress_data()
        ,FIELD_NUMBER:int
        ,VALUE:str
        ,INDEX_VALUE:str=None       # Update the record with this index value. Use if the user has multiple NIFs in progress. If None, will update the last row. If passed a value that isn't on the dataframe, will add a new row.
    ):
    funcname = inspect.currentframe().f_code.co_name

    df_mod = NIF_PROGRESS_DF.copy()
    name_for_index = df_mod.index.name

    # Check that FIELD_NUMBER provided is valid
    valid_field_numbers = list(nif_fields_req_init_template['field_number'])
    if FIELD_NUMBER in valid_field_numbers:

        # Get column name from template based on field number
        _field_number = (nif_fields_req_init_template['field_number'] == FIELD_NUMBER)
        nif_progress_colname = nif_fields_req_init_template.loc[_field_number, 'field_name_and_number'].item()

        # Check if INDEX_VALUE exists
        if INDEX_VALUE:
            index_to_update = INDEX_VALUE
            try:
                df_mod.loc[index_to_update]
            except KeyError:    # Create new record if needed
                print(f"<{funcname}> Index value '{index_to_update}' doesn't exist. Creating new record.")
                new_record = pd.DataFrame(columns=list(df_mod), index=[index_to_update]).rename_axis(name_for_index, axis='index')
                new_record = new_record.fillna('<NOT YET DETERMINED>')
                df_mod = pd.concat([df_mod, new_record])
        else:   # If no INDEX_VALUE specified, update the last record
            index_to_update = df_mod.iloc[-1].name

        # Update
        df_mod.loc[index_to_update, nif_progress_colname] = VALUE
        print(f"<{funcname}> Updated dataframe {NIF_PROGRESS_DF}: Field {nif_progress_colname} updated with value {VALUE}.")

    else:
        raise Exception(f"<{funcname}> ERROR: Field number provided ({FIELD_NUMBER}) is not valid.")

    return df_mod

def save_user_nif_progress_data(
        user_email,
        USERID:str
        ,NIF_PROGRESS_DF:object    # Dataframe user_nif_progress_df created by create_or_load_user_nif_progress_data()
    ):
    funcname = inspect.currentframe().f_code.co_name

    user_history_dir = get_user_history_dir(user_email)
    user_specific_progress_file = os.path.join(user_history_dir, f"nif_progress_{USERID}.csv")
    NIF_PROGRESS_DF.to_csv(user_specific_progress_file)     # Keep the index!
    print(f"<{funcname}> User NIF progress dataframe saved to file {user_specific_progress_file}.")

    return None

'''
test_user_id = 'user_a'

# Create or load
global active_user_nif_progress_df      # Make it global so NIF Guide agent can modify it
active_user_nif_progress_df = create_or_load_user_nif_progress_data(user_email, test_user_id)

# Invalid field number
active_user_nif_progress_df = update_user_nif_progress_data(active_user_nif_progress_df, 100, 'user_a@knova.com')

# No index specified
active_user_nif_progress_df = update_user_nif_progress_data(active_user_nif_progress_df, 1002, 'user_a@knova.com')

# Update existing record
existing_index_value = '20251017_125115'
active_user_nif_progress_df = update_user_nif_progress_data(active_user_nif_progress_df, 1002, 'user_a2@knova.com', existing_index_value)

# Add new record
active_user_nif_progress_df = update_user_nif_progress_data(active_user_nif_progress_df, 1002, 'user_a@knova.com', 'new_nif')

# Save to disk
save_user_nif_progress_data(user_email, test_user_id, active_user_nif_progress_df)
'''
# =============================================================================
#### Second version: each in-progress NIF is its own table
# =============================================================================
'''
Use this with Dash buttons: Save Progress, Load NIF, Start a New NIF.
This approach means Dash will load the single NIF in progress selected by the
user. All functions can then use the global active_user_nif_progress_df.
'''
# To use with 'Start a New NIF button'
# Usage:
#   user_nif_progress_df = create_active_user_nif_progress_data()
def create_active_user_nif_progress_data():
    funcname = inspect.currentframe().f_code.co_name

    # Create dataframe from template
    user_nif_progress_df = pd.DataFrame(
        columns=list(nif_fields_req_init_template['field_name_and_number'])
        ,index=[0]
    )

    # Add columns for agent to track its progress
    # Put these first
    user_nif_progress_df['_agentref_last_question_answered'] = np.nan
    user_nif_progress_df['_agentref_last_answer_given'] = np.nan

    cols_first = ['_agentref_last_question_answered', '_agentref_last_answer_given']
    cols_other = [i for i in list(user_nif_progress_df) if i not in cols_first]
    user_nif_progress_df = user_nif_progress_df.reindex(columns=cols_first + cols_other)

    # Fill in placeholder values
    user_nif_progress_df = user_nif_progress_df.fillna('<NOT YET DETERMINED>')

    print(f"<{funcname}> User's NIF progress data initialized.")

    return user_nif_progress_df

def update_nif_progress_data(
        NIF_PROGRESS_DF:object          # The dataframe to update. Should be one created by create_active_user_nif_progress_data().
        ,LAST_QUESTION_ANSWERED:str     # The Question ID from expert_system_rules that was most recently answered
        ,LAST_ANSWER_GIVEN:str          # The answer given by the user.
        ,FIELD_NUMBER:int=None          # Field number you want to update. Must exist in nif_fields_req_init_template. If None, only update LAST_QUESTION_ANSWERED and LAST_ANSWER_GIVEN (to capture a decision question that does not get written to the NIF).
    ):
    funcname = inspect.currentframe().f_code.co_name

    nif_progress_df_updated = NIF_PROGRESS_DF.copy()

    # Update reference columns
    nif_progress_df_updated['_agentref_last_question_answered'] = LAST_QUESTION_ANSWERED
    nif_progress_df_updated['_agentref_last_answer_given'] = LAST_ANSWER_GIVEN
    print(f"<{funcname}> Last question updated to '{LAST_QUESTION_ANSWERED}'.")

    # Check that FIELD_NUMBER provided is valid
    valid_field_numbers = list(nif_fields_req_init_template['field_number'])
    if FIELD_NUMBER:    # If field number is provided
        if FIELD_NUMBER in valid_field_numbers:

            # Get column name from template based on field number
            _field_number = (nif_fields_req_init_template['field_number'] == FIELD_NUMBER)
            nif_progress_colname = nif_fields_req_init_template.loc[_field_number, 'field_name_and_number'].item()

            # Update
            nif_progress_df_updated[nif_progress_colname] = LAST_ANSWER_GIVEN
            print(f"<{funcname}> Field '{nif_progress_colname}' updated with value '{LAST_ANSWER_GIVEN}'.")

        else:
            raise Exception(f"<{funcname}> ERROR: Field number provided ({FIELD_NUMBER}) is not valid.")

    return nif_progress_df_updated

# DEV: this function will also update the LAST_QUESTION_ANSWERED and LAST_ANSWER_GIVEN.
def update_active_user_nif_progress_data_2(
        LAST_QUESTION_ANSWERED:str      # The Question ID from expert_system_rules that was most recently answered
        ,LAST_ANSWER_GIVEN:str          # The answer given by the user.
        ,FIELD_NUMBER:int=None          # Field number you want to update. Must exist in nif_fields_req_init_template. If None, only update LAST_QUESTION_ANSWERED and LAST_ANSWER_GIVEN (to capture a decision question that does not get written to the NIF).
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Update reference columns
    active_user_nif_progress_df['_agentref_last_question_answered'] = LAST_QUESTION_ANSWERED
    active_user_nif_progress_df['_agentref_last_answer_given'] = LAST_ANSWER_GIVEN
    print(f"<{funcname}> Last question updated to '{LAST_QUESTION_ANSWERED}'.")

    # Check that FIELD_NUMBER provided is valid
    valid_field_numbers = list(nif_fields_req_init_template['field_number'])
    if FIELD_NUMBER:    # If field number is provided
        if FIELD_NUMBER in valid_field_numbers:

            # Get column name from template based on field number
            _field_number = (nif_fields_req_init_template['field_number'] == FIELD_NUMBER)
            nif_progress_colname = nif_fields_req_init_template.loc[_field_number, 'field_name_and_number'].item()

            # Update
            active_user_nif_progress_df[nif_progress_colname] = LAST_ANSWER_GIVEN
            print(f"<{funcname}> Field '{nif_progress_colname}' updated with value '{LAST_ANSWER_GIVEN}'.")

        else:
            raise Exception(f"<{funcname}> ERROR: Field number provided ({FIELD_NUMBER}) is not valid.")

    return None

# To use with "Save progress" button
# User will provide a filename. Must be CSV.
# Append [completed] to filename based on _agentref_last_question_answered
def save_active_user_nif_progress_data(
        FULL_PATH_TO_FILE:str       # User will provide a filename. Dash will provide path.
    ):
    funcname = inspect.currentframe().f_code.co_name

    full_path_touse = FULL_PATH_TO_FILE

    # If filename does not end in .csv, append
    if full_path_touse[-4:] != '.csv':
        full_path_touse = full_path_touse + '.csv'

    active_user_nif_progress_df.to_csv(full_path_touse)
    print(f"<{funcname}> User's NIF progress data saved to file: {full_path_touse}.")

    return None

# To use with "Load a NIF in progress" button
# User will select a file
def load_active_user_nif_progress_data(
        FULL_PATH_TO_FILE:str       # Dash will offer a browser window and user will select file
    ):
    funcname = inspect.currentframe().f_code.co_name

    # If filename does not end in .csv, throw error
    if FULL_PATH_TO_FILE[-4:] != '.csv':
        raise Exception(f"<{funcname}> ERROR: Filename provided ({FULL_PATH_TO_FILE}) is not a CSV.")

    else:
        # Load file
        user_nif_progress_df = pd.read_csv(FULL_PATH_TO_FILE, index_col=0)
        print(f"<{funcname}> User's NIF progress data loaded from file: {FULL_PATH_TO_FILE}.")

    return user_nif_progress_df

#%% GENERAL LLM TOOLS
'''
Note agent-specific tools are defined with their agents.
'''
# =============================================================================
#### Agent configs
# =============================================================================
# Create an agent config WITHOUT a system prompt to be used for multiple agents.
# Each agent will be wrapped in a task with its own system prompt
# agent_config_gpt4o = lr.ChatAgentConfig(llm=utils.azure_llm_gpt4o)

agent_config_claude4 = lr.ChatAgentConfig(llm=utils.aws_llm_claude4)
agent_config_claude35 = lr.ChatAgentConfig(llm=utils.aws_llm_claude35)
agent_config_claude35_sonnet = lr.ChatAgentConfig(llm=utils.aws_llm_claude35_sonnet)
agent_config_gptoss = lr.ChatAgentConfig(llm=utils.aws_llm_gptoss)


def get_docsearch_agent_config() -> lr.ChatAgentConfig:
    """
    Use the app-wide provider/model selection for training resources retrieval.
    """
    return utils.build_chat_agent_config(task_kind="docsearch")


def get_nifguide_agent_config() -> lr.ChatAgentConfig:
    """
    Use the app-wide provider/model selection for New NIF and NIF field questions.
    """
    return utils.build_chat_agent_config(task_kind="nifguide")


def get_nif_database_agent_config() -> lr.ChatAgentConfig:
    """
    Use the app-wide provider/model selection for Search NIF.
    """
    return utils.build_chat_agent_config(task_kind="sql")

# Name of receptionist agent. All subtasks will address responses to this.
receptionist_name = 'ReceptionistAgent'

# =============================================================================
#### General functions
# =============================================================================
# String functions to simplify common system instructions
def pass_to_agent(AGENT_NAME:str):      # Input: the name of a pre-defined agent or task
    return f"pass the question to agent {AGENT_NAME} using the '{RecipientTool.name()}' tool with 'intended_recipient':'{AGENT_NAME}'"

def use_recipient_tool(RECIPIENT):
    return f"use the '{RecipientTool.name()}' tool with 'intended_recipient':'{RECIPIENT}'"

def formatted_list(LIST:list[str]):     # Input: a list of strings
    return_string = ''
    for item in LIST:
        return_string = return_string + '\n- ' + item
    return return_string

class get_file_link_tool(lr.agent.ToolMessage):
    # request: the name of this function for reference in system messages
    request:str = "get_file_link"

    # purpose: a description of what this function does. A good description is important so the LLM knows how to use it.
    purpose:str = "Append a folder path to a filename."

    # Any other variables defined here before the handle() method are treated as required arguments
    FILENAME:str   # The SQL query to use

    def handle(self):
        encoded_filename = urllib.parse.quote(self.FILENAME)
        return f"/assets/raw_docs/{encoded_filename}"

# =============================================================================
#### Strings
# =============================================================================
# Requirements document says:
'''
If asked a question that doesn’t pertain to NIF forms the tool will
respond reminding users the purpose of the tool and offer two
suggestions; 1. Use alternative tool such as chatgpt 2. Notify NIF
administrator the tool is behaving incorrectly.
'''

llm_instruction_scope_of_discussion = f'''
# SCOPE OF DISCUSSION

You are allowed to discuss Kellanova or Kellogg products, documents,
and forms, and the people and departments associated with them.
If the user asks about any other topic, politely decline to answer.
Suggest that if the user believes the question should be in scope,
they use the feedback button to notify a NIFTY administrator that
the app is behaving incorrectly.
'''

# NIF Guide document links
nif_training_guide_link = f"[Full NIF training guide]({get_web_url('NIF Training Deck v4.pdf')})"
nif_training_guide_link_p24 = f"[NIF Training Deck v4, page 24]({get_web_url('NIF Training Deck v4.pdf')}#page=24)"
setup_type_guide_link = f"[Detailed product type guide with images]({get_web_url('Setup Type Guide.pdf')})"
pre_ini_checklist_link = f"[Pre-Ini NIF Checklist]({get_web_url('Pre-Ini NIF Checklist 03.26.25.xlsx')})"
case_nif_guide = f"[Creating a CASE NIF]({get_web_url('Data-Ops-NIF-Create-a-CASE-Training-Deck---11.24.pdf')})"

data_custodians_link = f"[Data custodians documentation](https://kelloggcompany.sharepoint.com/sites/DataCustodians/SitePages/New-Item-Form.aspx)"
data_ops_ticket_link = f"[Submit a ticket with the data operations team](https://kelloggprod.service-now.com/kelloggsdc?id=sc_cat_item&sys_id=308fb1f11b6a35904e2a62c6624bcbf6)"

# nif_training_guide_html_link = get_html_link_new_tab('NIF Training Deck v4.pdf', 'NIF Training Deck v4')
# nif_training_guide_link_p24_html_link = get_html_link_new_tab('NIF Training Deck v4.pdf#page=24', 'NIF Training Deck v4, page 24')
# setup_type_guide_html_link = get_html_link_new_tab('Setup Type Guide.pdf', 'Setup Type Guide')
# pre_ini_checklist_html_link = get_html_link_new_tab('Pre-Ini NIF Checklist 03.26.25.xlsx', 'Pre-Ini NIF Checklist')
# case_nif_guide_html_link = get_html_link_new_tab('Data-Ops-NIF-Create-a-CASE-Training-Deck---11.24.pdf', 'Creating a CASE NIF')

# This wording is from Brandel
nifwalkthru_opening_statement = f'''
    To begin filling out the NIF, start by ensuring you have the required access
    by selecting this link to the tool: (link). If you don't have access, follow
    this guide for requesting access: (link).

    Additionally, here are some helpful resources:
        {formatted_list([nif_training_guide_link, setup_type_guide_link])}

    You can also find help at the following links:
        {formatted_list([data_custodians_link, data_ops_ticket_link])}

    I can guide you through these {len(nif_fields_poc_dict)} fields:
        {formatted_list(list(nif_fields_poc_dict))}.
'''

#%% NIF GUIDE AGENT
'''
[done] Add: instructions about allowed topics
[done] Add: read from user-specific NIF Field table on startup.
[done] Add: write to user-specific NIF Field table for each answer you get from the user.
!!! If user goes back to a previous question (more than 1 back), set all questions after that back to <NOT YET DETERMINED>.
!!! When user gets to the end of the NIF, change all remaining <NOT YET DETERMINED> fields to <N/A>

Dev plan:
    1. [done] Walk through expert system rules for a brand new NIF, writing to in-progress table as you go.
    2. [done] Pick up walkthrough for a partially completed NIF
    3. [done] Add display dropdown lookups for PRLs
    4. [done] Add glossary lookup
    5. [with module 3] Add NIF database agent subtask
    6. [with module 1] Add documentation agent subtask
'''
# =============================================================================
#### Functions and tools
# =============================================================================
class write_nif_progress_tool(lr.agent.ToolMessage):
    # request: the name of this function for reference in system messages
    request:str = "write_nif_progress"

    # purpose: a description of what this function does. A good description is important so the LLM knows how to use it.
    purpose:str = "To update the table tracking the user's answers for each NIF field in the step-by-step guide."

    # Any other variables defined here before the handle() method are treated as required arguments
    # NIF_PROGRESS_DF:object      # The NIF progress dataframe to modify
    LAST_QUESTION_ID:str        # The Question ID from expert_system_rules that was most recently answered
    LAST_VALUE:str              # The answer given by the user or the value determined from decision logic
    FIELD_NUMBER:int=None       # Field number you want to update. Must exist in nif_fields_req_init_template. If None, only update LAST_QUESTION_ID and LAST_VALUE (to capture a decision question that does not get written to the NIF).

    # handle() is based on update_active_user_nif_progress_data_2()
    # Testing using NIF_PROGRESS_DF of active_user_nif_progress_df
    def handle(self):
        # Update reference columns
        active_user_nif_progress_df['_agentref_last_question_answered'] = self.LAST_QUESTION_ID
        active_user_nif_progress_df['_agentref_last_answer_given'] = self.LAST_VALUE
        print(f"Last question updated to '{self.LAST_QUESTION_ID}'.")

        # Check that FIELD_NUMBER provided is valid
        valid_field_numbers = list(nif_fields_req_init_template['field_number'])
        if self.FIELD_NUMBER:    # If field number is provided
            if self.FIELD_NUMBER in valid_field_numbers:

                # Get column name from template based on field number
                _field_number = (nif_fields_req_init_template['field_number'] == self.FIELD_NUMBER)
                nif_progress_colname = nif_fields_req_init_template.loc[_field_number, 'field_name_and_number'].item()

                # Update
                active_user_nif_progress_df[nif_progress_colname] = self.LAST_VALUE
                print(f"Field '{nif_progress_colname}' updated with value '{self.LAST_VALUE}'.")

            else:
                raise Exception(f"ERROR: Field number provided ({self.FIELD_NUMBER}) is not valid.")

        return None

class check_nif_progress_tool(lr.agent.ToolMessage):
    # request: the name of this function for reference in system messages
    request:str = "check_nif_progress"

    # purpose: a description of what this function does. A good description is important so the LLM knows how to use it.
    purpose:str = "To view the table tracking the user's prior answers for each NIF field in the step-by-step guide."

    # Any other variables defined here before the handle() method are treated as required arguments
    FIELD_NAME:str = 'ALL'      # The name of the field to return. If 'ALL', show all.

    def handle(self):
        # active_user_nif_progress = active_user_nif_progress_df[['_agentref_last_question_answered', '_agentref_last_answer_given']].to_dict(orient='list')
        active_user_nif_progress = active_user_nif_progress_df.to_dict(orient='list')
        # active_user_nif_progress = active_user_nif_progress_df.to_markdown()

        if self.FIELD_NAME == 'ALL':
            return_string = f'''
                <ACTIVE_NIF_PROGRESS>
                {active_user_nif_progress}
                </ACTIVE_NIF_PROGRESS>
            '''
        else:
            return_string = active_user_nif_progress.get(self.FIELD_NAME, 'Invalid Field Name')

        return return_string

class update_nif_progress_tool(lr.agent.ToolMessage):
    """Tool to update values in a pandas DataFrame"""

    request: str = "update_nif_progress"
    purpose:str = "To update the table tracking the user's answers for each NIF field in the step-by-step guide."

    LAST_QUESTION_ID:str        # The Question ID from expert_system_rules that was most recently answered
    LAST_VALUE:str              # The answer given by the user or the value determined from decision logic
    FIELD_NUMBER:int=None       # Field number you want to update. Must exist in nif_fields_req_init_template. If None, only update LAST_QUESTION_ID and LAST_VALUE (to capture a decision question that does not get written to the NIF).

    def handle(self) -> str:
        """Handle the update operation - actual implementation in agent"""
        return None

class nif_guide_update_agent(lr.ChatAgent):
    def __init__(self, CONFIG: lr.ChatAgentConfig, DATAFRAME: pd.DataFrame = None):
        super().__init__(CONFIG)

        # Initialize with empty DataFrame if none provided
        self.df = DATAFRAME if DATAFRAME is not None else pd.DataFrame()

        # Enable the tools
        self.enable_message(update_nif_progress_tool)

    def update_nif_progress(self, msg: update_nif_progress_tool) -> str:
        # Update reference columns
        self.df['_agentref_last_question_answered'] = msg.LAST_QUESTION_ID
        self.df['_agentref_last_answer_given'] = msg.LAST_VALUE
        print(f"Last question updated to '{msg.LAST_QUESTION_ID}'.")

        # Check that FIELD_NUMBER provided is valid
        valid_field_numbers = list(nif_fields_req_init_template['field_number'])
        if msg.FIELD_NUMBER:    # If field number is provided
            if msg.FIELD_NUMBER in valid_field_numbers:

                # Get column name from template based on field number
                _field_number = (nif_fields_req_init_template['field_number'] == msg.FIELD_NUMBER)
                nif_progress_colname = nif_fields_req_init_template.loc[_field_number, 'field_name_and_number'].item()

                # Update
                self.df[nif_progress_colname] = msg.LAST_VALUE
                print(f"Field '{nif_progress_colname}' updated with value '{msg.LAST_VALUE}'.")

            else:
                raise Exception(f"ERROR: Field number provided ({msg.FIELD_NUMBER}) is not valid.")

        return None

    def get_dataframe(self) -> pd.DataFrame:
         """Return the current state of the DataFrame"""
         return self.df

    def set_dataframe(self, df: pd.DataFrame):
        """Allow setting DataFrame after initialization"""
        self.df = df

# =============================================================================
#### Config
# =============================================================================
'''
!!! When modifying NIF Guide Agent system message, watch out: my attempts to
remove the warning about "stuck for 5 steps" by either setting task.run(turns=1)
or instructing the agent to say 'DONE' have BROKEN THE DF UPDATE FUNCTIONALITY!
I am leaving the stuck for 5 steps warning because it does not interfere with
anything.
'''
# nifguide_agent_name = 'NIFGuideAgent'     # Hard coding this in create_task() function

# Create a dummy dataframe for defining the agent.
# This will be updated with the user's active progress df.
user_nif_progress_df = pd.DataFrame()

def create_nifguide_task(
        CURRENT_USERNAME:str='Unknown'     # The name of the current user. Need this in the definition even if it is not used to keep consistency for get_session_task().
        ,NIF_DF:object=None     # A dataframe created with create_active_user_nif_progress_data(). Can be updated later.
    ):
    nifguide_agent = nif_guide_update_agent(get_nifguide_agent_config(), NIF_DF)

    system_message = build_nifguide_system_message(
        current_username=CURRENT_USERNAME,
        nif_progress_df=NIF_DF if isinstance(NIF_DF, pd.DataFrame) else None,
        user_query="",
        prompt_mode=NIF_GUIDE_PROMPT_MODE,
    )

    nifguide_task = lr.Task(
        nifguide_agent
        ,name='NIFGuideAgent'
        ,system_message=system_message
        # ,interactive=True     # For testing
    
        # For use in Dash, setting interactive=False so the task exits after each round.
        # This is necessary to get a response to print in Dash.
        ,interactive=False
    
        # Setting restart=False so that message history persists when task exits.
        ,restart=False
    
        ,inf_loop_cycle_len=1   # Stop after a single repetition
    )
    nifguide_task._nifguide_prompt_context = {
        "prompt_mode": NIF_GUIDE_PROMPT_MODE,
    }

    return nifguide_task
        
nifguide_task = create_nifguide_task()

#%% NIF DATABASE QUERY TOOLS
class query_nif_db_tool(lr.agent.ToolMessage):
    # request: the name of this function for reference in system messages
    request:str = "query_nif_db"

    # purpose: a description of what this function does. A good description is important so the LLM knows how to use it.
    purpose:str = "Run a sqlite query on the NIF database and return the result."

    # Any other variables defined here before the handle() method are treated as required arguments
    SQL_QUERY:str   # The SQL query to use

    def handle(self):
        db = sqlite3.connect(f"file:{nif_database}?mode=ro", uri=True)
        c = db.cursor()
        try:
            c.execute(self.SQL_QUERY)
            return c.fetchall()     # This is returned to the LLM! The LLM uses it to formulate a response to the user.
        except sqlite3.OperationalError as err:     # If there's an error, tell the LLM about it.
            return f"The following error occured: {str(err)}"

class query_brands_db_tool(lr.agent.ToolMessage):
    # request: the name of this function for reference in system messages
    request:str = "query_brands_db"

    # purpose: a description of what this function does. A good description is important so the LLM knows how to use it.
    purpose:str = "Run a sqlite query on the database of active brands and return the result."

    # Any other variables defined here before the handle() method are treated as required arguments
    SQL_QUERY:str   # The SQL query to use

    def handle(self):
        db = sqlite3.connect(f"file:{brands_database}?mode=ro", uri=True)
        c = db.cursor()
        try:
            c.execute(self.SQL_QUERY)
            return c.fetchall()     # This is returned to the LLM! The LLM uses it to formulate a response to the user.
        except sqlite3.OperationalError as err:     # If there's an error, tell the LLM about it.
            return f"The following error occured: {str(err)}"


def normalize_nif_sql_query(sql_query: str) -> str:
    sql_query_clean = (sql_query or "").strip()
    if sql_query_clean.startswith("```"):
        sql_query_clean = re.sub(r"^```(?:sql)?\s*", "", sql_query_clean, flags=re.IGNORECASE)
        sql_query_clean = re.sub(r"\s*```$", "", sql_query_clean)
        sql_query_clean = sql_query_clean.strip()
    return sql_query_clean


def execute_nif_select_query(sql_query: str, max_rows: int | None = None) -> dict:
    """
    Execute read-only SQL on NIFS database and return structured result.
    """
    if max_rows is None:
        max_rows = NIF_DB_MAX_ROWS

    sql_query_clean = normalize_nif_sql_query(sql_query)
    result = {
        "sql": sql_query_clean,
        "columns": [],
        "rows": [],
        "row_count": 0,
        "displayed_row_count": 0,
        "truncated": False,
        "error": None,
    }

    query_upper = sql_query_clean.upper()
    if not sql_query_clean:
        result["error"] = "SQL query is empty."
        return result
    if not (query_upper.startswith("SELECT") or query_upper.startswith("WITH")):
        result["error"] = "Only SELECT/CTE (WITH) queries are allowed for security reasons."
        return result

    db = None
    try:
        db = sqlite3.connect(f"file:{nif_database}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        c = db.cursor()
        c.execute(sql_query_clean)
        rows = c.fetchall()

        result["row_count"] = len(rows)
        selected_rows = rows[:max_rows]
        result["displayed_row_count"] = len(selected_rows)
        result["truncated"] = len(rows) > max_rows

        if c.description:
            result["columns"] = [desc[0] for desc in c.description]

        serializable_rows = []
        for row in selected_rows:
            row_dict = dict(row)
            row_serializable = {}
            for key, value in row_dict.items():
                if isinstance(value, (str, int, float, bool)) or value is None:
                    row_serializable[key] = value
                else:
                    row_serializable[key] = str(value)
            serializable_rows.append(row_serializable)

        result["rows"] = serializable_rows
        return result

    except sqlite3.OperationalError as err:
        result["error"] = (
            f"SQL Operational Error: {str(err)}\n\n"
            "Please check your table names, column names, and SQL syntax."
        )
        return result
    except sqlite3.DatabaseError as err:
        result["error"] = f"Database Error: {str(err)}"
        return result
    except Exception as err:
        result["error"] = f"Unexpected Error: {type(err).__name__}: {str(err)}"
        return result
    finally:
        if db:
            db.close()


def format_nif_query_result_for_llm(
    result: dict,
    preview_rows: int = 25,
    include_row_preview: bool = True,
) -> str:
    """
    Convert structured query result to concise text for the agent response.
    """
    if not isinstance(result, dict):
        return "Unexpected Error: Query result payload is invalid."

    if result.get("error"):
        return str(result["error"])

    row_count = int(result.get("row_count", 0))
    if row_count == 0:
        return "Query executed successfully but returned no results."

    rows = result.get("rows", [])
    displayed_row_count = int(result.get("displayed_row_count", len(rows)))
    output = f"Query returned {row_count} row(s)."

    if include_row_preview and preview_rows > 0:
        output += "\n\n"
        if displayed_row_count <= preview_rows:
            for i, row in enumerate(rows[:preview_rows], 1):
                output += f"Row {i}:\n"
                for key, value in row.items():
                    output += f"  {key}: {value}\n"
                output += "\n"
        else:
            output += f"First {preview_rows} rows:\n"
            for i, row in enumerate(rows[:preview_rows], 1):
                output += f"Row {i}: {row}\n"
            output += f"\n... and {row_count - preview_rows} more rows.\n"
    else:
        columns = result.get("columns", []) or []
        if columns:
            output += f"\nColumns: {', '.join(columns)}"

    if result.get("truncated"):
        if include_row_preview and preview_rows > 0:
            output += (
                f"\nNote: showing {displayed_row_count} of {row_count} rows "
                f"(display limit reached)."
            )
        else:
            output += (
                f"\nNote: table shows first {displayed_row_count} of {row_count} rows "
                f"(display limit reached)."
            )

    return output.strip()

class query_nif_db_tool_2(lr.agent.ToolMessage):
    """
    Enhanced SQLite database query tool with better error handling,
    result formatting, and security features.
    """
    request: str = "query_nif_db_2"
    purpose: str = """Run a SELECT query on the NIF database and return formatted results.
    Only SELECT queries are allowed for safety. Returns results as a list of dictionaries
    with column names as keys. Limit results to up to NIF_DB_MAX_ROWS (default 2000)."""

    SQL_QUERY: str  # The SQL query to execute (SELECT only)

    def handle(self) -> str:
        """
        Execute the SQL query and return formatted results or error message.

        Returns:
            str: Formatted query results or error description
        """
        global last_nif_sql_query, last_nif_query_result
        structured_result = execute_nif_select_query(self.SQL_QUERY, max_rows=NIF_DB_MAX_ROWS)
        last_nif_sql_query = structured_result.get("sql")
        last_nif_query_result = structured_result
        # Provide actual row values to the LLM (especially for aggregate/count queries),
        # while keeping SQL traces hidden in UI unless explicitly enabled.
        return format_nif_query_result_for_llm(
            structured_result,
            preview_rows=25,
            include_row_preview=True,
        )

# A companion tool for schema exploration
class get_db_schema_tool(lr.agent.ToolMessage):
    """Tool to help the LLM understand the database structure."""
    request: str = "get_db_schema"
    purpose: str = """Get the schema of tables in the NIF database.
    Optionally specify a table name to get detailed column information for that table.
    If no table name is provided, returns a list of all tables."""

    table_name: Optional[str] = None  # Optional: specific table to describe

    def handle(self) -> str:
        db = None
        try:
            db = sqlite3.connect(f"file:{nif_database}?mode=ro", uri=True)
            c = db.cursor()

            if self.table_name:
                # Get detailed info about specific table
                c.execute(f"PRAGMA table_info({self.table_name})")
                columns = c.fetchall()

                if not columns:
                    return f"Table '{self.table_name}' not found in database."

                output = f"Schema for table '{self.table_name}':\n\n"
                output += "Columns:\n"
                for col in columns:
                    col_id, name, type_, notnull, default, pk = col
                    output += f"  - {name} ({type_})"
                    if pk:
                        output += " [PRIMARY KEY]"
                    if notnull:
                        output += " [NOT NULL]"
                    output += "\n"

                return output
            else:
                # List all tables
                c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = c.fetchall()

                if not tables:
                    return "No tables found in database."

                output = "Available tables in NIF database:\n\n"
                for table in tables:
                    output += f"  - {table[0]}\n"
                output += "\nUse get_db_schema with a table_name to see column details."

                return output

        except sqlite3.Error as err:
            return f"Database Error: {str(err)}"
        finally:
            if db:
                db.close()

#%% NIF DATABASE QUERY AGENT
'''
'''
# =============================================================================
#### Functions and tools
# =============================================================================
# =============================================================================
#### Config
# =============================================================================
def _normalize_status_values(status_rows):
    values = []
    for row in status_rows or []:
        if isinstance(row, (list, tuple)):
            if row:
                values.append(str(row[0]))
        elif row is not None:
            values.append(str(row))
    return [val for val in values if val.strip()]


def _select_nif_core_columns(column_list_cln):
    """
    Keep prompt schema compact by prioritizing commonly queried columns.
    """
    column_type_map = {str(name): str(col_type) for name, col_type in (column_list_cln or [])}
    preferred_columns = [
        "Title",
        "Status_Name",
        "Status",
        "Detailed Status",
        "Created",
        "Created_By",
        "LIM",
        "Material_Number",
        "Brief Material Description",
        "Material_Description",
        "Project Description",
        "Product Type",
        "Project Type",
        "COUNTRY",
        "Package UPC",
        "PDF Link",
    ]

    core_columns = [(name, column_type_map[name]) for name in preferred_columns if name in column_type_map]
    if len(core_columns) < 12:
        already_selected = {name for name, _ in core_columns}
        for name, col_type in column_list_cln or []:
            if name in already_selected:
                continue
            core_columns.append((str(name), str(col_type)))
            already_selected.add(name)
            if len(core_columns) >= 12:
                break

    return core_columns[:20]


def _load_nif_database_schema_snapshot(db_path: str) -> dict:
    """
    Return complete DB schema as:
    {
      "TABLE_A": [("col1", "TEXT"), ("col2", "INTEGER"), ...],
      ...
    }
    """
    schema_by_table = {}
    db = None
    try:
        db = sqlite3.connect(db_path)
        c = db.cursor()
        c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        table_rows = c.fetchall() or []
        for row in table_rows:
            table_name = str(row[0] or "").strip()
            if not table_name:
                continue
            c.execute(f"PRAGMA table_info('{table_name}')")
            cols = c.fetchall() or []
            col_pairs = []
            for col in cols:
                col_name = str(col[1] or "").strip()
                col_type = str(col[2] or "").strip() or "UNKNOWN"
                if col_name:
                    col_pairs.append((col_name, col_type))
            schema_by_table[table_name] = col_pairs
    except Exception as err:
        print(f"> WARNING: failed loading DB schema snapshot: {err}")
        return {}
    finally:
        if db:
            db.close()
    return schema_by_table


def _load_status_column_samples(db_path: str, table_name: str, per_column_limit: int = 12) -> dict:
    """
    Return distinct sample values for status-like columns in a table.
    """
    samples = {}
    db = None
    try:
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        c = db.cursor()
        c.execute(f"PRAGMA table_info('{table_name}')")
        cols = c.fetchall() or []
        status_cols = [str(col[1]) for col in cols if "status" in str(col[1]).lower()]
        for col_name in status_cols:
            q = (
                f'SELECT DISTINCT "{col_name}" FROM "{table_name}" '
                f'WHERE "{col_name}" IS NOT NULL AND trim(CAST("{col_name}" AS TEXT)) != "" '
                f'LIMIT {max(1, int(per_column_limit))}'
            )
            try:
                c.execute(q)
                vals = [str(r[0]) for r in (c.fetchall() or [])]
                if vals:
                    samples[col_name] = vals
            except Exception:
                continue
    except Exception as err:
        print(f"> WARNING: failed loading status-column samples: {err}")
    finally:
        if db:
            db.close()
    return samples


def get_relevant_db_abbreviations(query_text, max_items=None):
    """
    Dynamically select a small abbreviation subset relevant to the current query.
    """
    if max_items is None:
        max_items = NIF_DB_PROMPT_MAX_ABBREVIATIONS

    try:
        max_items = int(max_items)
    except Exception:
        max_items = NIF_DB_PROMPT_MAX_ABBREVIATIONS
    max_items = max(0, min(max_items, 200))
    if max_items == 0:
        return {}

    query_lc = str(query_text or "").strip().lower()
    if not query_lc:
        return {}
    query_tokens = set(re.findall(r"[a-z0-9]+", query_lc))

    def _to_text(value):
        if isinstance(value, pd.Series):
            if value.empty:
                return ""
            value = value.iloc[0]
        elif isinstance(value, (list, tuple)):
            if len(value) == 0:
                return ""
            value = value[0]
        try:
            if pd.isna(value):
                return ""
        except Exception:
            pass
        return str(value).strip()

    scored_items = []
    for desc, abbr in db_abbreviations_dict.items():
        desc_text = _to_text(desc)
        abbr_text = _to_text(abbr)
        if not desc_text or not abbr_text:
            continue

        desc_lc = desc_text.lower()
        abbr_lc = abbr_text.lower()
        desc_tokens = set(re.findall(r"[a-z0-9]+", desc_lc))
        abbr_tokens = set(re.findall(r"[a-z0-9]+", abbr_lc))

        score = 0
        if desc_lc in query_lc:
            score += 8
        if abbr_lc in query_lc:
            score += 8
        if query_tokens and desc_tokens:
            score += 2 * len(query_tokens.intersection(desc_tokens))
        if query_tokens and abbr_tokens:
            score += 3 * len(query_tokens.intersection(abbr_tokens))

        if score > 0:
            scored_items.append((score, len(desc_text), desc_text, abbr_text))

    if not scored_items:
        return {}

    scored_items.sort(key=lambda item: (-item[0], item[1], item[2].lower()))
    selected = {}
    seen_desc = set()
    for _, _, desc_text, abbr_text in scored_items:
        desc_key = desc_text.lower()
        if desc_key in seen_desc:
            continue
        selected[desc_text] = abbr_text
        seen_desc.add(desc_key)
        if len(selected) >= max_items:
            break

    return selected


def build_nif_database_system_message(
    table_name,
    core_columns,
    full_schema_by_table,
    status_values,
    status_column_samples,
    country_abbreviations,
    current_username,
    relevant_abbreviations,
    sql_mode_override,
):
    relevant_abbreviations = relevant_abbreviations or {}

    def _sql_escape(value):
        return str(value).replace("'", "''")

    abbreviation_templates = []
    for i, (desc, abbr) in enumerate(relevant_abbreviations.items(), start=1):
        if i > 8:
            break
        desc_text = str(desc or "").strip().lower()
        abbr_text = str(abbr or "").strip().upper()
        if not desc_text or not abbr_text:
            continue
        desc_sql = _sql_escape(desc_text)
        abbr_sql = _sql_escape(abbr_text)
        abbreviation_templates.append(
            (
                f"- {desc_text} / {abbr_text}:\n"
                f"  (LOWER(COALESCE(\"Brief Material Description\", '')) LIKE '%{desc_sql}%' "
                f"OR LOWER(COALESCE(\"Material_Description\", '')) LIKE '%{desc_sql}%' "
                f"OR UPPER(COALESCE(\"Brief Material Description\", '')) LIKE '% {abbr_sql} %' "
                f"OR UPPER(COALESCE(\"Material_Description\", '')) LIKE '% {abbr_sql} %')"
            )
        )
    if abbreviation_templates:
        abbreviation_sql_examples = "\n".join(abbreviation_templates)
    else:
        abbreviation_sql_examples = "- (No abbreviation templates for this query.)"

    table_columns = []
    for col_name, col_type in full_schema_by_table.get(table_name, []):
        table_columns.append(f"{table_name}.\"{col_name}\" ({col_type})")
    if not table_columns:
        table_columns = [f"{table_name}.<no columns loaded>"]

    return f'''
        You are NIFDatabaseAgent. Convert user questions into one SQLite query
        against table "{table_name}" and answer strictly from query results.

        Scope:
        - Only handle questions answerable from this NIF database.
        - For out-of-scope questions, respond:
          "I can only help with questions about the NIF database."

        LATENCY MODE (MANDATORY):
        - Do not greet.
        - For in-scope database questions, first action must be exactly one call
          to 'query_nif_db_2'.
        - Do not ask clarifying questions before first query unless impossible to
          map to schema.
        - Never SELECT *; select only required columns.
        - For list/detail outputs (non-aggregate), include the PDF link column
          in results when present in schema. In this database the column is
          typically "Link". Do not force this for pure count/aggregate queries.
        - If LIMIT is needed, use LIMIT {NIF_DB_MAX_ROWS} by default unless user
          explicitly asks for fewer rows.
        - Superlative intent rule: if user asks for "most", "top", "highest",
          "lowest", "least", "bottom", "maximum", "minimum", "biggest", or "smallest",
          you MUST use ORDER BY on the relevant metric and apply LIMIT:
          - use DESC for most/top/highest/maximum/biggest
          - use ASC for least/lowest/bottom/minimum/smallest
          - use LIMIT 1 for singular asks (e.g., "what LIM has the most approved NIFs")
          - use LIMIT N for "top N" or "bottom N" asks.
        - If no rows, do one broader rewrite attempt only; then return
          "no matching records found".
        - Final user answer: max 5 lines, no SQL, no internal reasoning, no
          repeated rows, and no fabricated values.
        - Do not claim display limits (for example, "only first 10 rows")
          unless the tool output explicitly says results were truncated.

        Schema context:
        - Core columns (name, type): {core_columns}
        - Full database schema (all tables/columns): {full_schema_by_table}
        - Active table columns (authoritative): {table_columns}
        - Status_Name values: {status_values}
        - Status-like columns and sample values: {status_column_samples}
        - Country abbreviations: {country_abbreviations}
        - Relevant abbreviations for this query only: {relevant_abbreviations}

        Column-resolution policy (MANDATORY):
        - Use only columns listed in the active table columns above.
        - Do not invent new column names.
        - If user wording does not exactly match a column, choose the closest
          existing column by token similarity/synonym intent.
        - Example: if user asks "PDF links" and there is no exact "PDF Link",
          map to the most similar existing PDF-related column in schema.
        - Before returning SQL, verify every quoted column name exists in schema.
        - For status-related intent (status/state/stage/material complete/etc.),
          search across ALL status-like columns using OR unless user explicitly
          pins one column:
          LOWER(COALESCE("Status", '')) LIKE '%<term>%'
          OR LOWER(COALESCE("Status_Name", '')) LIKE '%<term>%'
          OR LOWER(COALESCE("Detailed Status", '')) LIKE '%<term>%'
        - Example: "status material complete" should match "Status" values like
          "LIM Report-Material Complete" even if "Status_Name" is only
          Approved/Running/etc.

        SQL rules:
        - Wrap column names in double quotes.
        - Text match guidance:
          - For text comparisons in WHERE, use wildcard contains search:
            LIKE '%value%'.
          - For case-insensitive search, use LOWER(COALESCE(<col>, '')) LIKE '%value%'.
          - For text search in descriptions, always check both:
            "Brief Material Description" and "Material_Description".
          - For person-name filters, do NOT require exact full-string matching.
            Split the input full name into tokens and match each token
            independently using lowercase token contains matching with LIKE,
            so order can vary (first last, last first, last, first).
            Example:
            LOWER(COALESCE("Created_By", '')) LIKE '%marie%'
            AND LOWER(COALESCE("Created_By", '')) LIKE '%smith%'

        - Abbreviation guidance:
          - For abbreviation predicates, use UPPER() and token-space pattern only:
            UPPER(COALESCE("Material_Description", '')) LIKE '% RKT %'
          - If a query term maps to an abbreviation, you MUST include BOTH:
            1) full-text term match using LOWER(... LIKE '%term%')
            2) abbreviation token match using UPPER(... LIKE '% ABBR %')
            Use them together in the same OR group.
          - Never use abbreviation-only matching when a mapped full-text term is
            available.

        - Date comparison guidance:
          - Reference date for relative comparisons: 2026-03-02
          - Temporal policy: use half-open intervals [start, end) to avoid overlap.
          - Interpret "last/next month|quarter|year|week" as complete periods.
          - Interpret "past/future N units" as rolling windows relative to the
            reference date.
          - SQLite date filter form:
            date(<date_col>) >= date('YYYY-MM-DD')
            AND date(<date_col>) < date('YYYY-MM-DD')
          - For quarter/month/year grouping use strftime('%Y', ...),
            strftime('%m', ...), and month arithmetic.
          - If the question has no clear date expression, avoid assuming a
            date filter.
          - Support date range filters for past/future, multiple
            months/quarters/years, and numeric spans (e.g., last 2 years,
            next 2 quarters).
          - Temporal columns (5, as provided):
            NIFS.Created, NIFS.Created_By, NIFS.First_Ship_Date,
            NIFS.MF_Approval_Start_Date, NIFS.Modified.
          - IMPORTANT: NIFS.Created_By is a person-name field for tokenized text
            matching, not date math.

        - Arithmetic and function guidance:
          - Arithmetic operators allowed: +, -, *, /.
          - Arithmetic on table columns must use numeric columns only.
          - HAVING and WHERE may compare arithmetic expressions if source columns
            follow numeric/date rules.
          - Do not invent derived expressions when required source columns are
            missing.
          - If a requested expression cannot be mapped confidently to schema
            columns, return empty SQL with low confidence.
          - Allowed SQLite functions only:
            ABS, AVG, CAST, COALESCE, COUNT, DATE, DATETIME, JULIANDAY, LOWER,
            MAX, MIN, NULLIF, ROUND, STRFTIME, SUM, TIME, UPPER.
          - Allowed date-shift units: day, week, month, quarter, year.
          - Quarter shift = 3 months.
          - SQLite date-shift forms:
            - Calculated column:
              date(<date_col>, '+N day|month|year')
              week => '+(7*N) day', quarter => '+(3*N) month'
            - WHERE/HAVING compare:
              date(<date_col>, '+N month') >= date('YYYY-MM-DD')
            - Date grouping:
              strftime('%Y', <date_col>), strftime('%m', <date_col>)
          - Numeric columns (13, as provided):
            NIFS.CAT_End, NIFS.GCF_End, NIFS.GCF_Start, NIFS.LIM_Launch_Date,
            NIFS.MAT_GRP_1, NIFS.MFLC_End, NIFS.MFLC_Start, NIFS.MF_Nbr_Returns,
            NIFS.Material_Number, NIFS.PROD_HIER, NIFS.PR_PT_CA, NIFS.RDQ_End,
            NIFS.index.

        - For grouped "who has the most/least/lowest/bottom" questions:
          GROUP BY the entity column, ORDER BY aggregate with direction based on intent,
          then LIMIT 1 (or N).
          Example (most):
          SELECT "LIM", COUNT(*) AS cnt
          FROM "NIFS"
          WHERE LOWER("Status_Name") LIKE '%approved%'
          GROUP BY "LIM"
          ORDER BY cnt DESC
          LIMIT 1
          Example (least/bottom):
          SELECT "LIM", COUNT(*) AS cnt
          FROM "NIFS"
          WHERE LOWER("Status_Name") LIKE '%approved%'
          GROUP BY "LIM"
          ORDER BY cnt ASC
          LIMIT 1
        - If user asks for multiple entity dimensions in one question (for example:
          "LIM or creator", "LIM and creator", "by LIM and creator"), return both
          aggregates independently in the same response.
          - "creator" maps to "Created_By".
          - Preferred SQL pattern: compute separate top/bottom aggregates for each
            entity and combine with UNION ALL.
          Example:
          WITH lim_top AS (
            SELECT
              'LIM' AS "Entity_Type",
              "LIM" AS "Entity_Value",
              COUNT(*) AS cnt
            FROM "NIFS"
            WHERE LOWER(COALESCE("Status_Name", '')) LIKE '%approved%'
            GROUP BY "LIM"
            ORDER BY cnt DESC
            LIMIT 1
          ),
          creator_top AS (
            SELECT
              'Creator' AS "Entity_Type",
              "Created_By" AS "Entity_Value",
              COUNT(*) AS cnt
            FROM "NIFS"
            WHERE LOWER(COALESCE("Status_Name", '')) LIKE '%approved%'
            GROUP BY "Created_By"
            ORDER BY cnt DESC
            LIMIT 1
          )
          SELECT * FROM lim_top
          UNION ALL
          SELECT * FROM creator_top
        - For person names in "Created_By", try both orders:
          LOWER("Created_By") IN (LOWER('Marie Smith'), LOWER('Smith, Marie'))
        - For empty checks use both NULL and empty string:
          "Package UPC" IS NOT NULL AND "Package UPC" != ''
        - For user-self questions, use "Created_By" with current logged-in user:
          {current_username}

        Abbreviation SQL templates for this query (copy/edit directly):
        {abbreviation_sql_examples}

        {sql_mode_override}
    '''


def refresh_nif_database_task_prompt(session_task, current_username, user_query):
    """
    Rebuild compact SQL-agent prompt with dynamic abbreviation subset per query.
    """
    prompt_context = getattr(session_task, "_nif_prompt_context", None)
    if not isinstance(prompt_context, dict):
        return

    relevant_abbreviations = get_relevant_db_abbreviations(
        user_query,
        max_items=NIF_DB_PROMPT_MAX_ABBREVIATIONS,
    )

    compact_prompt = build_nif_database_system_message(
        table_name=prompt_context.get("table_name", "NIFS"),
        core_columns=prompt_context.get("core_columns", []),
        full_schema_by_table=prompt_context.get("full_schema_by_table", {}),
        status_values=prompt_context.get("status_values", []),
        status_column_samples=prompt_context.get("status_column_samples", {}),
        country_abbreviations=prompt_context.get("country_abbreviations", {}),
        current_username=current_username,
        relevant_abbreviations=relevant_abbreviations,
        sql_mode_override=prompt_context.get("sql_mode_override", ""),
    )

    session_task.system_message = compact_prompt
    if getattr(session_task, "agent", None) is not None:
        session_task.agent.system_message = compact_prompt


def create_nif_database_task(
        CURRENT_USERNAME:str='Unknown'              # The name of the current user
        ,TOOL:object=query_nif_db_tool_2      # A Langroid lr.agent.ToolMessage object.
    ):
    # Claude 4 also makes up answers
    # nif_database_agent = lr.ChatAgent(agent_config_claude4)

    # 3.5 Haiku doesn't actually answer the question
    # nif_database_agent = lr.ChatAgent(agent_config_claude35)

    # 3.5 Sonnet seems to be making up numbers
    # nif_database_agent = lr.ChatAgent(agent_config_claude35_sonnet)
    
    # GPT-OSS is pretty good on Bedrock; switch to OpenAI config when provider=openai
    nif_database_agent = lr.ChatAgent(get_nif_database_agent_config())
    
    nif_database_agent.enable_message(TOOL)
    
    # Using just the main table
    table_name = 'NIFS'
    full_schema_by_table = _load_nif_database_schema_snapshot(nif_database)
    column_list = utils.run_query(nif_database, f"SELECT * FROM pragma_table_info('{table_name}');")
    column_list_cln = [(info[1], info[2]) for info in column_list]      # Keep column names and types
    core_columns = _select_nif_core_columns(column_list_cln)
    
    status_name_distinct_values = utils.run_query(nif_database, f"select distinct Status_Name from NIFS")
    status_values = _normalize_status_values(status_name_distinct_values)
    status_column_samples = _load_status_column_samples(nif_database, table_name)
    
    country_abbreviations = {
        "United States":"US"
        ,"Canada":"CA"
        ,"Mexico":"MX"
    }

    if NIF_DB_FORCE_FIRST_PASS_SQL:
        sql_mode_override = '''
            # EXECUTION MODE OVERRIDE (FIRST-PASS SQL)

            Ignore any prior instruction to begin with a greeting or ask clarification
            before querying.

            For user inputs that could reasonably map to the NIF database, your FIRST
            action must be to call 'query_nif_db_2' with exactly one best-effort
            SELECT/WITH query.

            Rules for first-pass SQL:
            - Do not ask follow-up questions before the first query.
            - Use one query only.
            - Keep results bounded. If you include LIMIT, use LIMIT {NIF_DB_MAX_ROWS}
              unless the user explicitly requests a smaller number of rows.
            - If user wording is ambiguous, make a reasonable assumption, run the query,
              and then state the assumption in your response.
        '''
    else:
        sql_mode_override = ''

    system_message = build_nif_database_system_message(
        table_name=table_name,
        core_columns=core_columns,
        full_schema_by_table=full_schema_by_table,
        status_values=status_values,
        status_column_samples=status_column_samples,
        country_abbreviations=country_abbreviations,
        current_username=CURRENT_USERNAME,
        relevant_abbreviations={},
        sql_mode_override=sql_mode_override,
    )

    nif_database_task = lr.Task(
        nif_database_agent
        ,name='NIFDatabaseAgent'
        ,system_message=system_message
        # For use in Dash, setting interactive=False so the task exits after each round.
        # This is necessary to get a response to print in Dash.
        ,interactive=False
    
        # Setting restart=False so that message history persists when task exits.
        ,restart=False
    )
    nif_database_task._nif_prompt_context = {
        "table_name": table_name,
        "core_columns": core_columns,
        "full_schema_by_table": full_schema_by_table,
        "status_values": status_values,
        "status_column_samples": status_column_samples,
        "country_abbreviations": country_abbreviations,
        "sql_mode_override": sql_mode_override,
    }
    return nif_database_task
            
nif_database_task = create_nif_database_task()

'''
test_question = 'How many NIFs have been submitted?'
test_question = 'Find the project description in the NIF database that has Material_Number 2410-012-054'
test_question = 'What is the material number for protein poptarts'
test_question = 'What is the material number, create date, and title for the most recent rice krispies NIF?'
test_question = 'What is the detailed status of the NIF with Material_Number 2410012054?'

nif_database_task.run('hello')
nif_database_task.run(test_question)

print(nif_database_agent.message_history_str())                # Concise message history as a single string

nif_database_agent.last_message_with_role(Role.ASSISTANT)

# Can I clone it? Yes.
# BUT the clone doesn't behave the same way!!
nif_database_task_clone = nif_database_task.clone(1)
nif_database_task_clone.run(test_question)
'''

#%% DOCUMENT RETRIEVAL AGENT
'''
'''
# =============================================================================
#### Functions and tools
# =============================================================================
# Multimodal retrieval by interpreting images
# Note this requires a vectorstore that returns paths to page images
#!!! Add minimum relevance (distance)
class retrieve_and_answer_tool(lr.agent.ToolMessage):
    # request: the name of this function for reference in system messages
    request:str = "retrieve_and_answer"

    # purpose: a description of what this function does. A good description is important so the LLM knows how to use it.
    purpose:str = "Query a vectorstore to retrieve relevant documents. Return an answer and the list of documents used."

    # Any other variables defined here before the handle() method are treated as required arguments
    QUERY:str   # Plain text query

    def handle(self):
        vectorstore_provider = utils.get_app_llm_provider()
        embedding_model = utils.get_cached_retrieval_embedding_function(
            provider=vectorstore_provider
        )

        # Get relevant documents (paths to page images)
        try:
            retrieved_docs_all_collections = utils.query_vectorstore(
                FOLDER_PATH=utils.VECTORSTORE_FOLDER
                ,QUERY=self.QUERY    # Plain text query. Will be embedded with EMBEDDING_MODEL before submitting to vectorstore.
                ,N_RESULTS=DOCSEARCH_RESULTS_PER_COLLECTION
                ,EMBEDDING_MODEL=embedding_model
                ,USE_CACHE=True
            )
        except Exception as err:
            return (
                "I couldn't access the training-resource index. "
                "Please ensure the local vectorstore is built and populated, then try again.\n\n"
                f"Details: {err}"
            )

        selected_hits = utils.select_vectorstore_hits(
            retrieved_docs_all_collections,
            max_total_results=DOCSEARCH_MAX_TOTAL_PAGES,
            max_distance=DOCSEARCH_MAX_DISTANCE,
        )

        if len(selected_hits) < DOCSEARCH_MIN_HITS:
            return (
                "I could not find enough relevant training-resource pages for that question.\n\n"
                "Try broader terms (for example: `NIF training deck`, `BOM training`, "
                "`material master`, `new hire guide`) and submit again."
            )

        # Parse retrieved docs
        retrieved_page_images = []      # Initialize
        retrieved_page_links = []       # Initialize

        for hit in selected_hits:
            ret_image = str(hit.get("document", "") or "").strip()
            if not ret_image:
                continue
            image_file_without_path = os.path.basename(ret_image)
            image_file_new_path = os.path.join(ASSETS_PAGE_IMAGES_FOLDER, image_file_without_path)
            if not os.path.exists(image_file_new_path):
                if os.path.exists(ret_image):
                    image_file_new_path = ret_image
                else:
                    continue
            retrieved_page_images.append(image_file_new_path)

            metadata = hit.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}
            doc_name = str(metadata.get("document_name") or image_file_without_path)
            page_num = str(metadata.get("page_number") or "?")
            encoded_doc_name = urllib.parse.quote(doc_name)
            link_to_page = f"{base_path_docs}/{encoded_doc_name}#page={page_num}"

            distance = hit.get("distance")
            if isinstance(distance, (float, int)):
                link_label = f"{doc_name}, p{page_num} (score={distance:.4f})"
            else:
                link_label = f"{doc_name}, p{page_num}"
            link_as_markdown = f"[{link_label}]({link_to_page})"
            retrieved_page_links.append(link_as_markdown)

        if len(retrieved_page_images) == 0:
            return (
                "I could not find relevant training-resource pages for that question.\n\n"
                "Try broader terms (for example: `NIF training deck`, `BOM training`, "
                "`material master`, `new hire guide`) and submit again."
            )

        formatted_sources_list = formatted_list(retrieved_page_links)

        # Prepare the prompt for the image query.
        if DOCSEARCH_STRICT_GROUNDING:
            grounding_rules = '''
            Grounding rules (strict):
            - Use only information visible in the provided pages.
            - Do not use outside knowledge or assumptions.
            - If the pages are insufficient, unclear, or conflicting, reply exactly:
              "I don't have enough evidence in the retrieved training pages to answer that confidently."
            '''
        else:
            grounding_rules = '''
            If the pages are insufficient, say you could not find enough evidence.
            Do not make up details.
            '''

        image_query_prompt = f'''
            You are answering a user question using images of retrieved training-document pages.

            {grounding_rules}

            Response requirements:
            - Keep answer concise and factual.
            - Do NOT include source citations, document names, or page numbers.
            - Prefer direct wording from the page content when possible.
        '''
        try:
            answer_from_images = utils.query_multiple_images_by_provider(
                IMAGE_LIST=retrieved_page_images,
                SYSTEM_PROMPT=image_query_prompt,
                USER_QUESTION=self.QUERY,
                provider=vectorstore_provider,
            )
        except Exception as err:
            if vectorstore_provider == "openai":
                return (
                    "I found relevant training-resource pages, but I couldn't run the OpenAI vision step.\n\n"
                    "Check APP_LLM_PROVIDER=openai, OPENAI_API_KEY, OPENAI_BASE_URL, "
                    "and OPENAI_VISION_MODEL/APP_LLM_MODEL in .env.\n\n"
                    f"Details: {err}\n\nSources used:\n{formatted_sources_list}"
                )
            return (
                "I found relevant training-resource pages, but I couldn't run the Bedrock vision step.\n\n"
                "Check APP_LLM_PROVIDER=bedrock and either IAM auth or "
                "BEDROCK_AUTH_MODE=api_key with AWS_BEARER_TOKEN_BEDROCK. "
                "Also verify region/model access in .env.\n\n"
                f"Details: {err}\n\nSources used:\n{formatted_sources_list}"
            )

        # Generate the final Markdown string including answer and sources
        final_output_string = answer_from_images
        final_output_string += "\n\nSources used:\n"
        final_output_string += formatted_sources_list

        return final_output_string

# Kristen's version
# class retrieve_and_answer_tool(lr.agent.ToolMessage):
#     # request: the name of this function for reference in system messages
#     request = "retrieve_and_answer"

#     # purpose: a description of what this function does. A good description is important so the LLM knows how to use it.
#     purpose = "Query a vectorstore to retrieve relevant documents. Return an answer and the list of documents used."

#     # Any other variables defined here before the handle() method are treated as required arguments
#     QUERY:str   # Plain text query

#     def handle(self):
#         # Get relevant documents (paths to page images)
#         retrieved_docs_all_collections = utils.query_vectorstore(
#             FOLDER_PATH=utils.VECTORSTORE_FOLDER
#             ,QUERY=self.QUERY    # Plain text query. Will be embedded with EMBEDDING_MODEL before submitting to vectorstore.
#             ,N_RESULTS=2
#         )
#         # Parse retrieved docs
#         retrieved_page_images = []

#         # Ensure unique document names are extracted and used for citation display
#         unique_docs_for_citation = {} # {display_name: web_url}

#         for i, CLCT in enumerate(retrieved_docs_all_collections['documents']):
#             for j, DOC_PATH in enumerate(retrieved_docs_all_collections['documents'][i]):
#                 doc_name = retrieved_docs_all_collections['metadatas'][i][j]['document_name']

#                 filename = os.path.basename(DOC_PATH)
#                 web_url = f"/assets/raw_docs/{urllib.parse.quote(filename)}" # Updated for subfolder

#                 retrieved_page_images.append(DOC_PATH)

#                 if doc_name not in unique_docs_for_citation:
#                     unique_docs_for_citation[doc_name] = web_url

#         # Prepare the prompt for the image query.
#         image_query_prompt = f'''
#             You will be given images of pages from documents. Use them to answer the user's question.

#             If the images do not contain information relevant to the user's question, say so;
#             do not make up an answer.

#             Provide a concise answer based on the images. Do NOT include any source citations,
#             document names, or page numbers in your answer. Just the factual answer.
#         '''
#         answer_from_images = utils.query_multiple_images_azureoai(retrieved_page_images, image_query_prompt, self.QUERY)

#         # Generate the final Markdown string including answer and sources
#         final_output_string = answer_from_images
#         final_output_string += "\n\nSources used:\n"

#         formatted_sources_list = []
#         for doc_name, web_url in unique_docs_for_citation.items():
#             original_filename_from_url = urllib.parse.unquote(os.path.basename(web_url))

#             # Get the full HTML tag
#             html_link = get_html_link_new_tab(original_filename_from_url, doc_name)
#             formatted_sources_list.append(html_link)

#         final_output_string += "\n".join(formatted_sources_list)

#         return final_output_string

# =============================================================================
#### Config
# =============================================================================
def create_nif_docsearch_task(
        CURRENT_USERNAME:str='Unknown'              # The name of the current user
        ,TOOL:object=retrieve_and_answer_tool      # A Langroid lr.agent.ToolMessage object.
    ):
    nif_docsearch_agent = lr.ChatAgent(get_docsearch_agent_config())
    # nif_docsearch_agent.enable_message(RecipientTool)
    nif_docsearch_agent.enable_message(TOOL)
    
    nif_docsearch_task = lr.Task(
        nif_docsearch_agent
        ,name='DocRetrievalAgent'
        ,system_message=f'''
            You are a helpful assistant with access to a set of documents in a
            vector store.
    
            {llm_instruction_scope_of_discussion}

            When you receive a question, pass it to the 'retrieve_and_answer'
            function. This function will return a single string containing
            the answer to the user's question followed by a list of relevant
            documents formatted as Markdown links.

            Never add facts that are not in the tool output. If evidence is
            insufficient, return the tool's abstention message as-is.
        
            If the 'retrieve_and_answer' function does not return anything, say
            "I apologize, I cannot find any relevant results in the documents."
        '''
        ,interactive=False
    )
    
    return nif_docsearch_task

'''
nif_docsearch_task = create_nif_docsearch_task()

nif_docsearch_task.run('What is a LIM?')
'''
#%% BRANDS DATABASE QUERY AGENT
'''
UPDATE: not sure we'll be including the Brands database (SAP Material Master)
but if we do, will probably give the query_brands_db_tool to the NIF Database
agent.
'''
# brands_database_agent_name = 'BrandsDatabaseAgent'

# brands_database_agent = lr.ChatAgent(agent_config_claude35)
# brands_database_agent.enable_message(RecipientTool)
# brands_database_agent.enable_message(query_brands_db_tool)

# # We want this bot to use just the main table
# table_touse = 'Export'

# column_list = utils.run_query(brands_database, f"SELECT * FROM pragma_table_info('{table_touse}');")
# column_list_cln = [(info[1], info[2]) for info in column_list]      # Keep column names and types

# brands_database_task = lr.Task(
#     brands_database_agent
#     ,name=brands_database_agent_name
#     ,system_message=f'''
#         You are an agent specialized in formulating SQLite queries based on
#         plain language questions.

#         You have access to a SQLite database with information on active brands.
#         The database contains a table called '{table_touse}' with one row
#         per material number. It contains the following columns, shown as
#         ('column_name', 'column_type'): {column_list_cln}.

#         When you receive a user question, construct a query using SQLite syntax
#         and submit it using the 'query_brands_db' function. Interpret the result
#         and reply with a concise answer to the user's question.

#         If the 'query_brands_db' function does not return anything, say '{lrc.NO_ANSWER}'.

#         Use the '{RecipientTool.name()}' tool with 'intended_recipient':'{receptionist_name}'
#         and 'content' being your answer.

#         # GUIDELINES

#         - When filtering on a column of type TEXT, construct the query to be
#         case-insensitive.

#         - When searching for a person's name, always use %LIKE% to capture
#         spelling variations. Also, try reversing first and last names and including
#         a comma such as 'Marie Smith' and 'Smith, Marie'.

#         - When searching for a material description, use a %LIKE% operator to
#         capture similar entries. Also search for abbreviations for common words
#         using this lookup: {db_abbreviations_dict}.

#         - Always first check how many records exist for a given query. If a record
#         exists but the requested field is empty, let the user know.
#     '''
#     #     Here are some notes about important columns:
#     ,interactive=False
# )

#%% 4. LAYOUT

# project metadata has path, project_id, uploaded_files (a list of file names), and settings (a dict of setting values)
FADashChatbot = dash.Dash(__name__,
    )

#### APP LAYOUT
app.layout = dbc.Container(
    fluid=True, children=[

    #### Define dcc.Stores
    dcc.Store(id='user_session_id'),
    # dcc.Store (id='user_session_chat'),   # May not be necessary - langroid task tracks this
    dcc.Store(id='nif_progress_data_json'),
    dcc.Store(id='active_task_name'),       # Can only store strings in dcc.Store, so these are names rather than task objects
    dcc.Store(id='nif_query_result_store'),
    dcc.Store(id='nif_llm_prompt_store'),
    dcc.Download(id='download-nif-data'),

    # Interval component pings to keep connection alive
    dcc.Interval(
        id='keepalive-interval',
        interval=60*1000,  # Ping every 60 seconds
        n_intervals=0
    ),
    html.Div(id='hidden-div'),

    #### BRANDING & HEADING
    dbc.Row([
        # Kellanova Branding
        dbc.Col(
            html.Div([
                html.A(href="https://www.kellanova.com/us/en/home.html",
                       target='_blank',
                       children=[
                           html.Img(id = 'kellanova-img',
                                    title="Link to Kellanova site",
                                    src=kellanova_img,
                                    style={'height': "60px"}
                                    )
                           ]),
                html.H4([
                        html.Span("NIFTY", className="gilroy-heavy"),
                        " - Your New Item Form Assistant"
                    ],
                    style=nifty_heading_text_style,
                    id='nifty-heading-text'
                    ),
                ], style={'margin-left':"10px",
                          'margin-right':"10px",
                          'margin-top':"10px"},
                )
            ),
            dbc.Col([
            html.Div(id='user-info'),
            dcc.Store(id='user-store'),
            dcc.Interval(
                id='load-user-interval',
                interval=1,        # 1 millisecond
                max_intervals=1,   # Run only once
                n_intervals=0      # Initial value
            )
        ]),
        ### END OF ROW
        ],
        style={'background-color': '#8401FF',
               'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.1)',},
        id='kellanova-branding-heading'
        ),
        ### END OF BRANDING & HEADING

    html.Br(),

    #### SAMPLE QUESTIONS CONTAINER
    dbc.Container([
        dbc.Row([
            dbc.Col(
                html.Div([
                        # Header Row with Branding and Sample Question Intro
                        html.Div(
                            style={
                                "display": "flex",
                                "justify-content": "space-between",
                                "align-items": "center",
                                "width": "100%",
                            },
                            children=[
                                # Left side: "Select a sample question..." text
                                # html.P("Select a sample question below or ask your own question to begin a chat session",
                                html.P("Click a button to begin a chat session",
                                       className="mb-0",
                                       style=HEADING_STYLE,
                                       id='sample-quesitons-heading'
                                ),
                                # Right side: Demand Chain AI Branding
                                html.Div(
                                    style={
                                        "display": "flex",
                                    },
                                    children=[
                                        html.H5("Built and Powered by",
                                                style={
                                                    "padding": "0",
                                                    "margin-bottom": "0rem",
                                                    "margin-right": "2px",
                                                    "color": "#0F2548",
                                                    "font-size": "x-small",
                                                    "font-style": "italic",
                                                }
                                        ),
                                        html.A(href="https://www.demandchainai.com/",
                                               target='_blank',
                                               children=[
                                                   html.Img(title="Link to Demand Chain AI site",
                                                            src='/assets/DCAI-horizontal-darkblue-1024x154.png',
                                                            style={
                                                                'height': "20px",
                                                            }
                                                   )
                                               ]
                                        ),
                                    ]
                                ),
                            ]
                        ),
                        # --- END: Header Row ---

                        # Load NIF in progress dialog box
                        dbc.Modal([
                            dbc.ModalHeader(dbc.ModalTitle("Select in progress NIF")),
                            dbc.ModalBody([
                                html.P("Please select which NIF you would like to load."),
                                dcc.Dropdown(
                                    id='file-dropdown',
                                    placeholder='Select a NIF to load',
                                    style={'marginBottom': '15px', 'width': '100%'}
                                ),
                           ]),
                            dbc.ModalFooter([
                                # The 'Yes' button will trigger the file selection
                                dbc.Button(
                                    "Submit",
                                    id="load-nif-submit-button",
                                    className="ms-2",
                                    style=BUTTON_STYLE,
                                    n_clicks=0,
                                    ),
                                # The 'No' button just closes the modal (by setting 'is_open' to False)
                                dbc.Button(
                                    "Cancel",
                                    id="load-nif-cancel-button",
                                    className="ms-auto",
                                    color="danger",

                                    n_clicks=0,
                                    ),
                                ]),
                            ],
                            id="load-nif-modal",
                            is_open=False, # Starts hidden
                            ),

                        # Radio buttons
                        html.Div(id='select-demo-questions-style-div',
                                 className='purple-radio-scheme',
                                 children=[
                                     dbc.RadioItems(
                                         id='select-demo-questions',
                                         options=demo_questions,
                                         inline=True,
                                         inputClassName="custom-radio-input",
                                         labelClassName="custom-radio-label",
                                         className="custom-radio-group",
                                     ),
                                 ]),
                        ], className="p-3"),
                className="rounded custom-container-style",
            )
        ], justify="center"),
    ],
    fluid=True,
    ),

    html.Br(),

    #### SIMPLE MESSAGES
    html.Div([
        html.P("",
               style={
                    'fontSize': '24px',
                    # 'fontWeight': 'bold',
                    'fontStyle': 'italic',
                    'textAlign': 'center',
                    },
               id='simple_message',
               ),
        ],
        ),

    #### AI RESPONSE CONTAINER
    # Text Area with Nifty Image
    dbc.Container([
        dbc.Row(
            dbc.Col([
                html.Div([
                    html.P([
                            html.Span("NIFTY's", className="gilroy-heavy"),
                            " Response:",
                        ],
                        style=HEADING_STYLE,
                        id='ai-response-heading'
                        ),
                    ],
                    id="bot_output_label",
                    style={"margin-left": "2rem",},
                    ),
                dbc.Row([
                    dbc.Col(
                        # Nifty Image
                        html.Img(
                            id='nifty-img',
                            title="Hi, I'm Nifty!",
                            src='/assets/Rice_Krispy-removebg.png',
                            style={'height': "70px",
                                   'filter': 'drop-shadow(0 6px 12px rgba(132, 1, 255, 0.4))'
                                   }
                            ),
                        width="auto",
                        align="start",
                        className="d-flex align-items-start"
                        ),
                    dbc.Col(
                        # Output text areas
                        html.Div([
                            html.P(id="results", style={'display': 'none',}),

                            # Use this to print instructions without activating the bot
                            html.P(id="results-plaintext", children='', style={}),

                            dbc.Spinner(children=[
                                dcc.Markdown(id="results-markdown",),
                            ], size="md", color="#000000", fullscreen=False),   # End of Spinner
                            html.Div(
                                id="nif-query-output-container",
                                style={"display": "none", "marginTop": "12px"},
                                children=[
                                    html.Div(
                                        style={
                                            "display": "flex",
                                            "justifyContent": "space-between",
                                            "alignItems": "center",
                                            "marginBottom": "6px",
                                            "gap": "8px",
                                        },
                                        children=[
                                            html.P(
                                                "NIFDatabaseAgent Query Output",
                                                style={
                                                    "fontWeight": "600",
                                                    "marginBottom": "0",
                                                    "color": "#0F2548",
                                                },
                                            ),
                                            dbc.Button(
                                                "Show LLM Prompt",
                                                id="show-nif-llm-prompt-button",
                                                n_clicks=0,
                                                disabled=True,
                                                size="sm",
                                                color="secondary",
                                                style={"fontSize": "12px"},
                                            ),
                                        ],
                                    ),
                                    html.P(
                                        id="nif-query-summary",
                                        style={
                                            "fontSize": "12px",
                                            "marginBottom": "8px",
                                            "color": "#444",
                                        },
                                    ),
                                    dash_table.DataTable(
                                        id="nif-query-table",
                                        columns=[],
                                        data=[],
                                        page_action="none",
                                        virtualization=True,
                                        sort_action="native",
                                        filter_action="native",
                                        style_table={
                                            "width": "100%",
                                            "minHeight": "220px",
                                            "height": "220px",
                                            "overflowX": "auto",
                                            "maxHeight": "380px",
                                            "overflowY": "auto",
                                            "border": "1px solid #ddd",
                                        },
                                        style_header={
                                            "backgroundColor": "#F5F7FA",
                                            "fontWeight": "700",
                                            "whiteSpace": "normal",
                                            "height": "auto",
                                        },
                                        style_cell={
                                            "textAlign": "left",
                                            "fontSize": "12px",
                                            "padding": "6px",
                                            "minWidth": "100px",
                                            "maxWidth": "360px",
                                            "whiteSpace": "normal",
                                            "height": "auto",
                                        },
                                    ),
                                ],
                            ),
                            dbc.Modal(
                                [
                                    dbc.ModalHeader(
                                        dbc.ModalTitle("Prompt Sent to NIFDatabaseAgent LLM")
                                    ),
                                    dbc.ModalBody(
                                        html.Pre(
                                            id="nif-llm-prompt-modal-body",
                                            style={
                                                "whiteSpace": "pre-wrap",
                                                "fontFamily": "monospace",
                                                "fontSize": "12px",
                                                "marginBottom": "0",
                                            },
                                        ),
                                        style={"maxHeight": "70vh", "overflowY": "auto"},
                                    ),
                                    dbc.ModalFooter(
                                        dbc.Button(
                                            "Close",
                                            id="nif-llm-prompt-modal-close-button",
                                            className="ms-auto",
                                            n_clicks=0,
                                        )
                                    ),
                                ],
                                id="nif-llm-prompt-modal",
                                is_open=False,
                                size="xl",
                                scrollable=True,
                            ),
                            ],
                            className="p-2",
                            ),
                        width=True,
                        className="ms-3"
                        ),
                    ],
                    align="start",
                    className="g-0"
                    ),
                    ],
                    className="rounded custom-container-style",
                ),
                justify="center",
            ),
        ],
        fluid=True,
        id='bot_output_container',
        style={'display': 'none'},      # Hidden on initial load
    ),

    html.Br(),

    #### HUMAN TEXT AREA
    dbc.Container([
        dbc.Row(
            dbc.Col(
                html.Div([
                    html.P([
                            # "Enter your question for ",
                            # html.Span("NIFTY", className="gilroy-heavy"),
                            # " below",
                            html.Span("USER", className="gilroy-heavy"),
                            " input",
                        ],
                        style=HEADING_STYLE,
                        id='human-text-heading'
                        ),
                    dbc.Row([
                        dbc.Col(
                            dbc.Textarea(id="human-chat-text-area",
                                         className="mb-3 mt-3 p-3",
                                         placeholder="Enter your question related to any field on the NIF or about the New Item Form in general",
                                         size="sm",
                                         ),
                            width=11
                        ),
                        dbc.Col(
                            html.Div([
                                html.Div(id="feedback-dummy-output", style={'display': 'none'}),
                                dbc.Alert(
                                    "✅ Thank you! Your chat history has been saved for review.",
                                    id="feedback-confirmation-alert",
                                    is_open=False,
                                    duration=4000,
                                    color="success",
                                    className="mt-2",
                                ),
                                dbc.Tooltip(
                                    "Provide Feedback",
                                    target="thumbs-down-button",
                                    placement="top",
                                ),
                                dbc.Button(
                                    html.I(className="fas fa-thumbs-down"),
                                    id="thumbs-down-button",
                                    className="feedback-button",
                                    n_clicks=0,
                                ),
                            ],
                            className="d-flex flex-column justify-content-center align-items-center",
                            style={"height": "100%"}
                            ),
                            width=1,
                            className="d-flex align-items-center justify-content-center"
                        )
                    ], className="g-2"),

                    dbc.Row([
                        dbc.Col(
                            html.Div(
                                [
                                    dbc.Button("Submit",
                                               id="submit-button",
                                               className="mb-1 human-chat-buttons",
                                               style=BUTTON_STYLE,
                                              ),
                                    dbc.Button("Show History",
                                               id="hist-collapse-button",
                                               className="mb-1 human-chat-buttons",
                                               style=BUTTON_STYLE,
                                               n_clicks=0,
                                              ),
                                    dbc.Button("Clear History",
                                               id="hist-clear-button",
                                               className="mb-1 human-chat-buttons",
                                               style=BUTTON_STYLE,
                                               n_clicks=0,
                                              ),
                                    # Clear chat history warning dialog box
                                    dbc.Modal([
                                        dbc.ModalHeader(dbc.ModalTitle("Confirm History Clear")),
                                        dbc.ModalBody(
                                            "Would you like to remove all chat history associated with this user and all saved NIF files? "
                                            "⚠️ WARNING - This action cannot be undone."
                                            ),
                                        dbc.ModalFooter([
                                            # The 'No' button just closes the modal (by setting 'is_open' to False)
                                            dbc.Button(
                                                "No, Cancel",
                                                id="history-cancel-button",
                                                className="ms-auto",
                                                style=BUTTON_STYLE,
                                                n_clicks=0,
                                                ),
                                            # The 'Yes' button will trigger the history clearing logic
                                            dbc.Button(
                                                "Yes, Clear History",
                                                id="history-confirm-button",
                                                color="danger",
                                                className="ms-2",
                                                n_clicks=0,
                                                ),
                                            ]),
                                        ],
                                        id="history-confirm-modal",
                                        is_open=False, # Starts hidden
                                        ),
                                ],
                                className="d-flex justify-content-end flex-wrap button-group-container"
                            ),
                            width=12
                        ),

                        # Additional Guidance chat buttons
                        dbc.Col(
                            html.Div(
                                [
                                    html.Label("Name this NIF:"),
                                    dcc.Input(
                                        id='save-filename',
                                        type='text',
                                        placeholder='Enter name for this NIF in progress',
                                        value=f'My In-progress NIF',
                                        style={'width': '300px', 'marginRight': '10px', 'marginLeft': '10px', 'marginBottom': '10px'}
                                    ),
                                    dbc.Button("Show progress",
                                               id="nif-progress-button",
                                               className="mb-1 human-chat-buttons",
                                               style=BUTTON_STYLE),
                                    dbc.Button("Save progress",
                                               id="nif-save-button",
                                               className="mb-1 human-chat-buttons",
                                               style=BUTTON_STYLE
                                               ),
                                    dbc.Button("Download file",
                                               id="nif-export-button",
                                               className="mb-1 human-chat-buttons",
                                               style=BUTTON_STYLE
                                               ),
                                    dbc.Button("Reload NIF Rules",
                                               id="nif-reload-config-button",
                                               className="mb-1 human-chat-buttons",
                                               style=BUTTON_STYLE
                                               ),
                                    # SHOW PROGRESS confirmation popup
                                    dbc.Modal([
                                        dbc.ModalHeader(
                                            dbc.ModalTitle("NIF progress:"),
                                            id="show-nif-progress-modal-header",
                                            ),
                                        dbc.ModalBody(
                                            "Test",
                                            id="show-nif-progress-modal-body",
                                            ),
                                        ],
                                        id="show-nif-progress-modal",
                                        is_open=False, # Starts hidden
                                        ),
                                    # SAVE PROGRESS confirmation popup
                                    dbc.Modal([
                                        dbc.ModalHeader(
                                            dbc.ModalTitle("NIF progress saved."),
                                            id="save-nif-progress-modal-header",
                                            ),
                                        ],
                                        id="save-nif-progress-modal",
                                        is_open=False, # Starts hidden
                                        ),
                                ],
                                # className="d-flex flex-wrap button-group-container",
                                id="nif-specific-buttons-container",
                                style={'display': 'none'}
                            ),
                            width={"size": "auto"},
                        ), # END OF ADDITIONAL GUIDANCE CHAT BUTTONS
                        ],
                        justify="beginning",
                    )
                    ]),
                className="rounded custom-container-style",
                ),
            justify="center",
        ),
    ],
    fluid=True,
    id='user_input_container',
    style={'display': 'none'},      # Hidden on initial load
    ),

    # html.Br(),

    # dbc.Col(
    #        html.Div([
    #            # Chat history amount toggle switch
    #            daq.ToggleSwitch(id="chat-history-amount-toggle",
    #                             label=['Current', 'Past 30 days'],
    #                             value=False,
    #                             ),
    #        ],
    #            style={
    #                'margin-left': "10px",
    #                'margin-right': "10px",
    #                'margin-top': "20px",
    #                "gap": "10px"
    #                }
    #        ),
    # width={"size": "auto", "offset": 0},
    # style={"display": "flex", "justify-content": "flex-end"},
    # ),

    # Chat History Amount
    dbc.Col(
        html.Div([
            # Chat history amount toggle switch
            daq.ToggleSwitch(id="chat-history-amount-toggle",
                             label=['Current', 'Past 30 days'],
                             value=False,
                             color="#B567FF",
                             ),
        ],
        style={
            'margin-left': "10px",
            'margin-right': "10px",
            'margin-top': "20px",
            "gap": "10px"
        }),
        width={"size": "auto", "offset": 0},
        id="toggle-switch-container",
        style={'display': 'none'}
    ),

    #### CHAT HISTORY CONTAINER
    dbc.Container([
        dbc.Row(
            dbc.Col(
                html.Div([
                    dbc.Collapse(
                        dbc.Spinner(children=[
                            dcc.Markdown(id="hist-content"),
                        ], size="md", color="#000000", fullscreen=False),   # End of Spinner
                        id="hist-collapse",
                        is_open=False,
                        ),
                    ]),
                className="rounded border",
                style={
                    "border-color": "#CCCCCC",

                    },
                ),
            justify="center",),
    ],
    fluid=True, style={'padding-bottom': '120px'}
    ),

    #### LEGAL LANGUAGE
    html.Div([
        html.H6(
            legal_language,
            # "All content copyright ©2025 Demand Chain AI Inc. All rights reserved. No reproduction, transmission or display is permitted without the written permission of Demand Chain AI Inc.",
            style={
                "color": "#000000",
                "font-size": "0.75rem",
                "text-align": "center",
                "margin-bottom": "0.5rem"
            }
        ),
        html.A(
            "Terms of Use Policy",
            href="https://www.demandchainai.com/demandchain-home-page/dcai-terms-of-use-policy/",
            target="_blank",
            style={
                "font-size": "0.75rem",
                "display": "block",
                "text-align": "center",
            }
        ),
    ],
    className="mt-auto p-3",
    style={
        "background-color": "#f8f9fa", # Light background for the footer
        "width": "100%",
        "border-top": "1px solid #e9ecef",
        "bottom": "0",
        "position": "fixed",

    }
    ),

    ### END OF APP
    ])


#%% 5. CALLBACKS

# Keepalive pings
@app.callback(
    Output('hidden-div', 'children'),  # Use a hidden div
    Input('keepalive-interval', 'n_intervals')
)
def keepalive(n):
    return ''  # Just trigger to keep connection alive


@app.callback(
    Output('simple_message', 'children', allow_duplicate=True),
    Input("nif-reload-config-button", "n_clicks"),
    State('active_task_name', 'data'),
    prevent_initial_call=True,
)
def reload_nif_config_from_ui(n_clicks, active_task_name):
    if n_clicks is None or n_clicks == 0:
        raise dash.exceptions.PreventUpdate

    try:
        return build_reload_nif_message(active_task_name)
    except Exception as err:
        return (
            "Failed to reload NIF rules at runtime. "
            f"Details: {err}"
        )


@app.callback(
    # 1. Output for the radio button container children
    Output('select-demo-questions-style-div', 'children'),
    # 2. Output for the radio button value (clearing it)
    Output('select-demo-questions', 'value'),
    # Output('select-demo-questions', 'options'),
    # 3. Output for the NIF button visibility
    Output('nif-specific-buttons-container', 'style'),
    # 4. Generate a unique session ID
    Output('user_session_id', 'data'),
    # 5. Show or hide the input and output boxes
    Output('user_input_container', 'style'),
    Output('bot_output_container', 'style'),

    Input('select-demo-questions', 'value'),
    State('user-store', 'data'),
)
def initialize_and_switch_buttons(selected_value, user_data):
    hide_buttons_style = {'display': 'none'}
    show_buttons_style = {'display': 'flex', 'margin-left': 'auto'}

    # Set defaults
    original_demo_questions = [
        dbc.RadioItems(
            id='select-demo-questions',
            options=demo_questions,
            inline=True,
            inputClassName="custom-radio-input",
            labelClassName="custom-radio-label",
            className="custom-radio-group",
        ),
    ]

    # Get user info from SSO
    if not user_data:   # When running on local or if SSO is not functioning
        active_user_name = 'User_no_sso'
        active_user_email = 'User_no_sso@email.com'
    else:
        active_user_name = user_data.get('name', 'User')
        active_user_email = user_data.get('email', 'user@email.com')

    # ----------------------------------------------------
    # Case 0: Initial Load (value is None)
    # ----------------------------------------------------
    if selected_value is None:
        # Get unique session ID
        sid = generate_session_id()

        # Execute cleanup at inital load
        cleanup_old_history_files(days_threshold=30)

        return (
            original_demo_questions,    # Show home screen buttons
            no_update,                  # Don't change selected question
            hide_buttons_style,         # Hide step by step guide buttons
            sid,                        # Return session ID
            hide_buttons_style,         # Hide user input box
            hide_buttons_style,         # Hide bot output box
        )

    # ----------------------------------------------------
    # Case 1: User selects the trigger question (Switch to NIF Menu)
    # ----------------------------------------------------
    if selected_value == GUIDANCE_QUESTION:
        # Construct user-specific folder path
        user_nif_progress_dir = get_user_nif_progress_dir(active_user_email)
        os.makedirs(user_nif_progress_dir, exist_ok=True)

        # Update file list
        files = get_available_files(user_nif_progress_dir)
        file_list = []  # Initialize
        for f in files:
            f_name, f_ext = f.rsplit('.', 1)
            file_list.append({'label': f_name, 'value': f})

        if not file_list:
            file_list = [NO_USER_NIFS_MESSAGE]

        nif_menu_children=[
            dbc.RadioItems(
                id='select-demo-questions',
                options=NIF_MENU_OPTIONS,
                inline=False,
                inputClassName="custom-radio-input",
                labelClassName="custom-radio-label",
                className="custom-radio-group",
            ),
            # dcc.Dropdown(
            #     id='file-dropdown',
            #     options=file_list,
            #     placeholder='Select a file to load',
            #     style={'width': '300px', 'display': 'inline-block', 'marginRight': '10px', 'marginLeft': '30px'}
            # ),
        ]

        # Action: Switch UI, Clear Value (None), Show NIF buttons
        return (
            nif_menu_children,      # Show NIF step by step buttons on top
            None,                   # Set selected question to None
            show_buttons_style,     # Show NIF step by step buttons below
            no_update,              # Don't change session ID
            hide_buttons_style,     # Hide user input box
            hide_buttons_style,     # Hide bot output box
        )

    # ----------------------------------------------------
    # Case 2: User selects "Back to landing page" (Switch to Original Menu)
    # ----------------------------------------------------
    elif selected_value == 'BACK_TO_LANDING':
        # Action: Switch UI, Clear Value (None), Hide NIF buttons
        return (
            original_demo_questions,    # Show home screen buttons
            None,                       # Set selected question to None
            hide_buttons_style,         # Hide step by step guide buttons
            no_update,                  # Don't change session ID
            hide_buttons_style,         # Hide user input box
            hide_buttons_style,         # Hide bot output box
        )

    # ----------------------------------------------------
    # Case 3: In NIF Menu, selected LOAD/NEW NIF
    # ----------------------------------------------------
    elif selected_value in ['LOAD_NIF', 'NEW_NIF_CHAT']:
        # Action: Do NOT change UI/Value (no_update), but confirm buttons stay VISIBLE
        return (
            no_update,              # Don't change NIF step by step buttons above
            no_update,              # Don't change selected question
            show_buttons_style,     # Show NIF step by step buttons below
            no_update,              # Don't change session ID
            None,                   # Reset user input box style (show)
            None,                   # Reset bot output box style (show)
        )
    elif selected_value in ['LOAD_NIF']:
        # Action: Do NOT change UI/Value (no_update), but confirm buttons stay VISIBLE
        return (
            no_update,              # Don't change NIF step by step buttons above
            no_update,              # Don't change selected question
            show_buttons_style,     # Show NIF step by step buttons below
            no_update,              # Don't change session ID
            None,                   # Reset user input box style (show)
            None,                   # Reset bot output box style (show)
        )

    # ----------------------------------------------------
    # Case 4: Other modules that are active
    # ----------------------------------------------------
    elif selected_value in ['Search NIF', 'Get started on training resources']:
        return (
            no_update,              # Don't change NIF step by step buttons above
            no_update,              # Don't change selected question
            hide_buttons_style,     # Hide step by step guide buttons
            no_update,              # Don't change session ID
            None,                   # Reset user input box style (show)
            None,                   # Reset bot output box style (show)
        )

    # ----------------------------------------------------
    # Case 5: Load NIF file
    # ----------------------------------------------------
    elif selected_value == RESET_NIF_SELECTION:
        return (
            no_update,              # Don't change NIF step by step buttons above
            None,                   # Reset selected question to None (Unselect 'LOAD_NIF')
            show_buttons_style,     # Hide step by step guide buttons
            no_update,              # Don't change session ID
            None,                   # Reset user input box style (show)
            None,                   # Reset bot output box style (show)
        )

    # ----------------------------------------------------
    # Other modules are inactive
    # ----------------------------------------------------
    return (
        no_update,              # Don't change NIF step by step buttons above
        no_update,              # Don't change selected question
        hide_buttons_style,     # Hide step by step guide buttons
        no_update,              # Don't change session ID
        hide_buttons_style,     # Hide user input box
        hide_buttons_style,     # Hide bot output box
    )

# Toggle load nif dialog box
@app.callback(
    Output("load-nif-modal", "is_open"),
    Output('select-demo-questions', 'value', allow_duplicate=True),

    Input('select-demo-questions', 'value'),
    Input("load-nif-cancel-button", "n_clicks"),
    State("load-nif-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_load_nif_dialog_box(selected_demo_questions, n_cancel, is_open):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # OPEN Logic
    if trigger_id == 'select-demo-questions' and selected_demo_questions == 'LOAD_NIF' and not is_open:
        # OPEN: returns True for modal, no_update for radio
        return True, dash.no_update

    # CLOSE Logic (Cancel Button)
    elif trigger_id == "load-nif-cancel-button" and is_open:
        # CLOSE: returns False for modal, NIF_MENU_OPTIONS to trigger menu reset
        return False, NIF_MENU_OPTIONS

    # If the trigger was the modal itself closing (X/Escape), we need to ensure the value is reset
    if trigger_id == "load-nif-modal" and not is_open:
        return False, NIF_MENU_OPTIONS

    raise dash.exceptions.PreventUpdate

@app.callback(
    # Output: Set the radio button value
    Output('select-demo-questions', 'value', allow_duplicate=True),

    # Input: The modal's open state changing
    Input("load-nif-modal", "is_open"),

    # State: Read the current value of the radio button
    State('select-demo-questions', 'value'),

    prevent_initial_call=True
)

# Logic for unclicking LOAD_NIF button upon exit of modal
def reset_on_x_or_escape(is_open, current_radio_value):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if not is_open and trigger_id == 'load-nif-modal' and current_radio_value == 'LOAD_NIF':
        print("DEBUG: Modal closed via X or Escape. Resetting radio value to NIF_MENU_OPTIONS.")
        return NIF_MENU_OPTIONS

    raise dash.exceptions.PreventUpdate

def _nif_backend_state_key(session_id: str, user_email: str) -> tuple:
    return ("nif_backend_save", str(user_email or ""), str(session_id or ""))


def _extract_nif_last_progress_markers(nif_progress_df: Optional[pd.DataFrame]) -> tuple[str, str]:
    if not isinstance(nif_progress_df, pd.DataFrame) or nif_progress_df.empty:
        return "", ""
    try:
        last_qid = str(
            nif_progress_df.get("_agentref_last_question_answered", pd.Series([""])).iloc[0]
        ).strip()
    except Exception:
        last_qid = ""
    try:
        last_answer = str(
            nif_progress_df.get("_agentref_last_answer_given", pd.Series([""])).iloc[0]
        ).strip()
    except Exception:
        last_answer = ""
    return last_qid, last_answer


def reset_nif_backend_save_state(session_id: str, user_email: str = "") -> None:
    if user_email:
        key = _nif_backend_state_key(session_id, user_email)
        nif_backend_save_state.pop(key, None)
        return

    sid_text = str(session_id or "")
    keys_to_remove = [k for k in list(nif_backend_save_state.keys()) if len(k) >= 3 and k[2] == sid_text]
    for key in keys_to_remove:
        nif_backend_save_state.pop(key, None)


def clear_nif_backend_user_state(user_email: str) -> None:
    email_text = str(user_email or "")
    keys_to_remove = [
        k for k in list(nif_backend_save_state.keys()) if len(k) >= 3 and k[1] == email_text
    ]
    for key in keys_to_remove:
        nif_backend_save_state.pop(key, None)


def maybe_autosave_nif_progress(
    user_data,
    session_id: str,
    user_nif_progress_df: pd.DataFrame,
    prior_last_question_id: str = "",
    prior_last_answer: str = "",
    force_save: bool = False,
) -> dict:
    if not isinstance(user_nif_progress_df, pd.DataFrame) or user_nif_progress_df.empty:
        return {"saved": False, "reason": "empty_progress"}

    if NIF_BACKEND_SAVE_EVERY_STEPS <= 0:
        return {"saved": False, "reason": "autosave_disabled"}

    _active_user_name, active_user_email = _resolve_active_user_identity(user_data)
    state_key = _nif_backend_state_key(session_id, active_user_email)
    state = nif_backend_save_state.get(state_key, {})

    current_qid, current_answer = _extract_nif_last_progress_markers(user_nif_progress_df)

    previous_qid = str(state.get("last_question_id", "") or "").strip()
    previous_answer = str(state.get("last_answer", "") or "").strip()
    if not previous_qid and prior_last_question_id:
        previous_qid = str(prior_last_question_id).strip()
    if not previous_answer and prior_last_answer:
        previous_answer = str(prior_last_answer).strip()

    current_qid_normalized = current_qid.upper()
    valid_current_qid = (
        bool(current_qid_normalized)
        and current_qid_normalized not in {"<NOT YET DETERMINED>", "NAN", "NONE", "START REQ INITIATE"}
    )
    progressed_to_new_question = bool(valid_current_qid and current_qid != previous_qid)

    answered_step_count = int(state.get("answered_step_count", 0) or 0)
    if progressed_to_new_question:
        answered_step_count += 1

    next_state = {
        "answered_step_count": answered_step_count,
        "last_question_id": current_qid,
        "last_answer": current_answer,
    }
    nif_backend_save_state[state_key] = next_state

    should_save = force_save or (
        progressed_to_new_question
        and answered_step_count > 0
        and (answered_step_count % NIF_BACKEND_SAVE_EVERY_STEPS == 0)
    )
    if not should_save:
        return {
            "saved": False,
            "reason": "not_due",
            "answered_step_count": answered_step_count,
            "interval": NIF_BACKEND_SAVE_EVERY_STEPS,
        }

    user_nif_progress_dir = get_user_nif_progress_dir(active_user_email)
    os.makedirs(user_nif_progress_dir, exist_ok=True)
    autosave_filename = f"_autosave_{str(session_id or 'session')}.pkl"
    autosave_path = user_nif_progress_dir / autosave_filename

    try:
        user_nif_progress_df.to_pickle(autosave_path)
    except Exception as exc:
        return {
            "saved": False,
            "reason": "save_failed",
            "error": str(exc),
            "answered_step_count": answered_step_count,
        }

    return {
        "saved": True,
        "reason": "interval_reached" if not force_save else "forced",
        "answered_step_count": answered_step_count,
        "interval": NIF_BACKEND_SAVE_EVERY_STEPS,
        "autosave_file": autosave_filename,
    }


def build_nif_resume_submit_text(
    user_nif_progress_df: pd.DataFrame,
    last_question_answered: str,
    last_answer_given: str,
) -> str:
    """
    Build compact resume prompt to avoid sending full table back to the LLM.
    """
    if NIF_RESUME_VERBOSE_CONTEXT:
        return (
            "Resume the user's NIF in progress.\n"
            f"They last answered question ID '{last_question_answered}' with '{last_answer_given}'.\n"
            "Here are all the values for their NIF in progress:\n"
            f"{user_nif_progress_df.to_markdown()}"
        )

    summary_lines = []
    max_fields = NIF_RESUME_SUMMARY_FIELDS
    if max_fields > 0 and isinstance(user_nif_progress_df, pd.DataFrame) and not user_nif_progress_df.empty:
        df = user_nif_progress_df.copy()
        for internal_col in ["_agentref_last_question_answered", "_agentref_last_answer_given"]:
            if internal_col in df.columns:
                df = df.drop(columns=[internal_col])

        row = df.iloc[0]
        for col_name, value in row.items():
            value_str = str(value).strip()
            if not value_str:
                continue
            if value_str in {"<NOT YET DETERMINED>", "nan", "None"}:
                continue
            if len(value_str) > 120:
                value_str = value_str[:117] + "..."
            summary_lines.append(f"- {col_name}: {value_str}")
            if len(summary_lines) >= max_fields:
                break

    summary_block = "\n".join(summary_lines) if summary_lines else "- (No filled NIF field values yet.)"
    return (
        "Resume the user's NIF in progress.\n"
        f"Last answered question ID: {last_question_answered}\n"
        f"Last answer given: {last_answer_given}\n"
        "Use the agent's dataframe state as source of truth.\n"
        "Compact field snapshot:\n"
        f"{summary_block}"
    )


def _resolve_active_user_identity(user_data):
    """
    Normalize user identity from SSO payload or local fallback.
    """
    if not user_data:
        return "User_no_sso", "User_no_sso@email.com"
    return (
        user_data.get("name", "User"),
        user_data.get("email", "user@email.com"),
    )


def _sanitize_nif_filename(filename, default_name="My In-progress NIF"):
    cleaned = re.sub(r"[^A-Za-z0-9 ._-]+", "", str(filename or "")).strip()
    return cleaned or default_name


def _read_nif_progress_df_from_json(user_nif_progress_json):
    raw_json = user_nif_progress_json
    if raw_json is None:
        raise ValueError("No progress data found.")
    if not isinstance(raw_json, str):
        raw_json = str(raw_json)
    if not raw_json.strip():
        raise ValueError("No progress data found.")
    return pd.read_json(StringIO(raw_json), orient="split")


def build_nif_progress_preview_text(user_nif_progress_json):
    try:
        user_nif_progress_df = _read_nif_progress_df_from_json(user_nif_progress_json)
        user_nif_progress_df_display = user_nif_progress_df.drop(
            columns=['_agentref_last_question_answered', '_agentref_last_answer_given'],
            errors="ignore",
        )
        dictionary_todisplay = user_nif_progress_df_display.to_dict(orient='list')
        output_string = ""
        for field_name, value in dictionary_todisplay.items():
            output_string = output_string + f"{field_name}: {value}\n"
        return {
            "ok": True,
            "code": "ok",
            "message": "",
            "progress_text": output_string or "No progress data found.",
        }
    except Exception:
        return {
            "ok": False,
            "code": "no_progress_data",
            "message": "No progress data found.",
            "progress_text": "No progress data found.",
        }


def build_nif_progress_download_frame(user_nif_progress_json):
    user_nif_progress_df = _read_nif_progress_df_from_json(user_nif_progress_json)
    user_nif_progress_df_fordl = user_nif_progress_df.drop(
        columns=['_agentref_last_question_answered', '_agentref_last_answer_given'],
        errors="ignore",
    )
    return user_nif_progress_df_fordl.transpose()


def build_reload_nif_message(active_task_name):
    summary = reload_nif_runtime_configuration()
    message = (
        "NIF rules reloaded successfully. "
        f"Rules: {summary.get('rules_count', 0)}, "
        f"Glossary terms: {summary.get('glossary_count', 0)}, "
        f"Dropdown lists: {summary.get('dropdown_lists', 0)}, "
        f"Legacy sessions refreshed: {summary.get('legacy_tasks_refreshed', 0)}."
    )
    message += (
        " Legacy step flow remains prompt-driven via <STEP_BY_STEP_RULES> "
        "from Expert_System_Rules.xlsx."
    )

    if str(active_task_name or "").strip() == 'nifguide_task':
        message += " Continue chatting to use the updated rules immediately."

    return message


def list_saved_nif_files_for_user(user_data):
    """
    List saved NIF files for a user as [{label, value}, ...].
    """
    _active_user_name, active_user_email = _resolve_active_user_identity(user_data)
    user_nif_progress_dir = get_user_nif_progress_dir(active_user_email)
    os.makedirs(user_nif_progress_dir, exist_ok=True)

    file_options = []
    for filename in get_available_files(user_nif_progress_dir):
        if "." in filename:
            label = filename.rsplit(".", 1)[0]
        else:
            label = filename
        file_options.append({"label": label, "value": filename})
    return file_options


def save_nif_session(user_data, filename, user_nif_progress_json):
    """
    Shared service: save in-progress NIF dataframe to user-specific pickle file.
    """
    _active_user_name, active_user_email = _resolve_active_user_identity(user_data)

    filename_clean = _sanitize_nif_filename(filename, default_name="")
    if not filename_clean:
        return {
            "ok": False,
            "code": "invalid_filename",
            "message": "Please provide a valid file name.",
        }

    try:
        user_nif_progress_df = _read_nif_progress_df_from_json(user_nif_progress_json)
    except Exception:
        return {
            "ok": False,
            "code": "invalid_progress_data",
            "message": "NIF progress data is invalid. Please refresh and try again.",
        }

    user_nif_progress_dir = get_user_nif_progress_dir(active_user_email)
    os.makedirs(user_nif_progress_dir, exist_ok=True)

    try:
        output_filename = f"{filename_clean}.pkl"
        output_path = user_nif_progress_dir / output_filename
        user_nif_progress_df.to_pickle(output_path)
    except Exception as exc:
        return {
            "ok": False,
            "code": "save_failed",
            "message": f"Failed to save NIF progress: {exc}",
        }

    return {
        "ok": True,
        "code": "ok",
        "message": f"Progress saved to {filename_clean}.",
        "saved_filename": output_filename,
        "saved_label": filename_clean,
        "files": list_saved_nif_files_for_user(user_data),
    }


def start_new_nif_session(user_data, active_sid, current_clicks):
    """
    Shared service: initialize a new NIF step-by-step session.
    """
    active_user_name, active_user_email = _resolve_active_user_identity(user_data)
    active_task_name = "nifguide_task"
    display_text = ""
    reset_nif_backend_save_state(active_sid, active_user_email)

    submit_text = "Start a new NIF with field 'LIM'"
    new_clicks = (current_clicks or 0) + 1

    user_nif_progress_df = create_active_user_nif_progress_data()
    requestor_date = f"{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    user_nif_progress_df = update_nif_progress_data(user_nif_progress_df, "START REQ INITIATE", active_user_name, 1001)
    user_nif_progress_df = update_nif_progress_data(user_nif_progress_df, "START REQ INITIATE", active_user_email, 1002)
    user_nif_progress_df = update_nif_progress_data(user_nif_progress_df, "START REQ INITIATE", requestor_date, 1003)
    user_nif_progress_df = update_nif_progress_data(user_nif_progress_df, "START REQ INITIATE", "0.0.0", 1004)
    user_nif_progress_df = update_nif_progress_data(user_nif_progress_df, "START REQ INITIATE", active_user_name, 1005)

    return {
        "ok": True,
        "code": "ok",
        "message": "",
        "session_id": str(active_sid or ""),
        "active_task_name": active_task_name,
        "submit_clicks": new_clicks,
        "human_chat_value": submit_text,
        "nif_progress_data_json": user_nif_progress_df.to_json(orient="split"),
        "simple_message": display_text,
        "auto_submit": True,
    }


def load_saved_nif_session(user_data, active_sid, current_clicks, selected_nif_file):
    """
    Shared service: load a saved NIF file and build resume submit payload.
    """
    _active_user_name, active_user_email = _resolve_active_user_identity(user_data)
    active_task_name = "nifguide_task"

    filename = str(selected_nif_file or "").strip()
    if not filename or filename == NO_USER_NIFS_MESSAGE:
        return {
            "ok": False,
            "code": "no_file_selected",
            "message": "Please select a file from the dropdown to load.",
        }

    user_nif_progress_dir = get_user_nif_progress_dir(active_user_email)
    selected_file_with_path = user_nif_progress_dir / filename
    if not os.path.isfile(selected_file_with_path):
        return {
            "ok": False,
            "code": "file_not_found",
            "message": f"File '{filename}' not found. Please refresh and try again.",
        }

    try:
        user_nif_progress_df = pd.read_pickle(selected_file_with_path)
    except Exception:
        return {
            "ok": False,
            "code": "invalid_pickle",
            "message": f"Could not load '{filename}'. The file is corrupted or invalid.",
        }

    try:
        if "_agentref_last_question_answered" in user_nif_progress_df.columns:
            last_question_answered = str(user_nif_progress_df["_agentref_last_question_answered"].item())
        else:
            last_question_answered = ""
        if "_agentref_last_answer_given" in user_nif_progress_df.columns:
            last_answer_given = str(user_nif_progress_df["_agentref_last_answer_given"].item())
        else:
            last_answer_given = ""
    except Exception:
        last_question_answered = ""
        last_answer_given = ""

    submit_text = build_nif_resume_submit_text(
        user_nif_progress_df=user_nif_progress_df,
        last_question_answered=last_question_answered,
        last_answer_given=last_answer_given,
    )

    reset_nif_backend_save_state(active_sid, active_user_email)

    if "." in filename:
        filename_label = filename.rsplit(".", 1)[0]
    else:
        filename_label = filename

    display_text = (
        f"Prior NIF '{filename_label}' loaded successfully. "
        "Submitting resume request to agent."
    )

    return {
        "ok": True,
        "code": "ok",
        "message": "",
        "session_id": str(active_sid or ""),
        "active_task_name": active_task_name,
        "submit_clicks": (current_clicks or 0) + 1,
        "human_chat_value": submit_text,
        "nif_progress_data_json": user_nif_progress_df.to_json(orient="split"),
        "simple_message": display_text,
        "auto_submit": True,
        "loaded_filename": filename,
    }


# NIF file selection, NIF loading, and closes the modal
@app.callback(
    # Outputs for the main application to update chat/data
    Output('human-chat-text-area', 'value', allow_duplicate=True),
    Output('submit-button', 'n_clicks', allow_duplicate=True),
    Output('nif_progress_data_json', 'data', allow_duplicate=True),
    Output('simple_message', 'children', allow_duplicate=True),

    # Output to close the modal itself
    Output("load-nif-modal", "is_open", allow_duplicate=True),
    Output('select-demo-questions', 'value', allow_duplicate=True),

    Input("load-nif-submit-button", "n_clicks"),

    # States for data needed for the loading logic
    State('file-dropdown', 'value'),
    State('user-store', 'data'),
    State('user_session_id', 'data'),
    State('submit-button', 'n_clicks'),
    State("load-nif-modal", "is_open"),
    prevent_initial_call=True
)
def load_nif_from_modal(n_submit, selected_nif_file, user_data, active_sid, current_clicks, is_open):

    if n_submit is None or n_submit == 0:
        raise dash.exceptions.PreventUpdate

    load_result = load_saved_nif_session(
        user_data=user_data,
        active_sid=active_sid,
        current_clicks=current_clicks,
        selected_nif_file=selected_nif_file,
    )
    if not load_result.get("ok"):
        display_text = f"Error: {load_result.get('message', 'Failed to load saved NIF.')}"
        return no_update, no_update, no_update, display_text, no_update, dash.no_update

    return (
        load_result.get("human_chat_value"),
        load_result.get("submit_clicks"),
        load_result.get("nif_progress_data_json"),
        load_result.get("simple_message"),
        False,
        RESET_NIF_SELECTION,
    )

# Dynamically load file options into the modal's dropdown
@app.callback(
    Output('file-dropdown', 'options'),
    Input("load-nif-modal", "is_open"),
    State('user-store', 'data'),
    prevent_initial_call=True
)
def populate_file_dropdown(is_open, user_data):
    if not is_open:
        raise dash.exceptions.PreventUpdate # Only run when modal opens

    file_list = list_saved_nif_files_for_user(user_data)
    if file_list:
        return file_list

    return [{'label': "No saved NIFs found.", 'value': 'NO_USER_NIFS_MESSAGE', 'disabled': True}]

# # Use display_text to give the user instructions
# @app.callback(
#     Output('results-plaintext', 'children'),
#     Input('select-demo-questions', 'value'),
#     prevent_initial_call=True
# )
# def update_instructions(selected_question):
#     if selected_question == GUIDANCE_QUESTION:
#         display_text = "NIF Step by Step: Please click a button above to start a new NIF chat or load a NIF from a prior chat."
#         return display_text

#     display_text = 'TEST'
#     return display_text

# Update human text area and trigger submit
@app.callback(
    Output('human-chat-text-area', 'value', allow_duplicate=True),
    Output('submit-button', 'n_clicks', allow_duplicate=True),
    Output('nif_progress_data_json', 'data', allow_duplicate=True),
    Output('active_task_name', 'data'),
    Output('simple_message', 'children', allow_duplicate=True),

    Input('select-demo-questions', 'value'),
    State('submit-button', 'n_clicks'),
    State('user-store', 'data'),
    State('user_session_id', 'data'),
    State('file-dropdown', 'value'),

    prevent_initial_call=True
)
def update_textarea_and_trigger_submit_chat(selected_question, current_clicks, user_data, active_sid, selected_nif_file):
    # Default empty dataframe
    user_nif_progress_json = pd.DataFrame(index=[0]).to_json(orient='split')

    # Default text
    display_text = ''

    # Default task
    active_task_name = 'nifguide_task'

    # Get user info from SSO
    if not user_data:   # When running on local or if SSO is not functioning
        active_user_name = 'User_no_sso'
        active_user_email = 'User_no_sso@email.com'
    else:
        active_user_name = user_data.get('name', 'User')
        active_user_email = user_data.get('email', 'user@email.com')

    if selected_question == GUIDANCE_QUESTION:
        if NIF_CHAT_ENGINE == "legacy" and NIF_GUIDE_LEGACY_SOURCE == "qa":
            display_text = "Continuing conversation with NIF Guide agent"
        else:
            display_text = "NIF Step by Step: Please click a button above to start a new NIF chat or load a NIF from a prior chat."
        return (
            no_update,      # Human chat area
            no_update,      # Submit button
            no_update,      # NIF progress data
            no_update,      # Active task name
            display_text    # Simple message
        )

    if selected_question == 'NEW_NIF_CHAT':
        start_result = start_new_nif_session(
            user_data=user_data,
            active_sid=active_sid,
            current_clicks=current_clicks,
        )
        if NIF_CHAT_ENGINE == "legacy" and NIF_GUIDE_LEGACY_SOURCE == "qa":
            start_result["simple_message"] = "Continuing conversation with NIF Guide agent"
        return (
            start_result.get("human_chat_value"),
            start_result.get("submit_clicks"),
            start_result.get("nif_progress_data_json"),
            start_result.get("active_task_name"),
            start_result.get("simple_message"),
        )

    if selected_question == 'LOAD_NIF':
        active_task_name = 'nifguide_task'
        # All outputs must be no_update except the one you intentionally change (active_task_name)
        return (
            no_update,       # Human chat area
            no_update,       # Submit button
            no_update,       # NIF progress data
            active_task_name,# Active task name
            no_update,       # Simple message
        )

        # # Construct user-specific folder path
        # # This must match pattern used in save_nif_in_progress
        # # The source file is the current history file
        # user_nif_progress_dir = get_user_nif_progress_dir(active_user_email)
        # selected_file_with_path = user_nif_progress_dir / f"{selected_nif_file}"

        # if os.path.isfile(selected_file_with_path):
        #     # Write display text
        #     f_name, f_ext = selected_nif_file.rsplit('.', 1)
        #     # display_text = f"Prior NIF '{f_name}' loaded"
        #     display_text = ''

        #     # Read file
        #     user_nif_progress_df = pd.read_pickle(selected_file_with_path)

        #     # Write to JSON for dcc.Store
        #     user_nif_progress_json = user_nif_progress_df.to_json(orient='split')

        #     # Submit to LLM
        #     last_question_answered = user_nif_progress_df['_agentref_last_question_answered'].item()
        #     last_answer_given = user_nif_progress_df['_agentref_last_answer_given'].item()

        #     new_clicks = (current_clicks or 0) + 1
        #     submit_text = f'''
        #         Resume the user's NIF in progress.
        #         They last answered question ID '{last_question_answered}' with '{last_answer_given}'.
        #         Here are all the values for their NIF in progress:
        #             {user_nif_progress_df.to_markdown()}
        #     '''

        #     return (
        #         submit_text,      # Human chat area
        #         new_clicks,      # Submit button
        #         user_nif_progress_json,      # NIF progress data
        #         active_task_name,      # Active task name
        #         display_text,    # Simple message
        #     )
        # else:
        #     display_text = 'Please select a file.'
        #     return (
        #         no_update,      # Human chat area
        #         no_update,      # Submit button
        #         no_update,      # NIF progress data
        #         active_task_name,      # Active task name
        #         display_text,    # Simple message
        #     )

    if selected_question == 'NIF field question':
        active_task_name = 'nifguide_task'
        display_text = "NIF Field module is not yet available."
        return (
            no_update,      # Human chat area
            no_update,      # Submit button
            no_update,      # NIF progress data
            active_task_name,      # Active task name
            display_text,    # Simple message
        )

    # Search NIF deactivated
    # if selected_question == 'Search NIF':
    #     active_task_name = 'nif_database_task'
    #     display_text = "NIF Search module is not yet available."
    #     submit_text = "Hello!"

    #     # Update n_clicks for submit button
    #     new_clicks = (current_clicks or 0) + 1

    #     return (
    #         no_update,          # Human chat area
    #         no_update,          # Submit button
    #         no_update,          # NIF progress data
    #         no_update,          # Active task name
    #         display_text,       # Simple message
    #     )

    # Search NIF activated
    if selected_question == 'Search NIF':
        active_task_name = 'nif_database_task'
        display_text = "Search NIF module is ready. Enter your question and click Submit."

        return (
            no_update,          # Human chat area
            no_update,          # Submit button
            no_update,          # NIF progress data
            active_task_name,   # Active task name
            display_text,       # Simple message
        )

    if selected_question == 'Get started on training resources':
        active_task_name = 'nif_docsearch_task'
        display_text = ''
        submit_text = "What training resources are available for NIF and what are the key topics they cover?"
        new_clicks = (current_clicks or 0) + 1

        # Display base set of reference links
        '''
        Favorites documents from meeting notes:
        UPDATE: see email from Bev 11/4
            Full NIF Training Deck v4
            BOM Training Material
            A file from Jamie (Tamara capturing)
            Material Master PowerBI Report
            New Hire Guide
            - This contains links about how to get access.
            RX documentation
        '''
        return (
            submit_text,    # Human chat area
            new_clicks,     # Submit button
            no_update,      # NIF progress data
            active_task_name,      # Active task name
            display_text,    # Simple message
        )

    # If selected question is not handled above, return defaults
    return (
        no_update,      # Human chat area
        no_update,      # Submit button
        no_update,      # NIF progress data
        active_task_name,      # Active task name
        display_text,    # Simple message
    )

# Chat bot with inputs
@app.callback(
    Output("results-markdown", "children", allow_duplicate=True),
    Output('nif_progress_data_json', 'data', allow_duplicate=True),
    Output("human-chat-text-area", "value", allow_duplicate=True),
    Output("nif_query_result_store", "data", allow_duplicate=True),
    Output("nif_llm_prompt_store", "data", allow_duplicate=True),

    # State("socketio", "socketId"),
    Input("submit-button", "n_clicks"),
    State("human-chat-text-area", "value"),
    State('user-store', 'data'),
    State('user_session_id', 'data'),
    State('nif_progress_data_json', 'data'),
    State('active_task_name', 'data'),

    prevent_initial_call=True,
    )
# def chat_bot(socket_id, n_sub, human_chat_value):
def chat_bot(n_sub, human_chat_value, user_data, sid, user_nif_progress_json, active_task_name):
    # global global_socket_id

    # pr.logit(f'chat_bot: {n_sub=}  {socket_id=}  {type(socket_id)} {human_chat_value=} ')
    pr.logit(f'chat_bot: {n_sub=} {human_chat_value=} ')

    # Get user info from SSO
    if not user_data:   # When running on local or if SSO is not functioning
        active_user_name = 'User_no_sso'
        active_user_email = 'User_no_sso@email.com'
    else:
        active_user_name = user_data.get('name', 'User')
        active_user_email = user_data.get('email', 'user@email.com')

    session_task = None
    session_agent = None

    # Get or create user-specific task based on active task
    try:
        if active_task_name == 'nifguide_task':
            # Read NIF progress data
            user_nif_progress_df = pd.read_json(user_nif_progress_json, orient='split')
            session_task = get_session_task('nifguide_task', sid, active_user_name)
            # Update user task to use user_nif_progress_df
            session_task.agent.set_dataframe(user_nif_progress_df)

        elif active_task_name == 'nif_database_task':
            session_task = get_session_task('nif_database_task', sid, active_user_name)

        elif active_task_name == 'nif_docsearch_task':
            # Retrieval module runs tool directly in callback to avoid an extra
            # orchestration LLM hop that can fail before retrieval executes.
            session_task = None

        else:
            return (
                "No active module selected. Please pick a starter question first.",
                no_update,
                no_update,
                no_update,
                None,
            )
    except Exception as err:
        return (
            "I couldn't initialize the selected module. "
            "Please verify credentials and vectorstore setup, then try again.\n\n"
            f"Details: {err}"
        ), no_update, no_update, no_update, None

    if session_task is not None:
        session_agent = session_task.agent

    # if socket_id == None:
    #     if global_socket_id == None:
    #         pr.logit(msg:='ERROR in chat_bot callback.  No socket_id present in callback or in global_socket_id')
    #         return msg
    #     else:
    #         pr.logit('Warning.  chat_bot callback missing socket_id. Using global_socket_id')
    #         socket_id = global_socket_id
    # else:
    #     pr.logit(f'Setting global_socket_id to {socket_id}')
    #     global_socket_id = socket_id

    # Submitting question/system text updates
    # Dash callbacks provide ctx.triggered_id. API calls invoke this function
    # directly, so default to submit-button when callback context is absent.
    try:
        triggered_id = ctx.triggered_id
    except Exception:
        triggered_id = "submit-button"

    if triggered_id == "submit-button":
        nif_query_result_data = None
        nif_llm_prompt_data = None
        expected_nifguide_qid = ""
        prior_nif_last_qid = ""
        prior_nif_last_answer = ""

        if active_task_name == 'nifguide_task':
            prior_nif_last_qid, prior_nif_last_answer = _extract_nif_last_progress_markers(
                user_nif_progress_df
            )

        if active_task_name == 'nif_docsearch_task':
            try:
                full_response = retrieve_and_answer_tool(QUERY=human_chat_value).handle()
            except Exception as err:
                full_response = (
                    "I couldn't run training-resource retrieval.\n\n"
                    "Please verify vectorstore and model credentials, then try again.\n\n"
                    f"Details: {err}"
                )

            if not full_response or not str(full_response).strip():
                full_response = (
                    "I couldn't find relevant results in the training-resource index. "
                    "Please try a broader query."
                )

            full_response = str(full_response).replace('DONE.', '').replace('DONE', '')

            if extra_output_bool:
                full_response = f"<DocRetrievalAgent>         {full_response}          (Session ID: {sid})"

            if not extra_output_bool:
                full_response = remove_tool_calls(full_response)

            return full_response, no_update, '', None, None

        # Did turns=1 break user nif progress df update? YES!!
        # session_task.run(human_chat_value, session_id=sid, turns=1)    # Turns=1 ensures the agent doesn't get into a loop
        # session_task.run(human_chat_value, session_id=sid, turns=10)    # Turns=10 ensures the agents can complete their back and forth

        use_qa_legacy_nifguide = (
            active_task_name == 'nifguide_task'
            and NIF_CHAT_ENGINE == "legacy"
            and NIF_GUIDE_LEGACY_SOURCE == "qa"
        )

        if active_task_name == 'nifguide_task' and not use_qa_legacy_nifguide:
            try:
                refresh_nifguide_task_prompt(
                    session_task=session_task,
                    current_username=active_user_name,
                    user_query=human_chat_value,
                    nif_progress_df=user_nif_progress_df,
                )
                expected_nifguide_qid = infer_expected_nif_question_id(
                    nif_progress_df=user_nif_progress_df,
                    user_query=human_chat_value,
                )
            except Exception as prompt_err:
                print(f"Warning: Failed to refresh NIF guide prompt: {prompt_err}")

        elif active_task_name == 'nif_database_task':
            global last_nif_sql_query, last_nif_query_result
            last_nif_sql_query = None
            last_nif_query_result = None
            nif_llm_prompt_data = build_nif_llm_prompt_payload(
                session_task=session_task,
                user_prompt=human_chat_value,
                session_id=sid,
            )
            try:
                refresh_nif_database_task_prompt(
                    session_task=session_task,
                    current_username=active_user_name,
                    user_query=human_chat_value,
                )
            except Exception as prompt_err:
                print(f"Warning: Failed to refresh NIF database prompt: {prompt_err}")

        try:
            if active_task_name == 'nifguide_task':
                if use_qa_legacy_nifguide:
                    # QA legacy behavior: single run call for NIF guide.
                    session_task.run(human_chat_value, session_id=sid)
                else:
                    session_task.run(
                        human_chat_value,
                        session_id=sid,
                        turns=NIF_GUIDE_TURNS_PER_SUBMIT,
                    )
            elif active_task_name == 'nif_database_task' and NIF_DB_FORCE_FIRST_PASS_SQL:
                session_task.run(
                    human_chat_value,
                    session_id=sid,
                    turns=NIF_DB_FIRST_PASS_TURNS,
                )
            else:
                session_task.run(human_chat_value, session_id=sid)
        except Exception as err:
            if active_task_name == 'nif_database_task':
                failure_hint = (
                    "For Search NIF, this usually means model credentials/provider "
                    "config is invalid."
                )
            elif active_task_name == 'nif_docsearch_task':
                failure_hint = (
                    "For training resources, this usually means Bedrock/OpenAI "
                    "credentials, model access, or endpoint configuration is invalid."
                )
            else:
                failure_hint = (
                    "This usually means model credentials, provider selection, or "
                    "endpoint configuration is invalid."
                )
            error_message = (
                "I couldn't complete your request due to a model/connectivity error.\n\n"
                f"{failure_hint}\n\n"
                f"Details: {err}"
            )
            if active_task_name == 'nifguide_task':
                user_nif_progress_json = user_nif_progress_df.to_json(orient='split')
                return error_message, user_nif_progress_json, '', None, None
            return error_message, no_update, '', None, nif_llm_prompt_data

        last_assistant_message = session_agent.last_message_with_role(Role.ASSISTANT)
        function_args = None

        # Extract assistant output safely across plain responses and tool-call envelopes.
        # SQL tool calls often do not have a "content" argument, so fall back to message content.
        if last_assistant_message is None:
            full_response = "I couldn't generate a response. Please try again."
        else:
            full_response = last_assistant_message.content
            function_call = getattr(last_assistant_message, "function_call", None)
            function_args_raw = getattr(function_call, "arguments", None)
            function_args = parse_function_arguments(function_args_raw)

            if active_task_name == 'nif_database_task':
                content_from_args = None
                sql_from_args = None
                if isinstance(function_args, dict):
                    content_from_args = function_args.get('content')
                    sql_from_args = function_args.get("SQL_QUERY")

                # 1) Prefer non-empty final content from orchestration tool calls.
                if isinstance(content_from_args, str) and content_from_args.strip():
                    full_response = content_from_args

                # 2) If no content, but SQL is present, execute SQL tool directly.
                elif isinstance(sql_from_args, str) and sql_from_args.strip():
                    try:
                        full_response = query_nif_db_tool_2(SQL_QUERY=sql_from_args).handle()
                    except Exception as err:
                        full_response = f"Search NIF tool execution error: {err}"

                # 3) Final fallback: use latest non-empty message content.
                elif full_response is None or str(full_response).strip() == "":
                    try:
                        last_msg_content = getattr(session_agent.message_history[-1], "content", None)
                        if isinstance(last_msg_content, str) and last_msg_content.strip():
                            full_response = last_msg_content
                    except Exception:
                        pass
            else:
                # Non-database tasks: use routed content when present.
                if isinstance(function_args, dict):
                    content_from_args = function_args.get('content')
                    if isinstance(content_from_args, str) and content_from_args.strip():
                        full_response = content_from_args

            if full_response is None:
                full_response = ""

        full_response = str(full_response)

        if active_task_name == 'nifguide_task':
            try:
                expected_nifguide_qid = infer_expected_nif_question_id(
                    nif_progress_df=user_nif_progress_df,
                    user_query="",
                )
            except Exception as infer_err:
                print(f"Warning: Failed to infer next NIF question ID after update: {infer_err}")
            full_response = enforce_nifguide_response_contract(
                response_text=full_response,
                expected_question_id=expected_nifguide_qid,
            )
            full_response = format_nifguide_choices_multiline(full_response)
            full_response = remove_tool_calls(full_response)

        if active_task_name == 'nif_database_task':
            sql_from_latest_msg = None
            if isinstance(function_args, dict):
                sql_candidate = function_args.get("SQL_QUERY")
                if isinstance(sql_candidate, str) and sql_candidate.strip():
                    sql_from_latest_msg = sql_candidate.strip()

            sql_from_history, tool_output_from_history = get_latest_sql_trace(session_agent)
            sql_to_display = sql_from_latest_msg or sql_from_history or last_nif_sql_query

            if isinstance(sql_to_display, str) and sql_to_display.strip():
                if (
                    isinstance(last_nif_query_result, dict)
                    and str(last_nif_query_result.get("sql", "")).strip() == sql_to_display.strip()
                ):
                    nif_query_result_data = last_nif_query_result
                else:
                    nif_query_result_data = execute_nif_select_query(
                        sql_to_display, max_rows=NIF_DB_MAX_ROWS
                    )
                    last_nif_query_result = nif_query_result_data
            elif isinstance(last_nif_query_result, dict):
                nif_query_result_data = last_nif_query_result

            # Force deterministic zero-row messaging for user clarity.
            if (
                isinstance(nif_query_result_data, dict)
                and not nif_query_result_data.get("error")
                and int(nif_query_result_data.get("row_count", 0) or 0) == 0
            ):
                full_response = "There are 0 records for that query."

            if NIF_DB_SHOW_SQL_TRACE:
                trace_sections = []
                if isinstance(sql_to_display, str) and sql_to_display.strip():
                    trace_sections.append(f"SQL executed:\n```sql\n{sql_to_display}\n```")
                else:
                    trace_sections.append("SQL executed:\n```text\n(No SQL statement was captured for this turn)\n```")

                if NIF_DB_SHOW_OUTPUT_RECORDS:
                    raw_output_to_display = None
                    trace_output_heading = "Output records"
                    if isinstance(nif_query_result_data, dict):
                        raw_output_to_display = format_nif_query_result_for_llm(
                            nif_query_result_data,
                            preview_rows=NIF_DB_TRACE_PREVIEW_ROWS,
                            include_row_preview=NIF_DB_TRACE_INCLUDE_ROWS,
                        )
                    elif isinstance(tool_output_from_history, str) and tool_output_from_history.strip():
                        raw_output_to_display = tool_output_from_history.strip()
                        trace_output_heading = "Raw query output"
                    elif isinstance(full_response, str) and full_response.strip():
                        raw_output_to_display = full_response.strip()
                        trace_output_heading = "Raw query output"

                    if isinstance(raw_output_to_display, str) and raw_output_to_display.strip():
                        trace_sections.append(f"{trace_output_heading}:\n```\n{raw_output_to_display}\n```")

                if trace_sections:
                    response_clean = full_response.strip()
                    if response_clean:
                        full_response = response_clean + "\n\n---\n" + "\n\n".join(trace_sections)
                    else:
                        full_response = "\n\n".join(trace_sections)

        # Remove 'DONE' from response if present (used for Langroid orchestration)
        full_response = full_response.replace('DONE.', '').replace('DONE', '')

        if extra_output_bool:
            # Append active task to results
            full_response = f"<{session_task.name}>         " + full_response

            # Append session ID to results
            full_response = full_response + f"          (Session ID: {sid})"

        if not extra_output_bool:
            # Remove TOOL calls
            full_response = remove_tool_calls(full_response)

        # emit("stream", full_response, namespace="/", to=socket_id)

        # Save the updated history
        try:
            trim_agent_history_for_task(session_agent, active_task_name)
            save_chat_history(session_agent.message_history, active_user_email, sid)
        except Exception as e:
            print(f"Exception saving chat history: {e}")

        # The value to clear the textarea
        cleared_input_value = ''

        # Write NIF progress data to dcc.Store
        if active_task_name == 'nifguide_task':
            try:
                autosave_result = maybe_autosave_nif_progress(
                    user_data=user_data,
                    session_id=sid,
                    user_nif_progress_df=user_nif_progress_df,
                    prior_last_question_id=prior_nif_last_qid,
                    prior_last_answer=prior_nif_last_answer,
                )
                if (
                    extra_output_bool
                    and isinstance(autosave_result, dict)
                    and autosave_result.get("saved")
                ):
                    full_response += (
                        f"\n\n---\nAutosave: step {autosave_result.get('answered_step_count')} "
                        f"saved ({autosave_result.get('autosave_file')})"
                    )
            except Exception as autosave_err:
                print(f"Warning: NIF autosave failed: {autosave_err}")
            user_nif_progress_json = user_nif_progress_df.to_json(orient='split')
            return full_response, user_nif_progress_json, cleared_input_value, None, None
        else:
            if active_task_name == 'nif_database_task':
                if NIF_DB_ENHANCED_OUTPUT:
                    return (
                        full_response,
                        no_update,
                        cleared_input_value,
                        nif_query_result_data,
                        nif_llm_prompt_data,
                    )
                return full_response, no_update, cleared_input_value, None, nif_llm_prompt_data
            return full_response, no_update, cleared_input_value, None, None


@app.callback(
    Output("nif-query-output-container", "style"),
    Output("nif-query-summary", "children"),
    Output("nif-query-table", "columns"),
    Output("nif-query-table", "data"),
    Input("nif_query_result_store", "data"),
    Input("active_task_name", "data"),
)
def render_nif_query_table(nif_query_result, active_task_name):
    if not NIF_DB_ENHANCED_OUTPUT:
        return {"display": "none"}, "", [], []

    if active_task_name != "nif_database_task":
        return {"display": "none"}, "", [], []

    if not nif_query_result or not isinstance(nif_query_result, dict):
        return {"display": "none"}, "", [], []

    sql = str(nif_query_result.get("sql", "") or "").strip()
    row_count = int(nif_query_result.get("row_count", 0) or 0)
    displayed_row_count = int(nif_query_result.get("displayed_row_count", 0) or 0)
    truncated = bool(nif_query_result.get("truncated", False))
    error = nif_query_result.get("error")

    columns = nif_query_result.get("columns", []) or []
    rows = nif_query_result.get("rows", []) or []

    if not columns and rows:
        columns = list(rows[0].keys())

    dash_columns = [{"name": col, "id": col} for col in columns]

    summary_parts = []
    if sql:
        summary_parts.append("SQL captured")
    else:
        summary_parts.append("No SQL captured")
    summary_parts.append(f"Rows returned: {row_count}")
    if truncated:
        summary_parts.append(f"Showing first {displayed_row_count} rows")
    if error:
        summary_parts.append(f"Error: {error}")

    return {"display": "block", "marginTop": "12px"}, " | ".join(summary_parts), dash_columns, rows


@app.callback(
    Output("show-nif-llm-prompt-button", "disabled"),
    Input("nif_llm_prompt_store", "data"),
    Input("active_task_name", "data"),
)
def toggle_nif_prompt_button(prompt_payload, active_task_name):
    # Prompt visibility is handled in the React UI.
    # Keep Dash "Show Prompt" button disabled.
    return True


@app.callback(
    Output("nif-llm-prompt-modal", "is_open"),
    Output("nif-llm-prompt-modal-body", "children"),
    Input("show-nif-llm-prompt-button", "n_clicks"),
    Input("nif-llm-prompt-modal-close-button", "n_clicks"),
    State("nif-llm-prompt-modal", "is_open"),
    State("nif_llm_prompt_store", "data"),
    prevent_initial_call=True,
)
def toggle_nif_prompt_modal(n_open, n_close, is_open, prompt_payload):
    trigger_id = ctx.triggered_id

    if trigger_id == "show-nif-llm-prompt-button":
        return True, format_nif_llm_prompt_for_modal(prompt_payload)

    if trigger_id == "nif-llm-prompt-modal-close-button":
        return False, no_update

    return is_open, no_update

# clientside_callback(
#     """connected => !connected""",
#     Output("btn", "disabled"),
#     Input("socketio", "connected"),
# )


# clientside_callback(
#     """(word) => {
#     window.aiwBuffer += word;
#     return "";
#     }""",
#     Output("results", "children", allow_duplicate=True),
#     Input("socketio", "data-stream"),
#     prevent_initial_call=True,

# )

# # Thumbs down button
# @app.callback(
#     Output("thumbs-down-button", "className"),
#     Input("thumbs-down-button", "n_clicks"),
#     State("thumbs-down-button", "className")
# )
# def toggle_thumbs_down(n_clicks, current_class):
#     if not n_clicks:
#         return "feedback-button"

#     # Toggle the active class
#     if "active" in current_class:
#         return "feedback-button"
#     else:
#         return "feedback-button active"

# Thumbs down chat history save
@app.callback(
    Output("feedback-dummy-output", "children"),
    Output("feedback-confirmation-alert", "is_open"),
    Output("thumbs-down-button", "className"),

    Input("thumbs-down-button", "n_clicks"),
    State('user-store', 'data'),
    # Need the current user's session ID to find the file
    State('user_session_id', 'data'),
    # Use the current class state for the required output, even if we don't change it here
    State("thumbs-down-button", "className"),
    prevent_initial_call=True,
)
def handle_feedback_save(n_clicks, user_data, active_sid, current_class):
    if n_clicks is None or n_clicks == 0:
        raise dash.exceptions.PreventUpdate

    # Get user info from SSO
    if not user_data:   # When running on local or if SSO is not functioning
        active_user_name = 'User_no_sso'
        active_user_email = 'User_no_sso@email.com'
    else:
        active_user_name = user_data.get('name', 'User')
        active_user_email = user_data.get('email', 'user@email.com')

    safe_user_id = get_safe_user_id(active_user_email)

    # The source file is the current history file
    user_history_dir = get_user_history_dir(active_user_email)
    SOURCE_FILE = user_history_dir / f"chat_history_{active_sid}.json"

    # The destination file includes a timestamp for uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    DEST_FILENAME = f"feedback_{safe_user_id}_{active_sid}_{timestamp}.json"
    DEST_FILE = ADMIN_FEEDBACK_DIR / DEST_FILENAME

    pr.logit(f"Feedback triggered. Checking for file: {SOURCE_FILE}")
    log_message = ""
    file_saved_successfully = False

    # Copy the file
    if SOURCE_FILE.exists():
        try:
            # Copy the file to the new location
            shutil.copy2(SOURCE_FILE, DEST_FILE)
            log_message = f"Feedback logged at {datetime.now().isoformat()}"
            file_saved_successfully = True
            pr.logit(f"Chat history saved to feedback folder: {DEST_FILE}")

        except Exception as e:
            log_message = f"Error logging feedback: {e}"
            pr.logit(f"ERROR saving chat history feedback: {e}")
    else:
        log_message = f"No history file found for session {active_sid}."
        pr.logit(f"Chat history file not found for session {active_sid}. Cannot save feedback.")

    dummy_output_content = log_message
    # Only show the alert if the file copy was successful
    alert_is_open = file_saved_successfully
    # Always return the base, unclicked class name to immediately reset the button's appearance
    button_class = "feedback-button"

    return dummy_output_content, alert_is_open, button_class

# Save in-progress NIF
#!!! Nice to have: append [completed] to name if they got to the last question
#!!! Nice to have: warn if overwriting a NIF
@callback(
    Output('file-dropdown', 'options', allow_duplicate=True),

    Input('nif-save-button', 'n_clicks'),
    State('save-filename', 'value'),
    State('nif_progress_data_json', 'data'),
    State('user-store', 'data'),
    State('user_session_id', 'data'),
    prevent_initial_call=True
)
def save_nif_in_progress(n_clicks, filename, user_nif_progress_json, user_data, active_sid):
    save_result = save_nif_session(
        user_data=user_data,
        filename=filename,
        user_nif_progress_json=user_nif_progress_json,
    )
    if not save_result.get("ok"):
        print(f"<save_nif_in_progress> {save_result.get('message', 'Failed to save progress.')}")
        return list_saved_nif_files_for_user(user_data)
    return save_result.get("files", [])

# Toggle save NIF in progress dialog box
@app.callback(
    Output("save-nif-progress-modal", "is_open"),
    Output('save-nif-progress-modal-header', 'children'),

    Input("nif-save-button", "n_clicks"),
    State('save-filename', 'value'),
    State("save-nif-progress-modal", "is_open"),

    prevent_initial_call=True,
)
def toggle_save_nif_progress_box(save_progress_clicks, filename, is_open):
    # Clean filename
    filename_touse = re.sub('[^A-Za-z0-9 ._-]+', '', filename)      # Remove all characters not in set A-Za-z0-9(space)(period)(underscore)(dash)
    popup_title = f"Progress saved to {filename_touse}."
    return not is_open, popup_title

# Download NIF data
@callback(
    Output('download-nif-data', 'data'),

    Input('nif-export-button', 'n_clicks'),
    State('save-filename', 'value'),
    State('nif_progress_data_json', 'data'),
    prevent_initial_call=True
)
def download_file(n_clicks, filename, user_nif_progress_json):
    filename_clean = _sanitize_nif_filename(filename)
    user_nif_progress_df_fordl_t = build_nif_progress_download_frame(user_nif_progress_json)
    return dcc.send_data_frame(user_nif_progress_df_fordl_t.to_csv, f"{filename_clean}.csv", header=False)

# Chat History Amount toggle
@app.callback(
    Output('toggle-switch-container', 'style'),
    Input('hist-collapse-button', 'n_clicks'),
)
def toggle_switch_visibility_by_clicks(n_clicks):
    visible_style = {
        'display': 'flex',
        'justify-content': 'flex-end',
    }

    if not n_clicks or n_clicks % 2 == 0:
        # Hide the toggle
        return {'display': 'none'}
    else:
        # Show the toggle
        return visible_style

# Show Progress by asking agent
# This only shows answers from chat history.
# @app.callback(
#     Output('human-chat-text-area', 'value', allow_duplicate=True),
#     Output('submit-button', 'n_clicks', allow_duplicate=True),

#     Input('nif-progress-button', 'n_clicks'),
#     State('submit-button', 'n_clicks'),
#     prevent_initial_call=True
# )
# def show_progress(nif_progress_button_clicks, submit_clicks):
#     submit_text = "Show me my answers so far, displayed as a list (Field Name: Answer)."
#     submit_clicks = (submit_clicks or 0) + 1
#     return submit_text, submit_clicks

# Show Progress by printing dataframe
@app.callback(
    Output("show-nif-progress-modal", "is_open"),
    Output('show-nif-progress-modal-body', 'children'),

    Input('nif-progress-button', 'n_clicks'),
    State('nif_progress_data_json', 'data'),
    State("show-nif-progress-modal", "is_open"),

    prevent_initial_call=True
)
def show_progress(nif_progress_button_clicks, user_nif_progress_json, is_open):
    preview_result = build_nif_progress_preview_text(user_nif_progress_json)
    modal_body = html.Pre(
        preview_result.get("progress_text", "No progress data found."),
        style={
            'fontSize': '12px',
            'fontFamily': 'monospace',
            'whiteSpace': 'pre-wrap'
        }
    )

    return not is_open, modal_body

# show/hide chat history
# For short term, consider printing session_agent.message_history rather than reading from file
# id="chat-history-amount-toggle",
# label=['Current', 'Past 30 days']
@app.callback(
    Output("hist-collapse", "is_open", allow_duplicate=True),
    Output('hist-collapse-button','children', allow_duplicate=True),
    Output("hist-content", "children", allow_duplicate=True), # Output for dcc.Markdown

    [Input("hist-collapse-button", "n_clicks")],
    [State("hist-collapse", "is_open")],
    Input('chat-history-amount-toggle', 'value'),
    State('user-store', 'data'),
    State('user_session_id', 'data'),
    # Input('results-markdown', 'children'),      # So it will refresh upon new message
    prevent_initial_call=True,
)
def show_hide_history(button_clicks, is_open, amount_toggle, user_data, active_sid):#, submit):
    pr.logit(f'show_hide_history: n_clicks={button_clicks} is_open={is_open}')

    if button_clicks is None:
        return is_open, 'Show history', ''

    # Get user info from SSO
    if not user_data:   # When running on local or if SSO is not functioning
        active_user_name = 'User_no_sso'
        active_user_email = 'User_no_sso@email.com'
    else:
        active_user_name = user_data.get('name', 'User')
        active_user_email = user_data.get('email', 'user@email.com')

    # Determine short or long term history
    if amount_toggle:   # Toggle True is longer history
        chat_history = load_chat_history(active_user_email)     # Omit session ID to load all user history
    else:               # Toggle False is session history
        chat_history = load_chat_history(active_user_email, active_sid)     # Pass session ID to load session history

    if chat_history:
        markdown_string = ""
        for hist in chat_history:
            try:
                role_display = hist.role.value.upper() if isinstance(hist.role, Role) else str(hist.role).upper()
                content = hist.content
                date = hist.timestamp
                # Append each message as a new block in Markdown
                markdown_string += f"*<{date.strftime('%Y-%m-%d %I-%M-%S %p')}>* **{role_display}**: {content}\n\n" # Added an extra newline for block separation
            except Exception as exception:
                pr.logit(f'ERROR: show_hide_history rendering history: {exception=}, hist={hist}')
                return True, 'Hide history', 'Error rendering history.'

        # Remove the last extra newline if desired, or leave for consistent spacing
        if markdown_string.endswith("\n\n"):
            markdown_string = markdown_string[:-2]

        display_content = markdown_string

    else: # No history found
        pr.logit('No chat history found.')
        display_content = 'There is no chat history yet.'

    if not is_open and ctx.triggered_id == 'hist-collapse-button':     # If the collapse is currently CLOSED, we want to OPEN it
        pr.logit('Opening history.')
        pr.logit(f'show_hide_history returning: is_open={not is_open}, button_text={"Hide History"}')
        return not is_open, 'Hide History', display_content

    if is_open:
        if ctx.triggered_id == 'hist-collapse-button':   # If the collapse is currently OPEN, and button is clicked, we want to CLOSE it
            pr.logit('Closing history.')
            return False, 'Show History', ''
        else:       # If the collapse is currently OPEN, and button is not clicked, return content (this happens if amount_toggle changes)
            return is_open, 'Hide History', display_content

# Toggle clear chat history warning dialog box
@app.callback(
    Output("history-confirm-modal", "is_open"),

    Input("hist-clear-button", "n_clicks"),
    Input("history-cancel-button", "n_clicks"),
    # Adding the 'Yes' button here as well, so it closes the modal after the action is done.
    Input("history-confirm-button", "n_clicks"),
    State("history-confirm-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_clear_chat_history_warning(n1, n2, n_confirm, is_open):
    ctx = dash.callback_context

    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    # Get the ID of the component that triggered the callback
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "hist-clear-button":
        if n1:
            return True # Open the modal

    # If Cancel or Confirm buttons are clicked, close the modal
    elif trigger_id in ["history-cancel-button", "history-confirm-button"]:
        if n2 or n_confirm:
            return False # Close the modal

    raise dash.exceptions.PreventUpdate

# clear chat history
@app.callback(
    Output("hist-content", "children", allow_duplicate=True),
    Output("hist-collapse", "is_open", allow_duplicate=True),
    Output("hist-collapse-button", "children", allow_duplicate=True),
    # Output("hist-clear-button", "n_clicks"),
    Output("results-markdown", "children", allow_duplicate=True),
    Output('human-chat-text-area', 'value', allow_duplicate=True),
    Output('file-dropdown', 'options', allow_duplicate=True),
    Output('nif_progress_data_json', 'data', allow_duplicate=True),
    Output('nif_query_result_store', 'data', allow_duplicate=True),
    Output('nif_llm_prompt_store', 'data', allow_duplicate=True),

    Input("history-confirm-button", "n_clicks"),
    State("hist-collapse", "is_open"),
    State('user-store', 'data'),
    State('user_session_id', 'data'),
    prevent_initial_call=True,
)
def clear_chat_history_and_file(n_clicks, is_collapse_open, user_data, active_sid):
    pr.logit(f'clear_chat_history_and_file: {n_clicks=}, is_collapse_open={is_collapse_open}')

    if n_clicks is None or n_clicks == 0:
        raise dash.exceptions.PreventUpdate

    # Get user info from SSO
    if not user_data:   # When running on local or if SSO is not functioning
        active_user_name = 'User_no_sso'
        active_user_email = 'User_no_sso@email.com'
    else:
        active_user_name = user_data.get('name', 'User')
        active_user_email = user_data.get('email', 'user@email.com')

    # Clear history from agent
    # Loop over all session_tasks
    for TASK, SESSION_ID in session_tasks.keys():
        # If it's for the active user's session, clear history
        if SESSION_ID == active_sid:
            session_task = get_session_task(TASK, SESSION_ID, active_user_name)
            session_agent = session_task.agent
            session_agent.clear_history(start=-len(session_agent.message_history))

    # Clear in-memory NIF backend autosave state for this user as well.
    clear_nif_backend_user_state(active_user_email)

    # Clear history file
    message_content = ""

    user_history_dir = get_user_history_dir(active_user_email)
    user_history_files = get_available_files(user_history_dir)
    if len(user_history_files) > 0:
        for filename in user_history_files:
            full_path_and_filename = os.path.join(user_history_dir, filename)
            os.remove(full_path_and_filename)
        message_content = "**Chat history has been cleared successfully!**"
        pr.logit("User chat history deleted.")
    else:
        message_content = "**No chat history to clear.**"
        pr.logit("No user chat history found.")

    # Clear any in-progress NIFs
    user_nif_progress_dir = get_user_nif_progress_dir(active_user_email)
    nif_save_dir = user_nif_progress_dir
    nif_in_prog_files = get_available_files(nif_save_dir)
    for filename in nif_in_prog_files:
        full_path_and_filename = os.path.join(nif_save_dir, filename)
        os.remove(full_path_and_filename)

    user_nif_progress_json = pd.DataFrame(index=[0]).to_json(orient='split')

    # Always ensure the collapse is open to display the message
    # And set the "Show history" button text to "Hide History" as it's now open
    return (
        message_content,    # hist-content: Display the confirmation message as Markdown
        True,               # hist-collapse: Ensure it's OPEN to show the message
        "Hide History",     # hist-collapse-button: Change text because it's now open
        '',                 # Clear NIFTY response box
        '',                 # Clear user input box
        [NO_USER_NIFS_MESSAGE],     # Clear file dropdown
        user_nif_progress_json,      # Write cleared NIF progress
        None,               # Clear NIF query table/store
        None,               # Clear NIF prompt store
    )


@app.server.before_request
def load_user_before_request():
    """Load user into Flask's g object before each request"""
    g.user = get_user_from_alb()

    # Optional: Log the failure only if g.user is None and we expect it
    if g.user is None and request.headers.get("x-amzn-oidc-data") is None:
         # This is likely a non-authenticated request (e.g., a simple Dash callback)
         # We can log this if desired, but we don't need the exception printout.
         pass
    elif g.user is None:
         # Log if we failed even though a token was present (meaning decoding failed)
         print("\n!!! ALB User Load FAILED: Token present but decoding failed.\n")

# Load user and create user-specific file
@app.callback(
    Output('user-store', 'data'),
    Input('load-user-interval', 'n_intervals'), # Triggers exactly once
    prevent_initial_call=False
)
def load_user(_):
    """
    Loads the user data from Flask's g.user, stores it in dcc.Store,
    and creates a dedicated user file directory.
    """
    # Get user data from Flask's global context
    user_data = g.user if g.user else {}

    if not user_data:
        # User not authenticated or token failed to decode
        return {}

    # Extract email
    user_email = user_data.get('email')

    if user_email:
        try:
            safe_user_id = get_safe_user_id(user_email)
            user_folder = USER_FILES_DIR / safe_user_id
            user_folder.mkdir(exist_ok=True)
            print(f"User folder created/verified for: {user_email} (ID: {safe_user_id}) at {user_folder}")

        except Exception as e:
            # Log any file system errors
            print(f"ERROR: Failed to create user directory for {user_email}. Error: {e}")

    # Return the user data to populate the dcc.Store
    return user_data

@app.callback(
    Output('user-info', 'children'),
    Input('user-store', 'data')
)
def display_user(user_data):
    """Display user information"""
    if not user_data or not user_data.get('name'):
        return html.Div(
            [
                html.H6("Loading user info...", className="text-white"),
                html.P(f"Version {version_number}", className="text-light small mt-0"),
                html.P(APP_LLM_HEADER_TEXT, className="text-light small mt-0 mb-0"),
            ],
            style={'textAlign': 'right', 'paddingRight': '15px'}
        )

    # User is logged in and data is available
    return html.Div(
        [
            html.H6(f"Welcome, {user_data.get('name', 'User')}", className="text-light mb-0"),
            html.P(f"Version {version_number}", className="text-light small mt-0"),
            html.P(APP_LLM_HEADER_TEXT, className="text-light small mt-0 mb-0"),
        ],
        style={'textAlign': 'right', 'paddingRight': '15px'}
    )


# =============================================================================
#### API v1 routes for React UI (parallel to Dash UI)
# =============================================================================
def _as_api_value(value, fallback=None):
    """
    Convert Dash callback no_update sentinel into API-friendly values.
    """
    if value is no_update:
        return fallback
    return value


def _api_user_payload():
    """
    Prefer Flask g.user (server-trusted identity), fallback to local defaults.
    """
    user = g.user if getattr(g, "user", None) else {}
    if not user:
        return {
            "name": "User_no_sso",
            "email": "User_no_sso@email.com",
            "roles": [],
        }
    return {
        "name": user.get("name") or "User",
        "email": user.get("email") or "user@email.com",
        "roles": user.get("roles") or [],
        "sub": user.get("sub"),
        "upn": user.get("upn"),
    }


def _allowed_react_origins():
    raw = os.getenv("REACT_UI_ALLOWED_ORIGINS", "http://localhost:5173")
    return {
        origin.strip()
        for origin in str(raw).split(",")
        if origin.strip()
    }


@app.server.after_request
def _apply_api_cors_headers(response):
    """
    Restrict cross-origin API access to an explicit allow-list.
    """
    if request.path.startswith("/api/v1/"):
        origin = (request.headers.get("Origin") or "").strip()
        if origin and origin in _allowed_react_origins():
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@app.server.route("/api/v1/<path:_path>", methods=["OPTIONS"])
def api_preflight(_path):
    return flask.Response(status=204)


@app.server.route("/api/v1/health/live", methods=["GET"])
def api_health_live():
    return flask.jsonify(
        {
            "status": "ok",
            "version": version_number,
            "llm_provider": APP_LLM_PROVIDER,
            "llm_model": APP_LLM_MODEL,
            "llm_header_text": APP_LLM_HEADER_TEXT,
            "dash_ui_qa_merge_enabled": DASH_UI_QA_MERGE,
            "timestamp_utc": dt.datetime.now(dt.UTC).isoformat(),
        }
    )


@app.server.route("/api/v1/me", methods=["GET"])
def api_me():
    return flask.jsonify({"user": _api_user_payload()})


@app.server.route("/api/v1/session", methods=["POST"])
def api_create_session():
    sid = generate_session_id()
    user_payload = _api_user_payload()
    return flask.jsonify(
        {
            "session_id": sid,
            "user": user_payload,
            "active_task_name": "nifguide_task",
            "nif_progress_data_json": pd.DataFrame(index=[0]).to_json(orient="split"),
            "llm_provider": APP_LLM_PROVIDER,
            "llm_model": APP_LLM_MODEL,
            "llm_header_text": APP_LLM_HEADER_TEXT,
        }
    )


@app.server.route("/api/v1/modules", methods=["GET"])
def api_modules():
    return flask.jsonify(
        {
            "modules": [
                {"label": "Get started On New training resources", "selected_question": "Get started on training resources"},
                {"label": "NIF Step by Step", "selected_question": "NIF step by step"},
                {"label": "Search NIF", "selected_question": "Search NIF"},
                {"label": "NIF Field question", "selected_question": "NIF field question"},
            ]
        }
    )


def _react_step_feature_disabled_response():
    return (
        flask.jsonify(
            {
                "code": "feature_disabled",
                "message": "Enhanced React NIF step flow is disabled. Set REACT_NIF_STEP_ENHANCED=true.",
            }
        ),
        404,
    )


@app.server.route("/api/v1/nif/step/options", methods=["GET"])
def api_nif_step_options():
    if not REACT_NIF_STEP_ENHANCED:
        return _react_step_feature_disabled_response()
    return flask.jsonify(
        {
            "actions": [
                {"id": "new", "label": "New NIF chat session"},
                {"id": "load", "label": "Load NIF from previous chat"},
            ]
        }
    )


@app.server.route("/api/v1/nif/saved", methods=["GET"])
def api_nif_saved_files():
    if not REACT_NIF_STEP_ENHANCED:
        return _react_step_feature_disabled_response()

    file_options = list_saved_nif_files_for_user(_api_user_payload())
    if file_options:
        return flask.jsonify({"files": file_options, "message": ""})
    return flask.jsonify({"files": [], "message": "No saved NIFs found."})


@app.server.route("/api/v1/nif/new-session", methods=["POST"])
def api_nif_new_session():
    if not REACT_NIF_STEP_ENHANCED:
        return _react_step_feature_disabled_response()

    payload = request.get_json(silent=True) or {}
    active_sid = str(payload.get("session_id", "") or "").strip() or generate_session_id()
    current_clicks = int(payload.get("submit_clicks", 0) or 0)

    start_result = start_new_nif_session(
        user_data=_api_user_payload(),
        active_sid=active_sid,
        current_clicks=current_clicks,
    )
    return flask.jsonify(start_result)


@app.server.route("/api/v1/nif/load-session", methods=["POST"])
def api_nif_load_session():
    if not REACT_NIF_STEP_ENHANCED:
        return _react_step_feature_disabled_response()

    payload = request.get_json(silent=True) or {}
    active_sid = str(payload.get("session_id", "") or "").strip() or generate_session_id()
    current_clicks = int(payload.get("submit_clicks", 0) or 0)
    selected_nif_file = str(payload.get("filename", "") or "").strip()

    load_result = load_saved_nif_session(
        user_data=_api_user_payload(),
        active_sid=active_sid,
        current_clicks=current_clicks,
        selected_nif_file=selected_nif_file,
    )
    if not load_result.get("ok"):
        return (
            flask.jsonify(
                {
                    "code": load_result.get("code", "load_failed"),
                    "message": load_result.get("message", "Failed to load saved NIF session."),
                }
            ),
            400,
        )
    return flask.jsonify(load_result)


@app.server.route("/api/v1/nif/save-session", methods=["POST"])
def api_nif_save_session():
    if not REACT_NIF_STEP_ENHANCED:
        return _react_step_feature_disabled_response()

    payload = request.get_json(silent=True) or {}
    filename = str(payload.get("filename", "") or "").strip()
    user_nif_progress_json = payload.get("nif_progress_data_json")

    save_result = save_nif_session(
        user_data=_api_user_payload(),
        filename=filename,
        user_nif_progress_json=user_nif_progress_json,
    )
    if not save_result.get("ok"):
        return (
            flask.jsonify(
                {
                    "code": save_result.get("code", "save_failed"),
                    "message": save_result.get("message", "Failed to save NIF progress."),
                }
            ),
            400,
        )
    return flask.jsonify(save_result)


@app.server.route("/api/v1/nif/reload-config", methods=["POST"])
def api_nif_reload_config():
    if not REACT_NIF_STEP_ENHANCED:
        return _react_step_feature_disabled_response()

    payload = request.get_json(silent=True) or {}
    active_task_name = str(payload.get("active_task_name", "nifguide_task") or "nifguide_task").strip()

    try:
        message = build_reload_nif_message(active_task_name)
        return flask.jsonify({"ok": True, "code": "ok", "message": message})
    except Exception as err:
        return (
            flask.jsonify(
                {
                    "code": "reload_failed",
                    "message": f"Failed to reload NIF rules at runtime. Details: {err}",
                }
            ),
            500,
        )


@app.server.route("/api/v1/nif/progress-preview", methods=["POST"])
def api_nif_progress_preview():
    if not REACT_NIF_STEP_ENHANCED:
        return _react_step_feature_disabled_response()

    payload = request.get_json(silent=True) or {}
    preview_result = build_nif_progress_preview_text(payload.get("nif_progress_data_json"))
    if not preview_result.get("ok"):
        return (
            flask.jsonify(
                {
                    "code": preview_result.get("code", "no_progress_data"),
                    "message": preview_result.get("message", "No progress data found."),
                }
            ),
            400,
        )
    return flask.jsonify(preview_result)


@app.server.route("/api/v1/nif/download", methods=["POST"])
def api_nif_download_file():
    if not REACT_NIF_STEP_ENHANCED:
        return _react_step_feature_disabled_response()

    payload = request.get_json(silent=True) or {}
    filename_clean = _sanitize_nif_filename(payload.get("filename"))

    try:
        download_df = build_nif_progress_download_frame(payload.get("nif_progress_data_json"))
        csv_text = download_df.to_csv(header=False)
    except Exception:
        return (
            flask.jsonify(
                {
                    "code": "download_failed",
                    "message": "No progress data found to download.",
                }
            ),
            400,
        )

    response = flask.Response(csv_text, mimetype="text/csv")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename_clean}.csv"'
    return response


@app.server.route("/api/v1/modules/select", methods=["POST"])
def api_select_module():
    payload = request.get_json(silent=True) or {}
    selected_question = str(payload.get("selected_question", "") or "").strip()
    current_clicks = int(payload.get("current_clicks", 0) or 0)
    active_sid = str(payload.get("session_id", "") or "").strip() or generate_session_id()
    selected_nif_file = payload.get("selected_nif_file")

    user_payload = _api_user_payload()

    (
        next_human_chat_value,
        next_clicks,
        next_nif_progress_json,
        next_active_task_name,
        next_simple_message,
    ) = update_textarea_and_trigger_submit_chat(
        selected_question=selected_question,
        current_clicks=current_clicks,
        user_data=user_payload,
        active_sid=active_sid,
        selected_nif_file=selected_nif_file,
    )

    human_chat_value = _as_api_value(next_human_chat_value, "")
    submit_clicks = _as_api_value(next_clicks, current_clicks)
    nif_progress_json = _as_api_value(next_nif_progress_json, payload.get("nif_progress_data_json"))
    active_task_name = _as_api_value(next_active_task_name, payload.get("active_task_name") or "nifguide_task")
    simple_message = _as_api_value(next_simple_message, "")

    auto_submit = bool(
        isinstance(human_chat_value, str)
        and human_chat_value.strip()
        and submit_clicks != current_clicks
    )

    return flask.jsonify(
        {
            "session_id": active_sid,
            "selected_question": selected_question,
            "human_chat_value": human_chat_value,
            "submit_clicks": submit_clicks,
            "nif_progress_data_json": nif_progress_json,
            "active_task_name": active_task_name,
            "simple_message": simple_message,
            "auto_submit": auto_submit,
        }
    )


@app.server.route("/api/v1/chat/turn", methods=["POST"])
def api_chat_turn():
    payload = request.get_json(silent=True) or {}

    sid = str(payload.get("session_id", "") or "").strip() or generate_session_id()
    active_task_name = str(payload.get("active_task_name", "nifguide_task") or "nifguide_task").strip()
    human_chat_value = str(payload.get("human_chat_value", "") or "").strip()
    n_sub = int(payload.get("submit_clicks", 1) or 1)

    incoming_progress_json = payload.get("nif_progress_data_json")
    if not incoming_progress_json:
        incoming_progress_json = pd.DataFrame(index=[0]).to_json(orient="split")

    user_payload = _api_user_payload()

    (
        response_markdown,
        next_nif_progress_json,
        _cleared_input_value,
        nif_query_result_data,
        nif_llm_prompt_data,
    ) = chat_bot(
        n_sub=n_sub,
        human_chat_value=human_chat_value,
        user_data=user_payload,
        sid=sid,
        user_nif_progress_json=incoming_progress_json,
        active_task_name=active_task_name,
    )

    return flask.jsonify(
        {
            "session_id": sid,
            "active_task_name": active_task_name,
            "response_markdown": _as_api_value(response_markdown, ""),
            "nif_progress_data_json": _as_api_value(next_nif_progress_json, incoming_progress_json),
            "nif_query_result": _as_api_value(nif_query_result_data, None),
            "nif_llm_prompt": _as_api_value(nif_llm_prompt_data, None),
        }
    )


@app.server.route("/react", defaults={"path": ""})
@app.server.route("/react/<path:path>")
def serve_react_ui(path: str):
    """
    Serve the built React UI bundle from react-ui/dist if present.
    """
    react_dist = os.path.join(CURRENT_FOLDER_DASH_APP, "react-ui", "dist")
    if not os.path.isdir(react_dist):
        return flask.Response(
            "React UI build not found. Run: cd react-ui && npm install && npm run build",
            status=404,
            mimetype="text/plain",
        )

    if path:
        candidate = os.path.join(react_dist, path)
        if os.path.isfile(candidate):
            return flask.send_from_directory(react_dist, path)
    return flask.send_from_directory(react_dist, "index.html")

#%% 6. RUN APP
#############################################################################################################
if __name__ == "__main__":
    app.run(port=int(os.getenv("DASH_PORT", "8052")), debug=False)
