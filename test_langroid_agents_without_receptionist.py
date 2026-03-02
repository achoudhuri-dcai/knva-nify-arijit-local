#%% ABOUT
# *****************************************************************************
"""
This script is for testing the Langroid agents.

It has been copied from the main Dash app DCAI_KN_Chat_Dash_UI_Gradio_Mock.py
but has all Dash components removed.

Version "without_receptionist" is for testing each agent as its own task. This
means:
    - Each agent will interact directly with the user.
    - Must include note about allowed topics in each agent's system prompt.
    - Each agent will be in its own task, and can have interactive=True.

This will require Dash script updates:
    - Each button on the UI will start a different task.
"""
#%% 1. STARTUP & IMPORTS

# standard library packages (included with python and always available)
import os, sys, datetime as dt
import inspect

from dotenv import find_dotenv, load_dotenv, dotenv_values
dotenv_loaded = load_dotenv()
dotenv_dict = dotenv_values()
if dotenv_loaded:
    print('> Environment file loaded.')
else:
    print('> Environment file is either empty or not found!')

print(f"[{dt.datetime.now().strftime('%Y%m%d_%H%M%S.%f')[:19]}] Starting {__name__}")
print(f"[{dt.datetime.now().strftime('%Y%m%d_%H%M%S.%f')[:19]}] cwd = {os.getcwd()}")
print(f"[{dt.datetime.now().strftime('%Y%m%d_%H%M%S.%f')[:19]}] {sys.path[:2] = }")
print(f"[{dt.datetime.now().strftime('%Y%m%d_%H%M%S.%f')[:19]}] {sys.version = }")

# Third party packages (ie, those installed with pip )
import base64
import io
import time
import uuid
from pathlib import Path
from addict import Dict
import urllib.parse
import shutil
import json
from datetime import datetime
import sqlite3
import pandas as pd
import numpy as np
from pprint import pp as pprint

from lib.fa_dash_utils import instantiate_app
import lib.fa_lib as fa
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
"This part is all about Dash and has been removed."

#%% 3. GLOBAL PROGRAM ELEMENTS
###############################################################################################
# - Global variables and functions that aren't directly involved in the UI interactivity (Callbacks)
# - Typical example would be functions that read, store, and prep data to be used in the app
###############################################################################################
# =============================================================================
#### Read data
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

# Create history directory if it doesn't exist
HISTORY_DIR = Path('./history')
HISTORY_DIR.mkdir(exist_ok=True)
HISTORY_FILE = HISTORY_DIR / 'chat_history.json'

END_MSG = 'END$$$END'

# NIF database
# nif_database = os.path.join(utils.DATABASE_FOLDER, 'NIFS.db')
# Using the one with added columns for rejection reason and link to PDF.
# NOTE these are only populated for a few example NIFs.
nif_database = os.path.join(utils.DATABASE_FOLDER, 'NIFS_with_reject_and_pdf.db')

# Brands database
brands_database = os.path.join(utils.DATABASE_FOLDER, 'KNV_Active_Brands.db')

# Glossary of terms
glossary = pd.read_excel(
    os.path.join(utils.DOCUMENT_FOLDER, 'Glossary of Terms for NIFs.xlsx')
    ,sheet_name='glossary'
)
glossary = glossary.set_index(keys='Term')      # Column to become dictionary keys
glossary_dict = dict(glossary['Definition'])

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

# Product Type: map abbreviations from online form to full names in NIF database
#!!! Note product type in database is actually a combination of country, type, and subtype!
product_type_abbreviations = {
    "CS":"Straight Case"
    ,"BULK CS":"Bulk Case"
}

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

# Drop Length column
del expert_system_rules['Length']

# Write to markdown for reading into LLM system message
expert_system_rules_md = expert_system_rules.to_markdown(index=False)

# For testing, subset to the rules used in the POC
# expert_system_rules_poc = expert_system_rules.iloc[3:28, :]
# expert_system_rules_poc_md = expert_system_rules_poc.to_markdown(index=False)

# Create dummy user role lookup for testing
user_roles_dummy = pd.DataFrame({
    'username':['user_a', 'user_b', 'user_c']
    , 'role':['requestor', 'requestor', 'lim']
})

# =============================================================================
#### Implementation Dropdown Reference Lists
# =============================================================================
# Import
ddref_rdl_categories = pd.read_excel(
    os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'RDL_Categories.xlsx')
)
# Prepare for agent
ddref_rdl_categories_md = ddref_rdl_categories['Category'].to_markdown(index=False)

# Import
ddref_material_prefix = pd.read_excel(
    os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'MATERIAL_PREFIX.xlsx')
)
# Prepare for agent
ddref_material_prefix_md = ddref_material_prefix[['COUNTRY', 'MATERIAL_PREFIX']].sort_values(by='COUNTRY').to_markdown(index=False)
# Not distinguishing countries for now. Would need to add instructions to agent.
# ddref_material_prefix_md = ddref_material_prefix['MATERIAL_PREFIX'].to_markdown(index=False)

# Import
ddref_addnl_packaging = pd.read_excel(
    os.path.join(utils.CONTROL_FOLDER, 'dropdown_references', 'ADDITIONAL_PACKAGING_LAUNCH.xlsx')
)
# Prepare for agent
ddref_addnl_packaging_md = ddref_addnl_packaging['Value'].to_markdown(index=False)

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

# The Glossary tab contains business terms and database abbreviations
glossary_and_db_terms = pd.read_excel(
    nifty_definitions_excel
    ,sheet_name='glossary'
    ,header=0
)
glossary_and_db_terms = dpu.cleancolnames(glossary_and_db_terms)

# Create a dictionary
glossary_and_db_terms = glossary_and_db_terms.set_index(keys='term')      # Column to become dictionary keys
glossary_and_db_terms_dict = dict(glossary_and_db_terms['definition'])

# =============================================================================
#### Define Styles
# =============================================================================
# the style arguments for the sidebar. We use position:fixed and a fixed width
SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "20rem",
    "padding": "2rem 1rem",
    "background-color": "white",
}

HEADING_STYLE = {
    "color":"#8401FF",
    "font-weight": "bold",
    }

BUTTON_STYLE = {
    "background-color": "#8401FF",
    "border-color": "#8401FF",
    "font-weight": "bold",
}

# =============================================================================
#### Text and constants
# =============================================================================

# Demo question options
demo_questions = [{'label': i, 'value': i, 'disabled': False} for i in ["Question about a specific NIF field",
                                                                        "Guidance to fill out the NIF step by step",
                                                                        "Get started (find training resources)",
                                                                        "Check NIF status (NIF database search)",
                                                                        ]]

# =============================================================================
#### Functions and Definitions
# =============================================================================
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

# Utility functions for history management
def load_chat_history(include_system=False):
    """Loads chat history from the HISTORY_FILE as a list of LLMMessage objects."""
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

def save_chat_history(message_history):
    """Saves the current chat history to the HISTORY_FILE as a list of dictionaries."""
    # Convert LLMMessage objects to dictionaries in the format you expect
    history_to_save = []
    for msg in message_history:
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

    with open(HISTORY_FILE, 'w') as f:
        json.dump(history_to_save, f, indent=2)

# Check and sync raw_docs folder in assets (used for webaddress links)
def sync_files_in_existing_dirs():
    source_files = {f for f in os.listdir(SOURCE_RAW_DOCS_FOLDER) if os.path.isfile(os.path.join(SOURCE_RAW_DOCS_FOLDER, f))}
    destination_files = {f for f in os.listdir(ASSETS_RAW_DOCS_FOLDER) if os.path.isfile(os.path.join(ASSETS_RAW_DOCS_FOLDER, f))}

    # Copy missing files from source to destination
    for filename in source_files:
        src_path = os.path.join(SOURCE_RAW_DOCS_FOLDER, filename)
        dst_path = os.path.join(ASSETS_RAW_DOCS_FOLDER, filename)

        if not os.path.exists(dst_path) or os.path.getmtime(src_path) > os.path.getmtime(dst_path):
            try:
                shutil.copy2(src_path, dst_path) # copy2 preserves metadata like modification times
                pr.logit(f"Copied/Updated: '{filename}' from '{src_path}' to '{dst_path}'.")
            except Exception as e:
                pr.logit(f"Error copying file '{filename}': {e}")

        # # Loggin for debugging
        # else:
        #     pr.logit(f"Skipping '{filename}': already up-to-date in destination.")

    # Remove files from destination that are no longer in source
    for filename in destination_files:
        src_path = os.path.join(SOURCE_RAW_DOCS_FOLDER, filename)
        dst_path = os.path.join(ASSETS_RAW_DOCS_FOLDER, filename)
        if not os.path.exists(src_path):
            try:
                os.remove(dst_path)
                pr.logit(f"Removed extraneous file: '{filename}' from '{dst_path}'.")
            except Exception as e:
                pr.logit(f"Error removing file '{filename}': {e}")

    pr.logit("Document folder synchronization complete.")

# Create the raw_docs in the assets folder if it doesn't exist. Make it match source folder
if not os.path.exists(ASSETS_RAW_DOCS_FOLDER):
    pr.logit(f"'{ASSETS_RAW_DOCS_FOLDER}' not found. Copying entire folder from '{SOURCE_RAW_DOCS_FOLDER}'.")
    try:
        shutil.copytree(SOURCE_RAW_DOCS_FOLDER, ASSETS_RAW_DOCS_FOLDER)
        pr.logit(f"Successfully copied '{SOURCE_RAW_DOCS_FOLDER}' to '{ASSETS_RAW_DOCS_FOLDER}'.")
    except shutil.Error as e:
        pr.logit(f"Error copying directory: {e}")
        pr.logit(f"It's possible '{ASSETS_RAW_DOCS_FOLDER}' already partially exists. Attempting file-by-file sync.")
        # Fallback to file-by-file if copytree fails (e.g., due to partial existence)
        sync_files_in_existing_dirs()
else:
    pr.logit(f"'{ASSETS_RAW_DOCS_FOLDER}' already exists. Syncing individual files.")
    sync_files_in_existing_dirs()

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

# =============================================================================
#### First version: storing multiple NIFs in single table
# =============================================================================
def create_or_load_user_nif_progress_data(USERID:str):
    funcname = inspect.currentframe().f_code.co_name

    name_for_index = 'nifty_id'
    user_specific_progress_file = os.path.join(HISTORY_DIR, f"nif_progress_{USERID}.csv")
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
        USERID:str
        ,NIF_PROGRESS_DF:object    # Dataframe user_nif_progress_df created by create_or_load_user_nif_progress_data()
    ):
    funcname = inspect.currentframe().f_code.co_name   

    user_specific_progress_file = os.path.join(HISTORY_DIR, f"nif_progress_{USERID}.csv")
    NIF_PROGRESS_DF.to_csv(user_specific_progress_file)     # Keep the index!
    print(f"<{funcname}> User NIF progress dataframe saved to file {user_specific_progress_file}.")
    
    return None

'''
test_user_id = 'user_a'

# Create or load
global active_user_nif_progress_df      # Make it global so NIF Guide agent can modify it
active_user_nif_progress_df = create_or_load_user_nif_progress_data(test_user_id)

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
save_user_nif_progress_data(test_user_id, active_user_nif_progress_df)
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
#   global active_user_nif_progress_df      # Make it global so NIF Guide agent can modify it
#   active_user_nif_progress_df = create_active_user_nif_progress_data()
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

# For the NIF Guide agent to update the active user table with each response
# active_user_nif_progress_df must exist as a global table
def update_active_user_nif_progress_data(
        FIELD_NUMBER:int                # Field number you want to update. Must exist in nif_fields_req_init_template.
        ,VALUE:str                      # Value to write to the field
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Check that FIELD_NUMBER provided is valid
    valid_field_numbers = list(nif_fields_req_init_template['field_number'])
    if FIELD_NUMBER in valid_field_numbers:
        
        # Get column name from template based on field number
        _field_number = (nif_fields_req_init_template['field_number'] == FIELD_NUMBER)
        nif_progress_colname = nif_fields_req_init_template.loc[_field_number, 'field_name_and_number'].item()
                   
        # Update
        active_user_nif_progress_df[nif_progress_colname] = VALUE
        print(f"<{funcname}> Field {nif_progress_colname} updated with value {VALUE}.")
        
    else:
        raise Exception(f"<{funcname}> ERROR: Field number provided ({FIELD_NUMBER}) is not valid.")
        
    return None

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
        
# To use with "Save progress" button
# User will provide a filename. Must be CSV.
#!!! Append [completed] to filename based on _agentref_last_question_answered
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

'''
test_user_id = 'user_a'
test_nif_label = 'test_nif'

# Create
global active_user_nif_progress_df      # Make it global so NIF Guide agent can modify it
active_user_nif_progress_df = create_active_user_nif_progress_data()

# Update: Invalid field number
update_active_user_nif_progress_data(100, 'user_a@knova.com')

# Update
update_active_user_nif_progress_data(1002, 'user_a@knova.com')

# Update with last_question_answered
update_active_user_nif_progress_data_2(
    LAST_QUESTION_ANSWERED='PRODUCT COUNTRY'
    ,LAST_ANSWER_GIVEN='US'
    ,FIELD_NUMBER=1008
)

# Update with last_question_answered (no field value)
update_active_user_nif_progress_data_2(
    LAST_QUESTION_ANSWERED='CASE'
    ,LAST_ANSWER_GIVEN='Club'
)

# Save
user_save_path = os.path.join(HISTORY_DIR, f"{test_user_id}_{test_nif_label}.csv")
save_active_user_nif_progress_data(user_save_path)

# Save: Invalid file type
user_save_path = os.path.join(HISTORY_DIR, f"{test_user_id}_{test_nif_label}")
save_active_user_nif_progress_data(user_save_path)

# Load
global active_user_nif_progress_df      # Make it global so NIF Guide agent can modify it
active_user_nif_progress_df = load_active_user_nif_progress_data(user_save_path)

# Load: Invalid file type
global active_user_nif_progress_df      # Make it global so NIF Guide agent can modify it
active_user_nif_progress_df = load_active_user_nif_progress_data(user_save_path)

'''
#%% LLM TOOLS

# =============================================================================
#### Agent configs
# =============================================================================
# Create an agent config WITHOUT a system prompt to be used for multiple agents.
# Each agent will be wrapped in a task with its own system prompt
agent_config_gpt4o = lr.ChatAgentConfig(llm=utils.azure_llm_gpt4o)

agent_config_claude4 = lr.ChatAgentConfig(llm=utils.aws_llm_claude4)
agent_config_claude35 = lr.ChatAgentConfig(llm=utils.aws_llm_claude35)
agent_config_gptoss = lr.ChatAgentConfig(llm=utils.aws_llm_gptoss)

agent_config_for_receptionist = agent_config_gptoss
agent_config_for_others = agent_config_claude35

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
!!! Add: anytime user wants to see their progress so far, display active_user_nif_progress_df.to_dict(orient='list')

Dev plan:
    1. [done] Walk through expert system rules for a brand new NIF, writing to in-progress table as you go.
!!! 2. Pick up walkthrough for a partially completed NIF
        This was working only when I put the active NIF table directly into the prompt.
        The issue seems to be that the agent doesn't see the 'check_nif_progress' results until AFTER it initiates the conversation.
        One solution: have Dash get the last question answered and pass it in when initiating the bot.
!!!    3. Add display dropdown lookups
!!!    4. Add glossary
    5. [if needed] Add all_nif_fields lookup
    6. [with module 3] Add NIF database search
    7. [with module 1] Add documentation search
'''
# =============================================================================
#### Initialize progress df
# =============================================================================
global active_user_nif_progress_df      # Make it global so NIF Guide agent can modify it
active_user_nif_progress_df = create_active_user_nif_progress_data()

# Auto-populate the first few fields. Dash should do this.
'''
    Bev's Notes:
    Capture "Requestor Name" (1001) from user logged in.
    Capture "Requestor Email" (1002) from user logged in.
    Capture "Requestor Date" (1003) from current date.
    Capture "Version" (1004) from current version of NIF form.
    Capture "Requestor" (1005) from user logged in, which matches with the drop down of the user roles. {This assigns security within the NIF form.}
    Go to LIM.
'''
REQUESTOR_NAME = 'user_a'
REQUESTOR_EMAIL = 'user_a@knova.com'
REQUESTOR_DATE = f"{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
NIF_FORM_VERSION = '1.2.3'
REQUESTOR = 'User A'

# update_active_user_nif_progress_data(1001, REQUESTOR_NAME)
# update_active_user_nif_progress_data(1002, REQUESTOR_EMAIL)
# update_active_user_nif_progress_data(1003, REQUESTOR_DATE)
# update_active_user_nif_progress_data(1004, NIF_FORM_VERSION)
# update_active_user_nif_progress_data(1005, REQUESTOR)

update_active_user_nif_progress_data_2('START REQ INITIATE', REQUESTOR_NAME, 1001)
update_active_user_nif_progress_data_2('START REQ INITIATE', REQUESTOR_EMAIL, 1002)
update_active_user_nif_progress_data_2('START REQ INITIATE', REQUESTOR_DATE, 1003)
update_active_user_nif_progress_data_2('START REQ INITIATE', NIF_FORM_VERSION, 1004)
update_active_user_nif_progress_data_2('START REQ INITIATE', REQUESTOR, 1005)

# =============================================================================
#### Functions and tools
# =============================================================================
# Function to update the table tracking the user's answers to the step-by-step guide.
# This will be called after each answer the user gives.
class write_nif_field_tool(lr.agent.ToolMessage):
    # request: the name of this function for reference in system messages
    request:str = "write_nif_field"

    # purpose: a description of what this function does. A good description is important so the LLM knows how to use it.
    purpose:str = "To update the table tracking the user's answers for each NIF field in the step-by-step guide."

    # Any other variables defined here before the handle() method are treated as required arguments
    # Alternative: hard-code the name of the NIF_PROGRESS_DF. Dash will create or load the user-specific file. Must be global for this function to modify it.
    # NIF_PROGRESS_DF:object  # Dataframe to write to. Should be a user-specific table created by create_or_load_user_nif_progress_data().
    # Alternative: the dataframe is for a specific in-progress NIF (single row table)
    # INDEX_VALUE:str         # ID that specifies which row to write to.
    FIELD_NUMBER:int        # NIF Field (column) to write. This corresponds to the step you are at in the Expert Rules flow.
    VALUE:str               # Value to write. Provided by the user.

    # handle() is based on update_active_user_nif_progress_data()
    def handle(self):   
        # Check that FIELD_NUMBER provided is valid
        valid_field_numbers = list(nif_fields_req_init_template['field_number'])
        if self.FIELD_NUMBER in valid_field_numbers:
            
            # Get column name from template based on field number
            _field_number = (nif_fields_req_init_template['field_number'] == self.FIELD_NUMBER)
            nif_progress_colname = nif_fields_req_init_template.loc[_field_number, 'field_name_and_number'].item()
                            
            # Update global active user table
            active_user_nif_progress_df[nif_progress_colname] = self.VALUE
    
        else:
            raise Exception(f"ERROR: Field number provided ({self.FIELD_NUMBER}) is not valid.")
            
        return f"Field {nif_progress_colname} updated with value {self.VALUE}."

class write_nif_progress_tool(lr.agent.ToolMessage):
    # request: the name of this function for reference in system messages
    request:str = "write_nif_progress"

    # purpose: a description of what this function does. A good description is important so the LLM knows how to use it.
    purpose:str = "To update the table tracking the user's answers for each NIF field in the step-by-step guide."

    # Any other variables defined here before the handle() method are treated as required arguments
    LAST_QUESTION_ANSWERED:str      # The Question ID from expert_system_rules that was most recently answered
    LAST_ANSWER_GIVEN:str           # The answer given by the user.
    FIELD_NUMBER:int=None           # Field number you want to update. Must exist in nif_fields_req_init_template. If None, only update LAST_QUESTION_ANSWERED and LAST_ANSWER_GIVEN (to capture a decision question that does not get written to the NIF).

    # handle() is based on update_active_user_nif_progress_data_2()
    def handle(self):   
        # Update reference columns
        active_user_nif_progress_df['_agentref_last_question_answered'] = self.LAST_QUESTION_ANSWERED
        active_user_nif_progress_df['_agentref_last_answer_given'] = self.LAST_ANSWER_GIVEN
        print(f"Last question updated to '{self.LAST_QUESTION_ANSWERED}'.")
    
        # Check that FIELD_NUMBER provided is valid
        valid_field_numbers = list(nif_fields_req_init_template['field_number'])
        if self.FIELD_NUMBER:    # If field number is provided
            if self.FIELD_NUMBER in valid_field_numbers:
                
                # Get column name from template based on field number
                _field_number = (nif_fields_req_init_template['field_number'] == self.FIELD_NUMBER)
                nif_progress_colname = nif_fields_req_init_template.loc[_field_number, 'field_name_and_number'].item()
                           
                # Update
                active_user_nif_progress_df[nif_progress_colname] = self.LAST_ANSWER_GIVEN
                print(f"Field '{nif_progress_colname}' updated with value '{self.LAST_ANSWER_GIVEN}'.")
                
            else:
                raise Exception(f"ERROR: Field number provided ({self.FIELD_NUMBER}) is not valid.")
            
        return f"Active user NIF progress data updated."

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

# =============================================================================
#### Config
# =============================================================================
nifguide_agent_name = 'NIFGuideAgent'

nifguide_agent = lr.ChatAgent(agent_config_claude35)
# nifguide_agent.enable_message(write_nif_field_tool)
nifguide_agent.enable_message(write_nif_progress_tool)
nifguide_agent.enable_message(check_nif_progress_tool)
# nifguide_agent.enable_message(RecipientTool)

nifguide_task = lr.Task(
    nifguide_agent
    ,name=nifguide_agent_name
    ,system_message=f'''
        You are an expert in Kellanova's New Item Form (NIF). This form is used
        to specify new products or variations of existing products. Your role
        is to guide the user through the 'Requestor - Project Initiation'
        section of the NIF, which contains the PROJECT_INITIATION_FIELDS listed
        here:
            <PROJECT_INITIATION_FIELDS>
            {list(nif_fields_req_init_template['field_name_and_number'])}
            </PROJECT_INITIATION_FIELDS>
        
        {llm_instruction_scope_of_discussion}
    '''
    # Prep step v1

    # Prep step v2
        # # PREPARATION STEP
        
        # Determine whether the user is starting a new NIF or resuming a NIF in
        # progress by calling the 'check_nif_progress' function with argument
        # FIELD_NAME = '_agentref_last_question_answered' and examining the value
        # returned:
        #     - If the value is ["START REQ INITIATE"], then the user is
        #     STARTING A NEW NIF.
        
        #     - If the value is anything besides ["START REQ INITIATE"], then the
        #     user is RESUMING A NIF IN PROGRESS.
        
    # Test specifying in progress. Bot still started a new NIF!
        # # PREPARATION STEP
        
        # The user is RESUMING A NIF IN PROGRESS. Review their ACTIVE_NIF_PROGRESS
        # by calling the 'check_nif_progress' function with argument FIELD_NAME='ALL'.

    f'''
        # PREPARATION STEP
        
        Review the user's ACTIVE_NIF_PROGRESS by calling the 'check_nif_progress'
        function. Determine whether the user is starting a new NIF or resuming a
        NIF in progress:
            - If the field "_agentref_last_question_answered" has a value of
            "START REQ INITIATE", then the user is STARTING A NEW NIF.
        
            - If the field "_agentref_last_question_answered" has any value besides
            "START REQ INITIATE", then the user is RESUMING A NIF IN PROGRESS.
            
        # INTERACTION WITH THE USER
        
        Begin with a simple greeting and state your role.
        
        State what you determined in the PREPARATION STEP and ask if the user
        would like to proceed with the walkthrough.
        
        If the user wants to proceed, follow these steps:

            - Refer to the STEP_BY_STEP_RULES table to guide the discussion. You
            will walk through this table one row at a time.
                <STEP_BY_STEP_RULES>
                {expert_system_rules_md}
                </STEP_BY_STEP_RULES>
                
            - If the user is STARTING A NEW NIF, begin the walkthrough with
            Question ID 'LIM'.
            
            - If the user is RESUMING A NIF IN PROGRESS, look up the Question ID
            that was last answered from '_agentref_last_question_answered'.
            Follow the instructions corresponding to the last answer the user gave
            from '_agentref_last_answer_given'. Begin the walkthrough with the next
            Question ID, indicated by the instruction "Go to".
    
            - Ask the user the question from the "Question" column. Based on the
            user's answer, follow the instructions in the "Instructions" column.
                        
                If the "Question" column says 'None', proceed with the instructions
                without asking the user.
                
                The instructions tell you (the LLM agent) which NIf field or fields
                to update based on the user's answer to this or prior questions.
                Instructions use the following formatting:
                    
                    - If the instruction includes "Display dd: reference list",
                    lookup the indicated table from DROPDOWN REFERENCE LISTS and
                    show the user the list of options.
                    
                    - If there is a NIF field to update, it is specified as
                    "FIELD_NAME" (FIELD_NUMBER). Update the active NIF table by
                    calling the 'write_nif_progress' function with the following
                    arguments:
                        
                        LAST_QUESTION_ANSWERED: the Question ID of the question you just asked.
                        LAST_ANSWER_GIVEN: the ['VALUE'] specified in the instructions based on the user's answer, if any. Otherwise, the literal answer given by the user.
                        FIELD_NUMBER: use this only if the instructions include a (FIELD_NUMBER) to update. Otherwise, do not use this argument.
                    
                    Note: you will have to call this function mulitple times if the
                    instructions include values for multiple fields!
                    
                    - If the value to write is exact based on the user's answer,
                    it will be wrapped in square brackets, as in ['VALUE'].
                    
                    - If the value to write is freeform, you will use whatever the
                    user says as long as it adheres to any rules stated in the
                    instructions. This is indicated by [FREEFORM].
                    
                    - "Go to" indicates the Question ID of the next question to ask.
        
        # DROPDOWN REFERENCE LISTS
        
        <RDL_CATEGORIES>
        {ddref_rdl_categories_md}
        </RDL_CATEGORIES>

        <MATERIAL_PREFIX>
        {ddref_material_prefix_md}
        </MATERIAL_PREFIX>

        <ADDITIONAL_PACKAGING_LAUNCH>
        {ddref_addnl_packaging_md}
        </ADDITIONAL_PACKAGING_LAUNCH>
    '''
    # Testing ran successfully
        # Ask the user the 3 questions below in order. After each answer you receive,      
        # call the 'write_nif_field' function with the following arguments:
        #     FIELD_NUMBER: the number in parenthesis at the end of the question
        #     VALUE: the answer given by the user
            
        #     <QUESTIONS>
        #     1. What is the requestor name (1001)?
        #     2. What is the requestor email (1002)?
        #     3. What is the requestor date (1003)?
        #     </QUESTIONS>
    # System message before using write_nif_progress_tool
        # # PREPARATION STEP
        
        # Review the user's active NIF table:
        #     <USERS_ACTIVE_NIF_TABLE>
        #     {active_user_nif_progress_df.to_dict(orient='list')}
        #     </USERS_ACTIVE_NIF_TABLE>
        
        # If every field after 'Requestor (1005)' has a value of
        # '<NOT YET DETERMINED>', then the user is starting a new NIF. You will
        # begin the walkthrough with field 'LIM (1006)'.
        
        # If any field after 'Requestor (1005)' has a value besides
        # '<NOT YET DETERMINED>', then the user is continuing an in-progress NIF.
        # You will begin the walkthrough with the first field whose value is
        # '<NOT YET DETERMINED>'.
        
        # # INTERACTION WITH THE USER
        
        # Begin with a simple greeting and state your role.
        
        # State what you determined in the PREPARATION STEP and ask if the user
        # would like to proceed with the walkthrough.
        
        # If the user wants to proceed, follow these steps:

        #     - Refer to the STEP_BY_STEP_RULES table to guide the discussion. You
        #     will walk through this table one row at a time.
        #         <STEP_BY_STEP_RULES>
        #         {expert_system_rules_md}.
        #         </STEP_BY_STEP_RULES>

        #     - Ask the user the question from the "Question" column. Based on the
        #     user's answer, follow the instructions in the "Instructions" column.
                        
        #         If the "Question" column says 'None', proceed with the instructions
        #         without asking the user.
                
        #         The instructions tell you (the LLM agent) which NIf field or fields
        #         to update based on the user's answer to this or prior questions.
        #         Instructions use the following formatting:
        #             - Any field to update is specified as "FIELD_NAME" (FIELD_NUMBER).
        #             - If the value to write is exact based on the user's answer,
        #             it will be wrapped in square brackets, as in ['VALUE'].
        #             - If the value to write is freeform, you will use whatever the
        #             user says as long as it adheres to any rules stated in the
        #             instructions. This is indicated by [FREEFORM].
        #             - "Go to" indicates the Question ID of next question to ask.
            
        #     - For each row in the STEP_BY_STEP_RULES table, if there is a field to
        #     update, then update the user's active NIF table by calling the
        #     'write_nif_field' function with the following arguments:
        #         FIELD_NUMBER: the field number to update
        #         VALUE: the value to write
                
        #         Note that you will have to call this function mulitple times if the
        #         instructions include values for multiple fields!

        #         Note that not every row in the STEP_BY_STEP_RULES table requires an
        #         update to the user's active NIF table; some simply direct you to the
        #         next question.
    ,interactive=True     # For testing
    
    # For use in Dash, setting interactive=False so the task exits after each round.
    # This is necessary to get a response to print in Dash. 
    # ,interactive=False

    # Setting restart=False so that message history persists when task exits.
    # ,restart=False
)

'''
# Test with interactive=True
nifguide_task.run()

# Test with interactive=False
nifguide_task.run('Justin')
nifguide_task.run('justin@gmail.com')
nifguide_task.run('10/17/2025')
''' 

#%% NIF GUIDE AGENT BEFORE OVERHAUL 10/30
nifguide_agent_name = 'NIFGuideAgent'

# nifguide_agent = lr.ChatAgent(agent_config_claude35)
# nifguide_agent.enable_message(write_nif_progress_tool)
# nifguide_agent.enable_message(check_nif_progress_tool)
# nifguide_agent.enable_message(RecipientTool)

# Create a dummy dataframe for defining the agent.
# When the agent is active inside a callback, nif_progress_df will point to the
# current user's nif progress data.
nif_progress_df = pd.DataFrame()

nifguide_agent = nif_guide_update_agent(agent_config_claude35)

nifguide_task = lr.Task(
    nifguide_agent
    ,name=nifguide_agent_name
    ,system_message=f'''
        You are an expert in Kellanova's New Item Form (NIF). This form is used
        to specify new products or variations of existing products. Your role
        is to guide the user through the 'Requestor - Project Initiation'
        section of the NIF, which contains the PROJECT_INITIATION_FIELDS listed
        here:
            <PROJECT_INITIATION_FIELDS>
            {list(nif_fields_req_init_template['field_name_and_number'])}
            </PROJECT_INITIATION_FIELDS>

        {llm_instruction_scope_of_discussion}
    '''
    # Prep step v2
        # # PREPARATION STEP

        # Determine whether the user is starting a new NIF or resuming a NIF in
        # progress by calling the 'check_nif_progress' function with argument
        # FIELD_NAME = '_agentref_last_question_answered' and examining the value
        # returned:
        #     - If the value is "START REQ INITIATE", then the user is
        #     STARTING A NEW NIF.

        #     - If the value is anything besides "START REQ INITIATE", then the
        #     user is RESUMING A NIF IN PROGRESS.

    # Prep step not working - do this in Dash when initiating instead
        # # PREPARATION STEP

        # Review the user's ACTIVE_NIF_PROGRESS by calling the 'check_nif_progress'
        # function. Determine whether the user is starting a new NIF or resuming a
        # NIF in progress:
        #     - If the field "_agentref_last_question_answered" has a value of
        #     "START REQ INITIATE", then the user is STARTING A NEW NIF.

        #     - If the field "_agentref_last_question_answered" has any value besides
        #     "START REQ INITIATE", then the user is RESUMING A NIF IN PROGRESS.

        # # INTERACTION WITH THE USER

        # Begin with a simple greeting and state your role.

        # State what you determined in the PREPARATION STEP and ask if the user
        # would like to proceed with the walkthrough.

            # - If the user is STARTING A NEW NIF, begin the walkthrough with
            # Question ID 'LIM'.

            # - If the user is RESUMING A NIF IN PROGRESS, look up the Question ID
            # that was last answered from '_agentref_last_question_answered'.
            # Follow the instructions corresponding to the last answer the user gave
            # from '_agentref_last_answer_given'. Begin the walkthrough with the next
            # Question ID, indicated by the instruction "Go to".
    f'''
        # INTERACTION WITH THE USER

        Begin with a simple greeting and state your role.

        Ask if the user would like to start a new NIF or resume a NIF in progress.

        If the user wants to proceed, follow these steps:

            - Refer to the STEP_BY_STEP_RULES table to guide the discussion. You
            will walk through this table one row at a time.
                <STEP_BY_STEP_RULES>
                {expert_system_rules_md}
                </STEP_BY_STEP_RULES>

            - Ask the user the question from the "Question" column. Based on the
            user's answer, follow the instructions in the "Instructions" column.
            If the "Question" column says 'None', proceed with the instructions
            without asking the user.

                ## READING THE "INSTRUCTIONS" COLUMN

                - If the instruction includes "Display dd: reference list",
                lookup the indicated table from DROPDOWN REFERENCE LISTS and
                show the user the list of options. Always display this list
                as a numbered list with each item on a new line.

                - If there is a NIF field to update, it is specified as
                "FIELD_NAME" (FIELD_NUMBER).

                - If the value to write is exact based on the user's answer,
                it will be wrapped in angle brackets, as in <'VALUE'>.

                - If the value to write is freeform, you will use whatever the
                user says as long as it adheres to any rules stated in the
                instructions. This is indicated by <FREEFORM>.

                - "Go to" indicates the Question ID of the next question to ask.

            - For each row in the table starting where you began the walkthrough,
            update the active NIF table by calling the 'update_nif_progress'
            function with the arguments below. Note that you will have to call
            this function mulitple times if the instructions include values for
            multiple fields.

                <write_nif_progress_arguments>
                LAST_QUESTION_ID: the Question ID of the current row.
                LAST_VALUE: the <'VALUE'> specified in the instructions, or the literal answer given by the user if <FREEFORM>.
                FIELD_NUMBER: use this only if the instructions include a (FIELD_NUMBER) to update. Otherwise, do not use this argument.
                </write_nif_progress_arguments>
    '''
    #### Reference lists
    f'''
        # DROPDOWN REFERENCE LISTS
        <LIM_USERS>
        {ddref_lim_users_md}
        </LIM_USERS>

        <RDL_CATEGORIES>
        {ddref_rdl_categories_md}
        </RDL_CATEGORIES>

        <MATERIAL_PREFIX>
        {ddref_material_prefix_md}
        </MATERIAL_PREFIX>

        <ADDITIONAL_PACKAGING_LAUNCH>
        {ddref_addnl_packaging_md}
        </ADDITIONAL_PACKAGING_LAUNCH>
        
        <PRIVATE_LABEL>
        {ddref_private_label_md}
        </PRIVATE_LABEL>
    '''
    # ,interactive=True     # For testing

    # For use in Dash, setting interactive=False so the task exits after each round.
    # This is necessary to get a response to print in Dash.
    ,interactive=False

    # Setting restart=False so that message history persists when task exits.
    ,restart=False
)
    
#%% TESTING DATAFRAME UPDATE CAPABILITIES
# https://claude.ai/chat/783734ee-8acf-4679-b125-4f04991f315c

# =============================================================================
#### Define agent tools
# =============================================================================
class UpdateDataFrameTool(lr.agent.ToolMessage):
    """Tool to update values in a pandas DataFrame"""
    
    request: str = "update_dataframe"
    purpose: str = "Update specific rows/columns in the DataFrame"
    
    row_index: int
    column_name: str
    new_value: str | int | float
    
    def handle(self) -> str:
        """Handle the update operation - actual implementation in agent"""
        return f"Updating row {self.row_index}, column '{self.column_name}' to {self.new_value}"
    
class DataFrameAgent(lr.ChatAgent):
    def __init__(self, config: lr.ChatAgentConfig, dataframe: pd.DataFrame):
        super().__init__(config)
        self.df = dataframe
        
        # Enable the tools
        self.enable_message(UpdateDataFrameTool)
   
    def update_dataframe(self, msg: UpdateDataFrameTool) -> str:
        """Handle DataFrame update requests"""
        try:
            if msg.row_index not in self.df.index:
                return f"Error: Row index {msg.row_index} does not exist"
            
            if msg.column_name not in self.df.columns:
                return f"Error: Column '{msg.column_name}' does not exist"
            
            old_value = self.df.at[msg.row_index, msg.column_name]
            self.df.at[msg.row_index, msg.column_name] = msg.new_value
            
            return f"Successfully updated row {msg.row_index}, column '{msg.column_name}' from {old_value} to {msg.new_value}"
        except Exception as e:
            return f"Error updating DataFrame: {str(e)}"
        
    def get_dataframe(self) -> pd.DataFrame:
         """Return the current state of the DataFrame"""
         return self.df
       
# =============================================================================
#### Configure agent
# =============================================================================
# Initialize dataframe
active_user_nif_progress_df = create_active_user_nif_progress_data()
# active_user_nif_progress_df = pd.DataFrame()    # Test with empty dataframe: doesn't work!

# Create the agent with the DataFrame
test_df_agent = DataFrameAgent(agent_config_claude35, active_user_nif_progress_df)

test_df_task = lr.Task(
    test_df_agent
    ,name='test_df_agent'
    ,system_message='''
        You are a helpful assistant that can update pandas DataFrames.
        You have access to tools to update rows in the DataFrame.
        When asked to modify the DataFrame, use the appropriate tool.
    '''
    ,interactive=True
)
test_df_task.run()

# =============================================================================
#### Test rearranging enable_message DOESN'T WORK
# =============================================================================
# class UpdateDataFrameTool(lr.agent.ToolMessage):
#     """Tool to update values in a pandas DataFrame"""
    
#     request: str = "update_dataframe"
#     purpose: str = "Update specific rows/columns in the DataFrame"
    
#     row_index: int
#     column_name: str
#     new_value: str | int | float
#     # df: object = active_user_nif_progress_df    # Putting this here due to errors. DOESN'T WORK.
    
#     def handle(self) -> str:
#         try:
#             if self.row_index not in self.df.index:
#                 return f"Error: Row index {self.row_index} does not exist"
            
#             if self.column_name not in self.df.columns:
#                 return f"Error: Column '{self.column_name}' does not exist"
            
#             old_value = self.df.at[self.row_index, self.column_name]
#             self.df.at[self.row_index, self.column_name] = self.new_value
            
#             return f"Successfully updated row {self.row_index}, column '{self.column_name}' from {old_value} to {self.new_value}"
#         except Exception as e:
#             return f"Error updating DataFrame: {str(e)}"

# class DataFrameAgent(lr.ChatAgent):
#     def __init__(self, config: lr.ChatAgentConfig, dataframe: pd.DataFrame):
#         super().__init__(config)
#         self.df = dataframe

# # Initialize dataframe
# active_user_nif_progress_df = create_active_user_nif_progress_data()

# # Create the agent with the DataFrame
# test_df_agent = lr.ChatAgent(agent_config_claude35)

# test_df_task = lr.Task(
#     test_df_agent
#     ,name='test_df_agent'
#     ,system_message='''
#         You are a helpful assistant that can update pandas DataFrames.
#         You have access to tools to update rows in the DataFrame.
#         When asked to modify the DataFrame, use the appropriate tool.
#     '''
#     ,interactive=True
# )
# test_df_task.run()

'''
row index 0, column 'LIM (1006)', value 'JRR Tolkien'
'''

#%% NIF GUIDE AGENT

# =============================================================================
#### Functions and tools
# =============================================================================
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
nifguide_agent_name = 'NIFGuideAgent'

# Create a dummy dataframe for defining the agent.
# When the agent is active inside a callback, user_nif_progress_df will point to the
# current user's nif progress data.
user_nif_progress_df = pd.DataFrame()

nifguide_agent = nif_guide_update_agent(agent_config_claude35, user_nif_progress_df)

nifguide_task = lr.Task(
    nifguide_agent
    ,name=nifguide_agent_name
    ,system_message = f'''
        You are an expert in Kellanova's New Item Form (NIF). This form is used
        to specify new products or variations of existing products. Your role
        is to guide the user through the 'Requestor - Project Initiation'
        section of the NIF, which contains the PROJECT_INITIATION_FIELDS listed
        here:
            <PROJECT_INITIATION_FIELDS>
            {list(nif_fields_req_init_template['field_name_and_number'])}
            </PROJECT_INITIATION_FIELDS>

        {llm_instruction_scope_of_discussion}

        # STRICT ADHERENCE TO RULES
        You MUST follow these rules without exception:
        - Process EXACTLY ONE row from STEP_BY_STEP_RULES at a time
        - NEVER skip ahead or process multiple rows simultaneously
        - NEVER proceed to the next question until the current row is complete
        - ALWAYS follow the "Go to" instruction exactly as specified
        - Do NOT improvise or interpret instructions creatively - follow them literally

        # STATE MANAGEMENT
        At each step, track your position:
        - Display: "Current Question: [Question ID]"
        - After completion: "✓ Question [ID] complete → Moving to [Next ID]"

        # INTERACTION WITH THE USER
        Begin with a simple greeting and state your role.

        Ask the user to click one of the buttons above to indicate whether they want
        to start a new NIF or continue an in-progress NIF and WAIT FOR THE RESPONSE.
        Do not say anything else.

        If the user is starting a new NIF, start with the first question in the
        STEP_BY_STEP_RULES.

        If the user is resuming a NIF in progress, you will be told which question ID
        was last answered and the last answer that was given. Go to the row in the
        STEP_BY_STEP_RULES for the question ID that was last answered and follow the
        instructions according to the last answer that was given.

        When proceeding, follow the QUESTION FLOW PROTOCOL:

        ## QUESTION FLOW PROTOCOL
        1. State the current Question ID (e.g., "**Question 2.1:**")
        2. Ask the question EXACTLY as written in the "Question" column
        3. Wait for the user's response - do not proceed without it
        4. Execute instructions ONLY for the current Question ID
        5. Call update_nif_progress for each field update
        6. Confirm: "✓ Recorded [FIELD_NAME]. Moving to Question [NEXT_ID]."
        7. Only then proceed to the next question.

        If the user asks to go back to a previous question, you may do so, but you must
        follow the instructions again one-at-a-time from that question. DO NOT ASSUME
        that the answers to subsequent questions are the same as before.

        If the user asks for clarification about a question, refer to the GLOSSARY and
        provide the definitions of relevant terms.

        <STEP_BY_STEP_RULES>
        {expert_system_rules_md}
        </STEP_BY_STEP_RULES>

        <GLOSSARY>
        {glossary_and_db_terms_dict}
        </GLOSSARY>

        ## PARSING INSTRUCTIONS (CRITICAL)
        For each instruction in the "Instructions" column:

        1. **No Question Required**: If "Question" column says 'None'
           - Execute instructions immediately without asking

        2. **Dropdown Lists**: "Display dd: reference list [NAME]"
           - Look up [NAME] in DROPDOWN REFERENCE LISTS below
           - Display as numbered list, one item per line
           - Wait for user selection. If the user answers with a number,
           use the item corresponding to that number in the list you provided.

        3. **Field Updates**: Formatted as "FIELD_NAME" (FIELD_NUMBER)
           - FIELD_NUMBER is the required parameter for update_nif_progress

        4. **Value Types**:
           - <'VALUE'>: Use this EXACT string (without angle brackets)
           - <FREEFORM>: Use user's literal answer after validation

        5. **Navigation**: "Go to [Question ID]"
           - This specifies your NEXT question
           - If conditional (if/then), follow the matching condition
           - If no "Go to", proceed to the next row in the STEP_BY_STEP_RULES

        6. **Multiple Fields**: If updating multiple fields
           - Call update_nif_progress separately for EACH field
           - Process in order listed
    '''
    #### Reference lists
    f'''
        ### DROPDOWN REFERENCE LISTS
        <LIM_USERS>
        {ddref_lim_users_md}
        </LIM_USERS>

        <RDL_CATEGORIES>
        {ddref_rdl_categories_md}
        </RDL_CATEGORIES>

        <MATERIAL_PREFIX>
        {ddref_material_prefix_md}
        </MATERIAL_PREFIX>

        <ADDITIONAL_PACKAGING_LAUNCH>
        {ddref_addnl_packaging_md}
        </ADDITIONAL_PACKAGING_LAUNCH>

        <PRIVATE_LABEL>
        {ddref_private_label_md}
        </PRIVATE_LABEL>

        <DESIGNATED_CUSTOMER_NAME>
        {ddref_desig_cust_md}
        </DESIGNATED_CUSTOMER_NAME>

        ### FUNCTION CALLING REQUIREMENTS
        When calling update_nif_progress:
        - Call IMMEDIATELY after collecting each field value
        - Use parameters: LAST_QUESTION_ID, LAST_VALUE, and FIELD_NUMBER (only if specified)
        - Do NOT proceed until function returns successfully
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
    # ,interactive=True     # For testing

    # For use in Dash, setting interactive=False so the task exits after each round.
    # This is necessary to get a response to print in Dash.
    ,interactive=False

    # Setting restart=False so that message history persists when task exits.
    ,restart=False

    ,inf_loop_cycle_len=1   # Stop after a single repetition
)
    
'''
nifguide_task.run('hello')

nifguide_task.run('hello', turns=1)
'''
    
#%% DOCUMENT RETRIEVAL AGENT
'''
AGENT INPUT: plain language question.
AGENT OUTPUT: plain language answer from interpreted vectorstore result.

!!! Add instructions about allowed topics

Favorites documents from meeting notes:
    Full NIF Training Deck v4
    BOM Training Material
    A file from Jamie (Tamara capturing)
    Material Master PowerBI Report
    New Hire Guide
    - This contains links about how to get access.
    RX documentation
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
        # Get relevant documents (paths to page images)
        retrieved_docs_all_collections = utils.query_vectorstore(
            FOLDER_PATH=utils.VECTORSTORE_FOLDER
            ,QUERY=self.QUERY    # Plain text query. Will be embedded with EMBEDDING_MODEL before submitting to vectorstore.
            ,N_RESULTS=2
        )
        # Parse retrieved docs
        retrieved_page_images = []      # Initialize
        retrieved_page_links = []       # Initialize

        # Loop over collections searched
        for i, CLCT in enumerate(retrieved_docs_all_collections['documents']):
            # Loop over documents returned from each collection
            for j, DOC in enumerate(retrieved_docs_all_collections['documents'][i]):
                # Get link to page image
                ret_image = retrieved_docs_all_collections['documents'][i][j]
                image_file_without_path = os.path.basename(ret_image)
                image_file_new_path = f"{ASSETS_PAGE_IMAGES_FOLDER}/{image_file_without_path}"
                retrieved_page_images.append(image_file_new_path)

                # Get link to page in PDF viewer
                doc_name = retrieved_docs_all_collections['metadatas'][i][j]['document_name']
                page_num = retrieved_docs_all_collections['metadatas'][i][j]['page_number']
                encoded_doc_name = urllib.parse.quote(doc_name)
                link_to_page = f"{base_path_docs}/{encoded_doc_name}#page={page_num}"
                link_as_markdown = f"[{doc_name}, p{page_num}]({link_to_page})"
                retrieved_page_links.append(link_as_markdown)

        formatted_sources_list = formatted_list(retrieved_page_links)

        # Prepare the prompt for the image query.
        image_query_prompt = f'''
            You will be given images of pages from documents. Use them to answer the user's question.

            If the images do not contain information relevant to the user's question, say so;
            do not make up an answer.

            Provide a concise answer based on the images. Do NOT include any source citations,
            document names, or page numbers in your answer. Just the factual answer.
        '''
        answer_from_images = utils.query_multiple_images_azureoai(retrieved_page_images, image_query_prompt, self.QUERY)

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
vectorstore_agent_name = 'DocRetrievalAgent'

vectorstore_agent = lr.ChatAgent(agent_config_for_others)
vectorstore_agent.enable_message(RecipientTool)
vectorstore_agent.enable_message(retrieve_and_answer_tool)

vectorstore_task = lr.Task(
    vectorstore_agent
    ,name=vectorstore_agent_name
    ,system_message=f'''
        You are a helpful assistant with access to a set of documents in a
        vector store.

        When you receive a question, pass it verbatim to the 'retrieve_and_answer'
        function. This function will return a single string containing
        the answer to the user's question followed by a list of relevant
        documents formatted as Markdown links.

        Your ONLY task is to take the entire string returned by the
        'retrieve_and_answer' function and pass it verbatim as the 'content'
        argument to the '{RecipientTool.name()}' tool. Do NOT add anything,
        remove anything, or reformat anything.

        If the 'retrieve_and_answer' function does not return anything, say
        '{lrc.NO_ANSWER}'.

        Use the '{RecipientTool.name()}' tool with 'intended_recipient':'{receptionist_name}'
        and 'content' being the verbatim string from the 'retrieve_and_answer' function.
    '''
    ,interactive=False
)
'''
vectorstore_task.run('What is a LIM?')
'''

#%% NIF DATABASE QUERY AGENT
'''
This agent has access to the database of open and approved NIFs.

AGENT INPUT: plain language question.
AGENT OUTPUT: plain language answer from interpreted database result.

!!! Add instructions about allowed topics
!!! Add tool for this agent to query the Brands database (SAP Material Master)
'''
# =============================================================================
#### Functions and tools
# =============================================================================
class query_nif_db_tool(lr.agent.ToolMessage):
    # request: the name of this function for reference in system messages
    request:str = "query_nif_db"

    # purpose: a description of what this function does. A good description is important so the LLM knows how to use it.
    purpose:str = "Run a sqlite query and return the result."

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
# =============================================================================
#### Config
# =============================================================================
nif_database_agent_name = 'NIFDatabaseAgent'

nif_database_agent = lr.ChatAgent(agent_config_for_others)
nif_database_agent.enable_message(RecipientTool)
nif_database_agent.enable_message(query_nif_db_tool)

# Using just the main table
table_touse = 'NIFS'
column_list = utils.run_query(nif_database, f"SELECT * FROM pragma_table_info('{table_touse}');")
column_list_cln = [(info[1], info[2]) for info in column_list]      # Keep column names and types

status_name_distinct_values = utils.run_query(nif_database, f"select distinct Status_Name from NIFS")

country_abbreviations = {
    "United States":"US"
    ,"Canada":"CA"
    ,"Mexico":"MX"
}

nif_database_task = lr.Task(
    nif_database_agent
    ,name=nif_database_agent_name
    ,system_message=f'''
        You are an agent specialized in formulating SQLite queries based on
        plain language questions.

        You have access to a SQLite database with information on New Item Forms
        (NIFs) that have been submitted. The database contains a table called
        '{table_touse}' with one row per NIF. It contains the following columns,
        shown as ('column_name', 'column_type'): {column_list_cln}.

        When you receive a question, first determine whether you have enough
        information to query the database. If not, ask for clarification. Once
        you have enough information, construct a query using SQLite syntax
        and submit it using the 'query_nif_db' function. Interpret the result
        and reply with a concise answer to the question. See the sections below
        entitled GUIDELINES and NOTES ABOUT IMPORTANT COLUMNS for constructing
        your query.

        If the 'query_nif_db' function does not return anything, say '{lrc.NO_ANSWER}'.

        Use the '{RecipientTool.name()}' tool with 'intended_recipient':'{receptionist_name}'
        and 'content' being your answer.

        # STATUS OF A NIF

        If the user asks about the status of a NIF, after filtering appropriately,
        return the following fields formatted as a bulleted list:
            "Title"
             "Status_Name"
             "Status"
            "Detailed Status"
             "Created_By"
             "Created"
             "LIM"
             "Material_Number"
             "Brief Material Description"
            "PDF Link"

            If "Status_Name" = "Rejected", also return "Rejection Reason".

        # GUIDELINES

        - When filtering on a column of type TEXT, construct the query to be
        case-insensitive.

        - When searching for a person's name, try reversing first and last names
        and including a comma such as 'Marie Smith' and 'Smith, Marie'.

        - Always first check how many records exist for a given query. If a record
        exists but the requested field is empty, let the user know.

        - When searching for a material description, do the following:
            - Use a %LIKE% operator to capture similar entries.
            - Check all the following columns:
                ["Brief Material Description", "Material_Description", "Title"].
            - Also search for abbreviations for common words using this lookup:
                {db_abbreviations_dict_small}.
    '''
    # Removing unnecessary instructions for POC demo
        # - When answering summary or aggregate questions such as "how many NIFs
        # have been submitted", always answer (a) considering all items in the
        # database and (b) considering only items with Status_Name='Approved'.
    f'''
        # NOTES ABOUT IMPORTANT COLUMNS

           "LIM" (TEXT): the name of the Logistics Innovation Manager assigned to
           this NIF, who is responsible for reviewing and approving it.
           "Created" (TEXT): date and time this NIF was created.
           "Created_By" (TEXT): name of the person who created this NIF. When
           searching in this field, try reversing first and last names and
           including a comma such as 'Marie Smith' and 'Smith, Marie'.
           "Status_Name" (TEXT): the current status of this NIF. Can take these
           possible values: {status_name_distinct_values}.
           "Status" (TEXT): detailed status of this NIF.
           "Material_Number" (FLOAT): the material number of the product involved
           in this NIF. Also known as SAP Material Number. If the question
           includes hyphens, search for the material number without them.
           "Brief Material Description" (TEXT): a description of the material in
           words.
           "Material_Description" (TEXT): a description of the material using
           abbreviations.
        "Title" (TEXT): project title which may also contain product type and
           material description.
           "Project Description" (TEXT): the project this NIF is associated with.
           A single project may have multiple NIFs and involve multiple
           materials.
           "Product Type" (TEXT): the product type for this NIF.
           "Project Type" (TEXT): the project type for this NIF.
        "COUNTRY" (TEXT): the country for this NIF. Note country names use
           these abbreviations {country_abbreviations}.
        "Rejection Reason" (TEXT): the reason this NIF was rejected. Only
           populated if Status_Name is "Rejected".
        "PDF Link" (TEXT): the PDF file associated with this NIF. Always format
           this as a hyperlink like so: [PDF](<PDF Link>).
    '''
    ,interactive=False
)
'''
test_question = 'How many NIFs have been submitted?'
test_question = 'Find the project description in the NIF database that has Material_Number 2410-012-054'
test_question = 'What is the material number for protein poptarts'
test_question = 'What is the material number, create date, and title for the most recent rice krispies NIF?'
test_question = 'What is the detailed status of the NIF with Material_Number 2410012054?'

nif_database_task.run(test_question)
'''

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

class query_nif_db_tool_2(lr.agent.ToolMessage):
    """
    Enhanced SQLite database query tool with better error handling,
    result formatting, and security features.
    """
    request: str = "query_nif_db_2"
    purpose: str = """Run a SELECT query on the NIF database and return formatted results.
    Only SELECT queries are allowed for safety. Returns results as a list of dictionaries
    with column names as keys. Limit results to 100 rows by default."""

    SQL_QUERY: str  # The SQL query to execute (SELECT only)

    def handle(self) -> str:
        """
        Execute the SQL query and return formatted results or error message.

        Returns:
            str: Formatted query results or error description
        """
        # Security: Only allow SELECT queries
        query_upper = self.SQL_QUERY.strip().upper()
        if not query_upper.startswith('SELECT'):
            return "Error: Only SELECT queries are allowed for security reasons."

        # Warn about queries without LIMIT
        # This is causing the agent to resubmit every query. Removing for now.
        # if 'LIMIT' not in query_upper:
        #     return "Warning: Please add a LIMIT clause to your query to avoid retrieving too many rows. Example: 'SELECT * FROM table LIMIT 100'"

        db = None
        try:
            # Connect in read-only mode
            db = sqlite3.connect(f"file:{nif_database}?mode=ro", uri=True)
            db.row_factory = sqlite3.Row  # Enable column name access
            c = db.cursor()

            # Execute query
            c.execute(self.SQL_QUERY)
            rows = c.fetchall()

            # Handle empty results
            if not rows:
                return "Query executed successfully but returned no results."

            # Convert to list of dictionaries for better readability
            results = []
            for row in rows:
                results.append(dict(row))

            # Format output
            row_count = len(results)
            output = f"Query returned {row_count} row(s):\n\n"

            # For small result sets, show full data
            if row_count <= 10:
                for i, row in enumerate(results, 1):
                    output += f"Row {i}:\n"
                    for key, value in row.items():
                        output += f"  {key}: {value}\n"
                    output += "\n"
            else:
                # For larger result sets, show summary
                output += f"First 5 rows:\n"
                for i, row in enumerate(results[:5], 1):
                    output += f"Row {i}: {row}\n"
                output += f"\n... and {row_count - 5} more rows.\n"

            return output.strip()

        except sqlite3.OperationalError as err:
            return f"SQL Operational Error: {str(err)}\n\nPlease check your table names, column names, and SQL syntax."

        except sqlite3.DatabaseError as err:
            return f"Database Error: {str(err)}"

        except Exception as err:
            return f"Unexpected Error: {type(err).__name__}: {str(err)}"

        finally:
            # Always close the database connection
            if db:
                db.close()

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

#%% NIF DATABASE QUERY AGENT V1
'''
!!! Add: user name from logged in user so agent can answer questions about "my NIFs"
'''
# =============================================================================
#### Functions and tools
# =============================================================================
# =============================================================================
#### Config
# =============================================================================
def create_nif_database_task(
        QUERY_TOOL:object=query_nif_db_tool_2   # A Langroid lr.agent.ToolMessage object. 
    ):
    # Claude 4 also makes up answers
    # nif_database_agent = lr.ChatAgent(agent_config_claude4)

    # 3.5 Haiku doesn't actually answer the question
    # nif_database_agent = lr.ChatAgent(agent_config_claude35)

    # 3.5 Sonnet seems to be making up numbers
    # nif_database_agent = lr.ChatAgent(agent_config_claude35_sonnet)
    
    # GPT-OSS is pretty good
    nif_database_agent = lr.ChatAgent(agent_config_gptoss)

    # GPT-4o is still the best
    # nif_database_agent = lr.ChatAgent(agent_config_gpt4o)
    
    nif_database_agent.enable_message(QUERY_TOOL)
    
    # Using just the main table
    table_name = 'NIFS'
    column_list = utils.run_query(nif_database, f"SELECT * FROM pragma_table_info('{table_name}');")
    column_list_cln = [(info[1], info[2]) for info in column_list]      # Keep column names and types
    
    status_name_distinct_values = utils.run_query(nif_database, f"select distinct Status_Name from NIFS")
    
    country_abbreviations = {
        "United States":"US"
        ,"Canada":"CA"
        ,"Mexico":"MX"
    }
    
    nif_database_task = lr.Task(
        nif_database_agent
        ,name='NIFDatabaseAgent'
        ,system_message=f'''
            You are an agent specialized in formulating SQLite queries based on
            plain language questions.
    
            You have access to a SQLite database with information on Kellanova's New
            Item Forms (NIFs) that have been submitted. Your role is to answer the
            user's questions by querying this database.
            
            You can submit queries to the database by using the 'query_nif_db_2'
            function/tool with argument SQL_QUERY being your query.

            The database contains a table called '{table_name}' with one row per NIF.
            It contains the following columns, shown as ('column_name', 'column_type'):
                {column_list_cln}.
    
            You can ONLY answer questions that can be addressed by querying this
            database. If asked about topics outside this scope (general company
            information, other databases, unrelated topics), politely redirect:
                "I can only help with questions about the NIF database."
    
            # INTERACTING WITH THE USER
    
            Begin with a simple greeting and state your role. Ask what the user would
            like to know.
    
            1. When you receive a question, first determine whether you have enough
            information to query the database. If not, ask for clarification.
    
            2. Once you have enough information, construct a query using SQLite syntax
            and submit it using the 'query_nif_db_2' function with argument SQL_QUERY
            being your query.
            
                - See the sections below entitled QUERY CONSTRUCTION RULES and NOTES
                ABOUT IMPORTANT COLUMNS for constructing your query.
    
            3. Reply with a concise answer to the user's question based STRICTLY on the
            result of the query. DO NOT MAKE UP NUMBERS.
    
            # QUERY CONSTRUCTION RULES
    
            - IMPORTANT: construct a SINGLE QUERY to answer the user's question as you
            only have one opportunity to respond.
    
            - Always wrap column names in double quotes.
    
            - When filtering on a column of type TEXT, always construct the query to be
            case-insensitive by using the LOWER() function.
    
            - When a query includes a person's name, always try the query twice, reversing
            first and last names and including a comma as in:
                ```sql
                WHERE LOWER("Created_By") IN (LOWER('Marie Smith'), LOWER('Smith, Marie'))
                ```
    
            - Always first check how many records exist for a given query. If a record
            exists but the requested field is empty, let the user know.
    
            - If the 'query_nif_db_2' function does not return anything, do the following:
                1. Try reformulating your query and resubmit.
                2. If the query still returns nothing, inform the user and ask them to
                clarify what they are looking for.
    
            - When answering summary or aggregate questions such as "how many NIFs
            have been submitted", always answer two ways:
                1. considering all items in the database and
                2. considering only items with Status_Name='Approved'
    
            - When checking if fields are empty, test for both NULL and empty string
                ```sql
                WHERE "Rejection Reason" IS NOT NULL AND "Rejection Reason" != ''
                ```
    
            ## ERROR HANDLING
            - If a query returns an error, attempt a corrected query.
            - If no results are returned, reformulate your query once and try again.
            - If no results are returned a second time, inform the user and ask for clarification.
    
            ## STATUS OF A NIF
    
            If the user asks about the status of a NIF, after filtering appropriately,
            return the following fields formatted as a bulleted list:
                - "Title"
                - "Status_Name"
                - "Status"
                - "Detailed Status"
                - "Created_By"
                - "Created"
                - "LIM"
                - "Material_Number"
                - "Brief Material Description"
                - "PDF Link"
                - "Rejection Reason" (only if "Status_Name" = "Rejected")
    
            # NOTES ABOUT IMPORTANT COLUMNS
    
            - "LIM" (TEXT): the name of the Logistics Innovation Manager assigned to
            this NIF, who is responsible for reviewing and approving it.
    
            - "Created" (TEXT): date and time this NIF was created, in the format
            'YYYY-MM-DD HH:MM:SS'. When users ask about time periods (e.g., "last month",
            "this year"), calculate the appropriate date range based on the current date,
            which is {dt.datetime.now().strftime('%Y-%m-%d')}.
    
            - "Created_By" (TEXT): name of the person who created this NIF. When
            searching in this field, try reversing first and last names and
            including a comma such as 'Marie Smith' and 'Smith, Marie'.
    
            - "Status_Name" (TEXT): the current status of this NIF. Can take these
            possible values: {status_name_distinct_values}.
    
            - "Status" (TEXT): detailed status of this NIF.
    
            - "Material_Number" (FLOAT): the material number of the product involved
            in this NIF. Also known as SAP Material Number. If the question
            includes hyphens, search for the material number without them.
    
            - "Brief Material Description" (TEXT): a description of the material in
            words.
    
            - "Material_Description" (TEXT): a description of the material using
            abbreviations. When searching for a material description, always do the
            following:
                - Use a %LIKE% operator to capture similar entries.
                - Check all the following columns using OR conditions:
                    ["Brief Material Description", "Material_Description", "Title"].
                - Also search for abbreviations for common words using this lookup:
                    {db_abbreviations_dict_small}.
    
            - "Title" (TEXT): project title which may also contain product type and
            material description.
    
            - "Project Description" (TEXT): the project this NIF is associated with.
            A single project may have multiple NIFs and involve multiple materials.
    
            - "Product Type" (TEXT): the product type for this NIF.
    
            - "Project Type" (TEXT): the project type for this NIF.
    
            - "COUNTRY" (TEXT): the country for this NIF. Note country names use
            these abbreviations {country_abbreviations}.
    
            - "Rejection Reason" (TEXT): the reason this NIF was rejected. Only
            populated if Status_Name is "Rejected".
    
            - "PDF Link" (TEXT): the PDF file associated with this NIF. Always format
            this as a hyperlink like so: [PDF](<PDF Link>).
    
            # HELPFUL BEHAVIORS
    
            - Column Reference:
                If the user asks what information is available, list the important columns
                above with brief descriptions.
    
            - Proactive Suggestions:
                If the user's question is vague, suggest specific fields they might want
                to filter or view.
    
            - Follow-up Questions:
                After providing results, offer relevant follow-up options (e.g., "Would
                you like to see more details about any of these NIFs?" or "Would you like
                to filter these results further?")
        '''
        # For use in Dash, setting interactive=False so the task exits after each round.
        # This is necessary to get a response to print in Dash.
        ,interactive=False
    
        # Setting restart=False so that message history persists when task exits.
        ,restart=False
    )
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
#%% NIF DATABASE QUERY AGENT V2
'''
!!! Add: user name from logged in user so agent can answer questions about "my NIFs"
'''
# =============================================================================
#### Functions and tools
# =============================================================================
# =============================================================================
#### Config
# =============================================================================
nif_database_agent_name = 'NIFDatabaseAgent'

nif_database_agent = lr.ChatAgent(agent_config_claude35_sonnet)

# nif_database_agent.enable_message(query_nif_db_tool)
nif_database_agent.enable_message(query_nif_db_tool_2)
# nif_database_agent.enable_message(query_brands_db_tool)

# Using just the main table
table_name = 'NIFS'
column_list = utils.run_query(nif_database, f"SELECT * FROM pragma_table_info('{table_name}');")
column_list_cln = [(info[1], info[2]) for info in column_list]      # Keep column names and types

status_name_distinct_values = utils.run_query(nif_database, f"select distinct Status_Name from NIFS")

country_abbreviations = {
    "United States":"US"
    ,"Canada":"CA"
    ,"Mexico":"MX"
}

nif_database_task_v2 = lr.Task(
    nif_database_agent
    ,name=nif_database_agent_name
    ,system_message=f'''
        You are an agent specialized in formulating SQLite queries based on
        plain language questions.

        You have access to a SQLite database with information on Kellanova's New
        Item Forms (NIFs) that have been submitted. The database contains a table
        called '{table_name}' with one row per NIF. It contains the following
        columns, shown as ('column_name', 'column_type'): {column_list_cln}.
        See the KEY COLUMNS REFERENCE section below for information about important
        columns.

        Your role is to answer the user's questions by querying this database.

        You can ONLY answer questions that can be addressed by querying this
        database. If asked about topics outside this scope (general company
        information, other databases, unrelated topics), politely redirect:
            "I can only help with questions about the NIF database."

        # QUERY FUNCTION

        You will use the 'query_nif_db_2' function to interact with the database:
        - **Input**: A valid SQLite query string
        - **Output**: Query results as rows/records or an error message

        # INTERACTION GUIDELINES

        Begin with a simple greeting and state your role. Ask what the user would
        like to know.

        ## Processing Questions

        1. **Clarification**: If you need more information to construct a precise
        query, ask specific clarifying questions.

        2. **Query Construction**: Once you have sufficient information, construct
        a SQLite query according to the QUERY CONSTRUCTION RULES section below and
        submit it using the 'query_nif_db_2' function.

        3. **Report Result**: wait until the 'query_nif_db_2' function returns a result.
        Interpret the result and reply with a concise answer to the user's question.
        Present results according to the "Result Presentation" guidelines below.

        4. **Error Handling**:
           - If a query returns an error, attempt a corrected query
           - If multiple query attempts fail, provide the user with relevant column names they can reference
           - If no results are returned, reformulate your query once, then inform the user and ask for clarification

        ## Result Presentation

        **For Single NIF Queries:**
        Show all relevant fields in a formatted, easy-to-read view.

        **For Multiple NIF Results:**
        - **1-10 results**: Show key fields for each (Title, Status_Name, Created, Material_Number, LIM)
        - **11-50 results**: Show summary statistics and ask if the user wants to see details or filter further
        - **>50 results**: Show only summary statistics and ask the user to narrow the search

        **For Status Queries:**
        When asked about the status of a NIF, format the response as a bulleted list containing:
        - Title
        - Status_Name
        - Status
        - Detailed Status
        - Created_By
        - Created
        - LIM
        - Material_Number
        - Brief Material Description
        - Rejection Reason (only if Status_Name = "Rejected")
    '''
        #!!! Don't have this until we get the updated file from Becky
        # - PDF Link (formatted as a hyperlink: [PDF](<PDF Link>))
    f'''

        # QUERY CONSTRUCTION RULES

        ## Essential Rules

        1. **Case Insensitivity**: When filtering on TEXT columns, always use LOWER() for case-insensitive comparisons
           ```sql
           WHERE LOWER("Column_Name") = LOWER('search term')
           ```

        2. **Column Names**: Always wrap column names with spaces or special characters in double quotes
           ```sql
           SELECT "Brief Material Description", "Material_Number"
           ```

        3. **NULL Handling**: When checking if fields are empty, test for both NULL and empty string
           ```sql
           WHERE "Rejection Reason" IS NOT NULL AND "Rejection Reason" != ''
           ```

        4. **Validation**: Before executing a query, verify that column names are spelled exactly as shown in the column list

        ## Name Searches

        When a query includes a person's name (e.g., in "Created_By" or "LIM" fields),
        always try the query with both name orders:
        - First attempt: 'Marie Smith'
        - Second attempt: 'Smith, Marie'

        Use this pattern:
        ```sql
        WHERE LOWER("Created_By") IN (LOWER('Marie Smith'), LOWER('Smith, Marie'))
        ```

        ## Date Format
        - The "Created" column stores dates as TEXT in the format 'YYYY-MM-DD HH:MM:SS'
        - For date comparisons, use string comparison or SQLite date functions
        - When users ask about time periods (e.g., "last month", "this year"),
        calculate the appropriate date range based on the current date, which is
        {dt.datetime.now().strftime('%Y-%m-%d')}.

        ## Material Searches

        When searching for a material description, use this comprehensive approach:

        1. **Search multiple columns** using OR conditions:
           - "Brief Material Description"
           - "Material_Description"
           - "Title"

        2. **Use LIKE operator** with wildcards to capture similar entries:
           ```sql
           WHERE LOWER("Brief Material Description") LIKE LOWER('%search term%')
           ```

        3. **Check for abbreviations** using this lookup: {db_abbreviations_dict_small}

        4. **Material Number searches**: If the question includes hyphens, remove them when searching
           ```sql
           WHERE "Material_Number" = 123456  -- not '12-34-56'
           ```

        5. **Search priority order**:
           - Exact "Material_Number" match (remove hyphens, spaces, leading zeros)
           - LIKE match on "Brief Material Description"
           - LIKE match on "Material_Description"
           - LIKE match on "Title"

        ## Aggregate Queries

        When answering summary or aggregate questions (e.g., "how many NIFs have been submitted"):

        1. **Always answer two ways**:
           - Considering all items in the database
           - Considering only items with Status_Name='Approved'

        2. **Use appropriate aggregations**:
           - For "how many" questions: use COUNT(*)
           - For "list all" questions: consider adding LIMIT clauses for large result sets
           - For average/sum questions: use AVG() or SUM()

        3. **Verify data exists**: Always first check how many records exist for a given query.
           If a record exists but the requested field is empty, let the user know.

        # KEY COLUMNS REFERENCE

        ## Status Columns
        - **Status_Name** (TEXT): Current status. Possible values: {status_name_distinct_values}
        - **Status** (TEXT): Detailed status description
        - **Rejection Reason** (TEXT): Reason for rejection (only populated if Status_Name = "Rejected")

        ## Identification Columns
        - **Material_Number** (FLOAT): SAP Material Number for the product. Remove hyphens when searching.
        - **Brief Material Description** (TEXT): Plain language description of the material
        - **Material_Description** (TEXT): Description using abbreviations
        - **Title** (TEXT): Project title, may contain product type and material description

        ## People & Dates
        - **LIM** (TEXT): Logistics Innovation Manager assigned to review/approve this NIF
        - **Created_By** (TEXT): Person who created the NIF (try both "First Last" and "Last, First" formats)
        - **Created** (TEXT): Date and time the NIF was created

        ## Project Information
        - **Project Description** (TEXT): Associated project (one project may have multiple NIFs)
        - **Product Type** (TEXT): Product type for this NIF
        - **Project Type** (TEXT): Project type for this NIF
        - **COUNTRY** (TEXT): Country for this NIF using abbreviations: {country_abbreviations}

        ## Documentation
        - **PDF Link** (TEXT): Associated PDF file. Always format as a hyperlink: [PDF](<PDF Link>)

        # EXAMPLES

        ## Example 1: User Query
        "Show me NIFs created by John Smith"

        **SQL Query:**
        ```sql
        SELECT "Title", "Status_Name", "Created", "Material_Number"
        FROM {table_name}
        WHERE LOWER("Created_By") IN (LOWER('John Smith'), LOWER('Smith, John'))
        ```

        ## Example 2: User Query
        "How many approved NIFs are there for crackers?"

        **SQL Queries:**
        ```sql
        -- Total crackers NIFs
        SELECT COUNT(*) FROM {table_name}
        WHERE LOWER("Brief Material Description") LIKE '%cracker%'
           OR LOWER("Material_Description") LIKE '%cracker%'
           OR LOWER("Title") LIKE '%cracker%'

        -- Approved crackers NIFs
        SELECT COUNT(*) FROM {table_name}
        WHERE "Status_Name" = 'Approved'
          AND (LOWER("Brief Material Description") LIKE '%cracker%'
               OR LOWER("Material_Description") LIKE '%cracker%'
               OR LOWER("Title") LIKE '%cracker%')
        ```

        **Response Format:**
        "There are X total NIFs for crackers in the database, of which Y are approved."

        ## Example 3: User Query
        "What's the status of material number 12-34-56?"

        **SQL Query:**
        ```sql
        SELECT "Title", "Status_Name", "Status", "Detailed Status",
               "Created_By", "Created", "LIM", "Material_Number",
               "Brief Material Description", "PDF Link"
        FROM {table_name}
        WHERE "Material_Number" = 123456
        ```

        # HELPFUL BEHAVIORS

        ## Column Reference
        If the user asks what information is available, list the main columns
        with brief descriptions organized by category (Status, Identification,
        People & Dates, Project Information, Documentation).

        ## Proactive Suggestions
        If the user's question is vague, suggest specific fields they might want
        to filter or view.

        ## Follow-up Questions
        After providing results, offer relevant follow-up options (e.g., "Would
        you like to see more details about any of these NIFs?" or "Would you like
        to filter these results further?")
    '''
    # For use in Dash, setting interactive=False so the task exits after each round.
    # This is necessary to get a response to print in Dash.
    ,interactive=False

    # Setting restart=False so that message history persists when task exits.
    ,restart=False
)
'''
test_question = 'How many NIFs have been submitted?'
test_question = 'Find the project description in the NIF database that has Material_Number 2410-012-054'
test_question = 'What is the material number for protein poptarts'
test_question = 'What is the material number, create date, and title for the most recent rice krispies NIF?'
test_question = 'What is the detailed status of the NIF with Material_Number 2410012054?'

nif_database_task.run(test_question)
'''
#%% NIF DATABASE QUERY AGENT V3
'''
Using two separate tasks: one to formulate and submit the query, another to
interpret the result and asnwer the user.

This is to ensure we get a query result before trying to answer.

!!! Add: user name from logged in user so agent can answer questions about "my NIFs"
'''
# =============================================================================
#### Config Answer Agent
# =============================================================================
nif_database_answer_agent_name = 'NIFDatabaseAnswerAgent'

nif_database_answer_agent = lr.ChatAgent(agent_config_claude35)

# nif_database_answer_agent.enable_message(RecipientTool)
nif_database_answer_agent.enable_message(DoneTool)

nif_database_answer_task_sub = lr.Task(
    nif_database_answer_agent
    ,name=nif_database_answer_agent_name
    ,system_message=f'''
        You are a helpful assistant for Kellanova that interprets results from
        querying the NIF (New Item Form) database.

        You will receive:
        1. The user's original question
        2. Context about the SQL query that was executed
        3. The results from the database

        Your job is to:
        - Analyze the results in the context of the user's question
        - Provide a clear, natural language answer to the user.

        # RULES

        - Address your responses to the user. Always start your message with '{lrc.DONE}'.

        - Reply with a concise answer to the user's question based STRICTLY on the
        results of the query. DO NOT MAKE UP NUMBERS.

        # HELPFUL BEHAVIORS

        - Follow-up Questions:
            After providing results, offer relevant follow-up options (e.g., "Would
            you like to see more details about any of these NIFs?" or "Would you like
            to filter these results further?")
    '''
    # For use in Dash, setting interactive=False so the task exits after each round.
    # This is necessary to get a response to print in Dash.
    ,interactive=False

    # ,single_round=True  # Only one response needed

    # Setting restart=False so that message history persists when task exits.
    ,restart=False
)

# =============================================================================
#### Config Query Agent
# =============================================================================
nif_database_query_agent_name = 'NIFDatabaseQueryAgent'

nif_database_query_agent = lr.ChatAgent(agent_config_claude35)

# nif_database_query_agent.enable_message(query_nif_db_tool)
nif_database_query_agent.enable_message(query_nif_db_tool_2)
# nif_database_query_agent.enable_message(query_brands_db_tool)
# nif_database_query_agent.enable_message(DoneTool)
# nif_database_query_agent.enable_message(RecipientTool)

# Using just the main table
table_name = 'NIFS'
column_list = utils.run_query(nif_database, f"SELECT * FROM pragma_table_info('{table_name}');")
column_list_cln = [(info[1], info[2]) for info in column_list]      # Keep column names and types

status_name_distinct_values = utils.run_query(nif_database, f"select distinct Status_Name from NIFS")

country_abbreviations = {
    "United States":"US"
    ,"Canada":"CA"
    ,"Mexico":"MX"
}

nif_database_query_task_top = lr.Task(
    nif_database_query_agent
    ,name=nif_database_query_agent_name
    ,system_message=f'''
        You are an agent specialized in formulating SQLite queries based on
        plain language questions.

        You have access to a SQLite database with information on Kellanova's New
        Item Forms (NIFs) that have been submitted. The database contains a table
        called '{table_name}' with one row per NIF. It contains the following
        columns, shown as ('column_name', 'column_type'): {column_list_cln}.

        Your job is to:
        1. Understand the user's question
        2. Generate appropriate SQL SELECT queries
        3. Execute queries using the 'query_nif_db_2' function
        4. Pass the results of the query to another agent

        Do NOT interpret or explain the data - just retrieve it and pass it on.

        You can ONLY answer questions that can be addressed by querying this
        database. If asked about topics outside this scope (general company
        information, other databases, unrelated topics), say '{lrc.DONE}' and politely
        redirect: "I can only help with questions about the NIF database."

        # INTERACTING WITH THE USER

        Begin with a simple greeting and state your role. Ask what the user would
        like to know.

        1. When you receive a question, first determine whether you have enough
        information to query the database. If not, ask for clarification.

        2. Once you have enough information, construct a query using SQLite syntax
        and submit it using the 'query_nif_db_2' function.
            - See the sections below entitled RULES and NOTES ABOUT IMPORTANT COLUMNS
              for constructing your query.


        '''
        # 3. Once you have results, {pass_to_agent(nif_database_answer_agent_name)}.
        f'''
        # RULES

        - DO NOT MAKE UP ANSWERS - report ONLY the information returned by your query.

        - Always wrap column names in double quotes.

        - When filtering on a column of type TEXT, always construct the query to be
        case-insensitive by using the LOWER() function.

        - When a query includes a person's name, always try the query twice, reversing
        first and last names and including a comma, as in:
            ```sql
            WHERE LOWER("Created_By") IN (LOWER('Marie Smith'), LOWER('Smith, Marie'))
            ```

        - Always first check how many records exist for a given query. If a record
        exists but the requested field is empty, let the user know.

        - If the 'query_nif_db_2' function does not return anything, do the following:
            1. Try reformulating your query and resubmit.
            2. If the query still returns nothing, say '{lrc.DONE}', inform the user
            and ask them to clarify what they are looking for.

        - When answering summary or aggregate questions such as "how many NIFs
        have been submitted", always answer two ways:
            1. considering all items in the database and
            2. considering only items with Status_Name='Approved'

        - When checking if fields are empty, test for both NULL and empty string
            ```sql
            WHERE "Rejection Reason" IS NOT NULL AND "Rejection Reason" != ''
            ```

        ## STATUS OF A NIF

        If the user asks about the status of a NIF, after filtering appropriately,
        return the following fields formatted as a bulleted list:
            - "Title"
            - "Status_Name"
            - "Status"
            - "Detailed Status"
            - "Created_By"
            - "Created"
            - "LIM"
            - "Material_Number"
            - "Brief Material Description"
            - "PDF Link"
            - "Rejection Reason" (only if "Status_Name" = "Rejected")

        # NOTES ABOUT IMPORTANT COLUMNS

        - "LIM" (TEXT): the name of the Logistics Innovation Manager assigned to
        this NIF, who is responsible for reviewing and approving it.

        - "Created" (TEXT): date and time this NIF was created, in the format
        'YYYY-MM-DD HH:MM:SS'. When users ask about time periods (e.g., "last month",
        "this year"), calculate the appropriate date range based on the current date,
        which is {dt.datetime.now().strftime('%Y-%m-%d')}.

        - "Created_By" (TEXT): name of the person who created this NIF. When
        searching in this field, try reversing first and last names and
        including a comma such as 'Marie Smith' and 'Smith, Marie'.

        - "Status_Name" (TEXT): the current status of this NIF. Can take these
        possible values: {status_name_distinct_values}.

        - "Status" (TEXT): detailed status of this NIF.

        - "Material_Number" (FLOAT): the material number of the product involved
        in this NIF. Also known as SAP Material Number. If the question
        includes hyphens, search for the material number without them.

        - "Brief Material Description" (TEXT): a description of the material in
        words.

        - "Material_Description" (TEXT): a description of the material using
        abbreviations. When searching for a material description, always do the
        following:
            - Use a %LIKE% operator to capture similar entries.
            - Check all the following columns using OR conditions:
                ["Brief Material Description", "Material_Description", "Title"].
            - Also search for abbreviations for common words using this lookup:
                {db_abbreviations_dict_small}.

        - "Title" (TEXT): project title which may also contain product type and
        material description.

        - "Project Description" (TEXT): the project this NIF is associated with.
        A single project may have multiple NIFs and involve multiple materials.

        - "Product Type" (TEXT): the product type for this NIF.

        - "Project Type" (TEXT): the project type for this NIF.

        - "COUNTRY" (TEXT): the country for this NIF. Note country names use
        these abbreviations {country_abbreviations}.

        - "Rejection Reason" (TEXT): the reason this NIF was rejected. Only
        populated if Status_Name is "Rejected".

        - "PDF Link" (TEXT): the PDF file associated with this NIF. Always format
        this as a hyperlink like so: [PDF](<PDF Link>).

        # HELPFUL BEHAVIORS

        - Column Reference:
            If the user asks what information is available, list the important columns
            above with brief descriptions.
    '''

    # For use in Dash, setting interactive=False so the task exits after each round.
    # This is necessary to get a response to print in Dash.
    ,interactive=False

    ,llm_delegate=True      # True: this agent decides when subtasks are done. False: subtask results are shown to the user and await confirmation.

    # Setting restart=False so that message history persists when task exits.
    ,restart=False
)

# =============================================================================
#### Orchestration
# =============================================================================
nif_database_query_task_top.add_sub_task(nif_database_answer_task_sub)

# Can I clone it? Yes.
# nif_database_query_task_top_cloned = nif_database_query_task_top.clone(1)

'''
test_question = 'How many NIFs have been submitted?'

nif_database_query_task_top.run(test_question)
nif_database_query_task_top_cloned.run(test_question)
'''

#%% NIF DATABASE QUERY AGENT V4
'''
Using two separate tasks: one to formulate and submit the query, another to
interpret the result and asnwer the user. This flips the delegation so that
the interpreter is the main task and the query is the subtask.

!!! Add: user name from logged in user so agent can answer questions about "my NIFs"
'''
# =============================================================================
#### Tools
# =============================================================================
class GetDataTool(lr.agent.ToolMessage):
    """Tool for the interpreter to request data from the SQL subtask."""
    request: str = "get_data"
    purpose: str = """Request data from the NIF database by describing what you need.
    The SQL specialist will generate and execute the appropriate query.
    Describe the data request clearly and any specific requirements."""

    data_request: str  # What data is needed

    def handle(self) -> str:
        # This tool signals to use the SQL subtask
        # The actual handling is done by the task routing
        return self.data_request

# =============================================================================
#### Config Query Agent
# =============================================================================
nif_database_query_agent_name = 'NIFDatabaseQueryAgent'

# nif_database_query_agent = lr.ChatAgent(agent_config_claude35)
nif_database_query_agent = lr.ChatAgent(agent_config_gpt4o)
# nif_database_query_agent = lr.ChatAgent(agent_config_claude4)

# nif_database_query_agent.enable_message(query_nif_db_tool)
nif_database_query_agent.enable_message(query_nif_db_tool_2)
nif_database_query_agent.enable_message(DoneTool)

# Using just the main table
table_name = 'NIFS'
column_list = utils.run_query(nif_database, f"SELECT * FROM pragma_table_info('{table_name}');")
column_list_cln = [(info[1], info[2]) for info in column_list]      # Keep column names and types

status_name_distinct_values = utils.run_query(nif_database, f"select distinct Status_Name from NIFS")

country_abbreviations = {
    "United States":"US"
    ,"Canada":"CA"
    ,"Mexico":"MX"
}

nif_database_query_task = lr.Task(
    nif_database_query_agent
    ,name=nif_database_query_agent_name
    ,system_message=f'''
        You are an agent specialized in formulating SQLite queries based on
        plain language questions.

        You have access to a SQLite database with information on Kellanova's New
        Item Forms (NIFs) that have been submitted. The database contains a table
        called '{table_name}' with one row per NIF. It contains the following
        columns, shown as ('column_name', 'column_type'): {column_list_cln}.

        # TASK

        When you receive a data request, construct a query using SQLite syntax and
        submit it using the 'query_nif_db_2' function with argument SQL_QUERY being
        your query. Then use the `{DoneTool.name()}` tool to return the results.

        See the sections below entitled QUERY CONSTRUCTION RULES and NOTES ABOUT
        IMPORTANT COLUMNS for constructing your query.

        Do NOT interpret or explain the data. Pass on the results of your query verbatim.

        # QUERY CONSTRUCTION RULES

        - Always wrap column names in double quotes.

        - When filtering on a column of type TEXT, always construct the query to be
        case-insensitive by using the LOWER() function.

        - When a query includes a person's name, always try the query twice, reversing
        first and last names and including a comma as in:
            ```sql
            WHERE LOWER("Created_By") IN (LOWER('Marie Smith'), LOWER('Smith, Marie'))
            ```

        - Always first check how many records exist for a given query. If a record
        exists but the requested field is empty, let the user know.

        - If the 'query_nif_db_2' function does not return anything, do the following:
            1. Try reformulating your query and resubmit.
            2. If the query still returns nothing, inform the user and ask them to
            clarify what they are looking for.

        - When answering summary or aggregate questions such as "how many NIFs
        have been submitted", always answer two ways:
            1. considering all items in the database and
            2. considering only items with Status_Name='Approved'

        - When checking if fields are empty, test for both NULL and empty string
            ```sql
            WHERE "Rejection Reason" IS NOT NULL AND "Rejection Reason" != ''
            ```

        ## ERROR HANDLING
        - If a query returns an error, attempt a corrected query.
        - If no results are returned, reformulate your query once and try again.
        - If no results are returned a second time, inform the user and ask for clarification.

        ## STATUS OF A NIF

        If the user asks about the status of a NIF, after filtering appropriately,
        return the following fields formatted as a bulleted list:
            - "Title"
            - "Status_Name"
            - "Status"
            - "Detailed Status"
            - "Created_By"
            - "Created"
            - "LIM"
            - "Material_Number"
            - "Brief Material Description"
            - "PDF Link"
            - "Rejection Reason" (only if "Status_Name" = "Rejected")

        # NOTES ABOUT IMPORTANT COLUMNS

        - "LIM" (TEXT): the name of the Logistics Innovation Manager assigned to
        this NIF, who is responsible for reviewing and approving it.

        - "Created" (TEXT): date and time this NIF was created, in the format
        'YYYY-MM-DD HH:MM:SS'. When users ask about time periods (e.g., "last month",
        "this year"), calculate the appropriate date range based on the current date,
        which is {dt.datetime.now().strftime('%Y-%m-%d')}.

        - "Created_By" (TEXT): name of the person who created this NIF. When
        searching in this field, try reversing first and last names and
        including a comma such as 'Marie Smith' and 'Smith, Marie'.

        - "Status_Name" (TEXT): the current status of this NIF. Can take these
        possible values: {status_name_distinct_values}.

        - "Status" (TEXT): detailed status of this NIF.

        - "Material_Number" (FLOAT): the material number of the product involved
        in this NIF. Also known as SAP Material Number. If the question
        includes hyphens, search for the material number without them.

        - "Brief Material Description" (TEXT): a description of the material in
        words.

        - "Material_Description" (TEXT): a description of the material using
        abbreviations. When searching for a material description, always do the
        following:
            - Use a %LIKE% operator to capture similar entries.
            - Check all the following columns using OR conditions:
                ["Brief Material Description", "Material_Description", "Title"].
            - Also search for abbreviations for common words using this lookup:
                {db_abbreviations_dict_small}.

        - "Title" (TEXT): project title which may also contain product type and
        material description.

        - "Project Description" (TEXT): the project this NIF is associated with.
        A single project may have multiple NIFs and involve multiple materials.

        - "Product Type" (TEXT): the product type for this NIF.

        - "Project Type" (TEXT): the project type for this NIF.

        - "COUNTRY" (TEXT): the country for this NIF. Note country names use
        these abbreviations {country_abbreviations}.

        - "Rejection Reason" (TEXT): the reason this NIF was rejected. Only
        populated if Status_Name is "Rejected".

        - "PDF Link" (TEXT): the PDF file associated with this NIF. Always format
        this as a hyperlink like so: [PDF](<PDF Link>).
    '''
    ,interactive=False
)

# =============================================================================
#### Config Answer Agent
# =============================================================================
nif_database_answer_agent_name = 'NIFDatabaseAnswerAgent'

nif_database_answer_agent = lr.ChatAgent(agent_config_claude35)
# nif_database_answer_agent = lr.ChatAgent(agent_config_gpt4o)

# nif_database_answer_agent.enable_message(GetDataTool)
nif_database_answer_agent.enable_message(RecipientTool)
nif_database_answer_agent.enable_message(DoneTool)

nif_database_answer_task = lr.Task(
    nif_database_answer_agent
    ,name=nif_database_answer_agent_name
    ,system_message=f'''
        You are a helpful assistant that interprets results from database
        query results to answer user questions.

        Your helper agent has access to a database with information on
        Kellanova's New Item Forms (NIFs) that have been submitted.

        You can ONLY answer questions that can be addressed by querying this
        database. If asked about topics outside this scope (general company
        information, other databases, unrelated topics), politely redirect by
        saying "I can only help with questions about the NIF database."

        When the user asks a question:
            - Determine if the question requires a database query. If so:
                1. {pass_to_agent(nif_database_query_agent_name)}.
                2. Once you receive the results, use the `{DoneTool.name()}`
                tool to give a concise answer to the user.
             - If the question does not require a database query (greetings,
            clarifications, etc.), respond normally.

        You can:
            - Handle follow-up questions
            - Ask for clarification if the user's question is ambiguous
            - Request multiple queries if needed for complex questions

        # HELPFUL BEHAVIORS

        - Follow-up Questions:
            After providing results, offer relevant follow-up options (e.g., "Would
            you like to see more details about any of these NIFs?" or "Would you like
            to filter these results further?")
    '''
    # For use in Dash, setting interactive=False so the task exits after each round.
    # This is necessary to get a response to print in Dash.
    ,interactive=False

    # ,llm_delegate=True  # True: this agent decides when subtasks are done. Not necessary if agents use DoneTool.

    # Setting restart=False so that message history persists when task exits.
    ,restart=False
)

# =============================================================================
#### Orchestration
# =============================================================================
nif_database_answer_task.add_sub_task(nif_database_query_task)

# Can I clone it? Yes.
# nif_database_answer_task_cloned = nif_database_answer_task.clone(1)

'''
test_question = 'How many NIFs have been submitted?'

nif_database_answer_task.run(test_question)
nif_database_answer_task_cloned.run(test_question)
'''

#%% BRANDS DATABASE QUERY AGENT
'''
UPDATE: not sure we'll be including the Brands database (SAP Material Master)
but if we do, will probably give the query_brands_db_tool to the NIF Database
agent.
'''
brands_database_agent_name = 'BrandsDatabaseAgent'

brands_database_agent = lr.ChatAgent(agent_config_for_others)
brands_database_agent.enable_message(RecipientTool)
brands_database_agent.enable_message(query_brands_db_tool)

# We want this bot to use just the main table
table_touse = 'Export'

column_list = utils.run_query(brands_database, f"SELECT * FROM pragma_table_info('{table_touse}');")
column_list_cln = [(info[1], info[2]) for info in column_list]      # Keep column names and types

brands_database_task = lr.Task(
    brands_database_agent
    ,name=brands_database_agent_name
    ,system_message=f'''
        You are an agent specialized in formulating SQLite queries based on
        plain language questions.

        You have access to a SQLite database with information on active brands.
        The database contains a table called '{table_touse}' with one row
        per material number. It contains the following columns, shown as
        ('column_name', 'column_type'): {column_list_cln}.

        When you receive a user question, construct a query using SQLite syntax
        and submit it using the 'query_brands_db' function. Interpret the result
        and reply with a concise answer to the user's question.

        If the 'query_brands_db' function does not return anything, say '{lrc.NO_ANSWER}'.

        Use the '{RecipientTool.name()}' tool with 'intended_recipient':'{receptionist_name}'
        and 'content' being your answer.

        # GUIDELINES

        - When filtering on a column of type TEXT, construct the query to be
        case-insensitive.

        - When searching for a person's name, always use %LIKE% to capture
        spelling variations. Also, try reversing first and last names and including
        a comma such as 'Marie Smith' and 'Smith, Marie'.

        - When searching for a material description, use a %LIKE% operator to
        capture similar entries. Also search for abbreviations for common words
        using this lookup: {db_abbreviations_dict}.

        - Always first check how many records exist for a given query. If a record
        exists but the requested field is empty, let the user know.
    '''
    #     Here are some notes about important columns:
    ,interactive=False
)

#%% GLOSSARY AGENT
'''
Idea: rather than querying a vectorstore, this agent will have a glossary of
terms in its system prompt.

AGENT INPUT: plain language question.
AGENT OUTPUT: plain language answer from glossary lookup.

UPDATE: the glossary will be direct input to the agents that need it. No need
for a glossary agent.
'''
glossary_agent_name = 'GlossaryAgent'

glossary_agent = lr.ChatAgent(agent_config_for_others)
glossary_agent.enable_message(RecipientTool)

glossary_task = lr.Task(
    glossary_agent
    ,name=glossary_agent_name
    ,system_message=f'''
        You are a helpful assistant with access to a glossary of terms. When
        asked about the meaning of a term, see if it exists in this lookup
        table: {glossary_dict}. Ignore case when looking for a term.

        Also check the New Item Form field lookup: {nif_fields_dict}.

        If the term exists in the lookup table, reply with the following:
            'EXACT MATCH' <term>:<definition>

        If the term does not have an exact match but there are similar terms in
        the lookup table, reply with the following:
            'NO EXACT MATCH'
            'SIMILAR TERM' <term>:<definition>

        If the term does not exist and there are no similar terms, reply with:
            '{lrc.NO_ANSWER}'

        Use the '{RecipientTool.name()}' tool with 'intended_recipient':'{receptionist_name}'
        and 'content' being your answer.
    '''
    ,interactive=False
)

#%% RECEPTIONIST AGENT
# *****************************************************************************
'''
UPDATE FOR IMPLEMENTATION: no loner using a receptionist.
'''
receptionist_agent = lr.ChatAgent(agent_config_for_receptionist)
receptionist_agent.enable_message(RecipientTool)

#! This is key! Give the receptionist the DoneTool to exit the task loop after
# receiving an answer. No special settings needed on subtasks.
# receptionist_agent.enable_message(DoneTool)

receptionist_task = lr.Task(
    receptionist_agent
    ,name=receptionist_name
    ,system_message=f'''
        You are a helpful assistant for Kellanova specializing in helping
        employees fill out New Item Forms (NIFs). You are the primary agent
        interacting with the user. You will delegate tasks to specialized agents
        as needed to query documents, lookup information from databases, or
        guide the user through filling out forms, then pass those agents' responses
        back to the user.

        See the section TYPES OF USER QUESTION below for instructions on routing
        user questions to different agents.

        IMPORTANT REQUIREMENTS:
            - Start your message with '{lrc.DONE}' any time you are addressing
            the user, whether it is an answer to their question or a request for
            more information.

            - When you receive a response from a specialized agent, REPEAT IT VERBATIM.
            The user will not see the response from any agent except you.

        If an agent does not respond or says '{lrc.NO_ANSWER}', try rephrasing your
        question and ask again.

        If you don't get a response a second time or the agent says '{lrc.NO_ANSWER}'
        again, apologize to the user and say the agent assigned to that task did not
        respond. Ask the user to clarify the scope of their question.

        # SCOPE OF DISCUSSION

        You are allowed to discuss Kellanova or Kellogg products, documents,
        and forms, and the people and departments associated with them.
        If the user asks about any other topic, politely decline to answer.

        # TYPES OF USER QUESTION

        ## Specific NIF field

        If the user asks for help with a specific field on the NIF,
        ask which field they need help with and list the fields:
            {formatted_list(list(nif_fields_poc_dict))}.

        If the user's question is about one of these terms, then
        {pass_to_agent(nifguide_agent_name)}.

        If the user's question is about a term that's not among the NIF fields,
        {pass_to_agent(glossary_agent_name)}.

        If agent {nifguide_agent_name} begins guiding the user through the product
        type flowchart, direct all subsequent user responses to him until he says
        '{lrc.DONE}'.

        ## Guidance to fill out the NIF step by step

        If the user asks for step by step guidance to fill out the NIF, do the
        following:
            - Say '{nifwalkthru_opening_statement}'.
            - Ask if they would like to begin the walkthrough. If so,
            {pass_to_agent(nifguide_agent_name)}. Direct all subsequent user
            responses to {nifguide_agent_name} until he says '{lrc.DONE}'.

        ## Training resources for the NIF

        If the user asks for training resources for the NIF, say the following:
            - 'There are several sources for training documents that can be located on the NIF Sharepoint Site located here:'
            (https://kelloggcompany.sharepoint.com/sites/DataCustodians/SitePages/New-Item-Form.aspx)

            - 'Additionally, you can attend an open forum training session that takes place on Monday / Wednesday. Contact Tommy Jones to be added to the distribution list for the training.'

            - 'Here are direct links to the most popular training guides:'
                {formatted_list([nif_training_guide_link, setup_type_guide_link])}

            - 'Can I help you find something specific in the documentation?'

        If the user asks for help finding something specific, {pass_to_agent(vectorstore_agent_name)}.

        ## Check NIF status

        If the user asks to check the status of a NIF, ask for a project name,
        material number, or other identifying information. Then
        {pass_to_agent(nif_database_agent_name)}.

        If the user simply states a project name or material number,
        {pass_to_agent(nif_database_agent_name)}.

        Note that material number is sometimes called SAP material number.

        ## Meaning of a term

        If the user asks about the meaning of a term, {pass_to_agent(glossary_agent_name)}.
        Also {pass_to_agent(nifguide_agent_name)}.
    '''
        # Also search for documents relevant to that term. {pass_to_agent(vectorstore_agent_name)}.

    # Not using brands database for demo
        # ## Existing products and brands

        # If the user asks for information about existing products and brands,
        # {pass_to_agent(nif_database_agent_name)}.
        # Agent {brands_database_agent_name} may also have relevant information.
        # {pass_to_agent(brands_database_agent_name)}.

    # ,llm_delegate=True  # True: this agent decides when subtasks are done

    # Setting interactive=False so that the user doesn't have to press enter after every step.
    # This requires enable_message(RecipientTool) so that the bot addresses the user and waits when appropriate.
    ,interactive=False

    # Setting restart=False so that message history persists when task exits.
    # This is essential because we only get a response to print in Dash when the task exits,
    # so we have instructed the receptionist to exit whenever addressing the user.
    ,restart=False
)

# =============================================================================
#### Task flow control
# =============================================================================
# Since Receptionist has RecipientTool, it will address questions to specific helper bots. Put them all in the same list.
receptionist_task.add_sub_task([
    glossary_task
    ,nifguide_task
    ,nif_database_task
    # ,brands_database_task
    ,vectorstore_task
])

# =============================================================================
#### Test strings
# =============================================================================
'''
import litellm
litellm._turn_on_debug()

receptionist_task.run('Question about a specific NIF field')
receptionist_task.run('Project type')

receptionist_task.run('What does Display mean?')

receptionist_task.run('What is product type?')
receptionist_task.run('Guide me through selecting the correct product type.')
receptionist_task.run('What are training resources for product type and subtype?')

receptionist_task.run('How many NIFs have been submitted?')
receptionist_task.run('What is the material number for protein poptarts?')

receptionist_task.run('What is the status of the NIF with Material_Number 2410012054?')
receptionist_task.run('Show me the detailed status of that NIF.')

receptionist_task.run('Find documents on club products in Canada')


# Testing multi-turn conversation
receptionist_task.run('I would like to find out the status of an existing NIF')
receptionist_task.run('Material number 6410015220')

# Message history
receptionist_agent.message_history
last_assistant_message = receptionist_agent.last_message_with_role(Role.ASSISTANT)
last_assistant_message.content
'''

#%% 4. LAYOUT
"This part is all about Dash and has been removed."

#%% 5. CALLBACKS
"This part is all about Dash and has been removed."

#%% 6. RUN APP
#############################################################################################################
"This part is all about Dash and has been removed."
