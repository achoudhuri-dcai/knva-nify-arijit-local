#%% ABOUT
# *****************************************************************************
"""
This script is for testing the Langroid agents.

It has been copied from the main Dash app DCAI_KN_Chat_Dash_UI_Gradio_Mock.py
but has all Dash components removed.
"""
#%% 1. STARTUP & IMPORTS

# standard library packages (included with python and always available)
import os, sys, datetime as dt
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

# private (fa) libraries
from lib.fa_dash_utils import instantiate_app
import lib.fa_lib as fa
import lib.projects_lib as pr
import lib.knova_utils as utils

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
	CURRENT_FOLDER_DASH_APP = os.path.dirname(os.path.realpath(__file__)) 	# Doesn't rely on working directory. Will throw NameError if run as a single line. Works only when running a cell or the whole file.
	print(f"> CURRENT_FOLDER_DASH_APP set to location of this file: {CURRENT_FOLDER_DASH_APP}")
except NameError:
	CURRENT_FOLDER_DASH_APP = os.getcwd() 		 			# Relies on working directory being set to this program.
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

# Product Type Expert Rules
prodtype_rules = pd.read_excel(os.path.join(utils.DOCUMENT_FOLDER, 'decision_tree_product_type_subtype.xlsx'))
decision_tree_product_type_subtype = prodtype_rules.to_markdown(index=False)

# Project Type Expert Rules
projtype_rules = pd.read_excel(os.path.join(utils.DOCUMENT_FOLDER, 'decision_tree_project_type.xlsx'))
decision_tree_project_type = projtype_rules.to_markdown(index=False)

# Product Type: map abbreviations from online form to full names in NIF database
#!!! Note product type in database is actually a combination of country, type, and subtype!
product_type_abbreviations = {
    "CS":"Straight Case"
    ,"BULK CS":"Bulk Case"
}

#IMPLEMENTATION
# The file now contains rule logic for every field, not just product type.
expert_system_rules = pd.read_excel(
    os.path.join(utils.DOCUMENT_FOLDER, 'Expert_System_Rules_20250926.xlsx')
    ,sheet_name='Implementation v1'
    ,header=1
)
expert_system_rules_md = expert_system_rules.to_markdown(index=False)

# For testing, subset to the rules used in the POC
expert_system_rules_poc = expert_system_rules.iloc[3:28, :]
expert_system_rules_poc_md = expert_system_rules_poc.to_markdown(index=False)

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

# =============================================================================
#### Chatbot options
# =============================================================================
# Starting system message
system_message = """
You are a helpful assistant working for Kellanova to assist someone fulling out a New Item Form (NIF).
Do not answer any questions that are not related to Kellanova or the New Item Form.
You have been trained with documentation on the NIF and you can answer specific questions about certian fields
as well as guide a user step by step through the NIF.
"""

# JR: Using the model specified by utils.azure_llm_gpt4o

# global_socket_id = None

#%% AGENTS AND TOOLS

# =============================================================================
#### Agent config
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
#### Agent tools
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
#### Glossary agent
# =============================================================================
'''
Idea: rather than querying a vectorstore, this agent will have a glossary of
terms in its system prompt.

AGENT INPUT: plain language question.
AGENT OUTPUT: plain language answer from glossary lookup.
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

# =============================================================================
#### Document Retrieval agent
# =============================================================================
'''
AGENT INPUT: plain language question.
AGENT OUTPUT: plain language answer from interpreted vectorstore result.
'''
vectorstore_agent_name = 'DocRetrievalAgent'

vectorstore_agent = lr.ChatAgent(agent_config_for_others)
vectorstore_agent.enable_message(RecipientTool)
vectorstore_agent.enable_message(retrieve_and_answer_tool)

#!!! Combine with glossary agent
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

# =============================================================================
#### NIF Database query agent
# =============================================================================
'''
This agent has access to the database of open and approved NIFs.

AGENT INPUT: plain language question.
AGENT OUTPUT: plain language answer from interpreted database result.
'''
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

# =============================================================================
#### Brands Database query agent
# =============================================================================
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

# =============================================================================
#### NIF Guide agent
# =============================================================================
nifguide_agent_name = 'NIFGuideAgent'

nifguide_agent = lr.ChatAgent(agent_config_for_others)
nifguide_agent.enable_message(RecipientTool)

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

nifguide_task = lr.Task(
    nifguide_agent
    ,name=nifguide_agent_name
    ,system_message=f'''
        You are an expert in Kellanova's New Item Form (NIF). This form is used
        to setup new products or new packaging for existing products. It contains
        the following fields: {list(nif_fields_poc_dict)}.

        See the instructions below for how to answer various questions.

        Address your responses to agent {receptionist_name} using the
        '{RecipientTool.name()}' tool with 'intended_recipient':'{receptionist_name}'
        and 'content' being your answer.

        # SPECIFIC FIELD

        If you are asked about a specific field, do the following:

            - Provide the description for that field from this lookup:
                {nif_fields_poc_dict}.

            - If the question is about Product Type or Subtype, see the
            instructions in the section DETERMINING PRODUCT TYPE AND SUBTYPE,
            below. When you are done with that process, say '{lrc.DONE}'.
    '''
            # - Ask the document retrieval agent {vectorstore_agent_name} to search
            # for documents related to that field. Use the '{RecipientTool.name()}' tool
            # with 'intended_recipient':'{vectorstore_agent_name}' and 'content'
            # being just the field name. If the response is relevant, include it in
            # your answer.
    f'''
        # STEP BY STEP GUIDANCE

        If you are asked for step-by-step guidance in filling out the NIF,
        walk through the following in order, asking one question at a time:

            1. Determine country, form type, product type and subtype: see the
            instructions in the section DETERMINING PRODUCT TYPE AND SUBTYPE,
            below.

            2. Ask the user if this is a Pringles product (YES or NO).

            3. Ask the user if this is an RX product (YES or NO).

            4. SAP Material number: notify the user that this will be added by
            the Masterfiles team. Proceed to the next question.

            5. Determine project type by asking the user the questions from this
            table and following the instructions: {decision_tree_project_type}.

            6. Ask the user for a Project Name or Number. Point out the
            requirements for this from here: {nif_fields_poc_dict}.
            If the user does not know the name or number, recommend that they
            review the KPATH system (link) for that information.

            7. Ask the user for a brief product description. OFFER TO PROVIDE
            SOME EXAMPLES. If they want examples, direct {receptionist_name} to
            ask agent {nif_database_agent_name} to provide the Brief Material
            Description for 3 NIFs matching the Country, Product Type, Pringles
            yes or no, and Project Type you determined above.

            8. Ask the user for a brief project overview. Suggest an overview
            based on the information you have determined above.

            9. Say 'That concludes the NIF walkthrough' and show a summary of
            the value that you determined for each field.

            10. Say '{lrc.DONE}'.

        # DETERMINING PRODUCT TYPE AND SUBTYPE

        If asked how to determine product type and subtype, offer to guide the
        user through the process of determining these. If they want to begin,
        proceed with the following:

            - The following table represents rules from a flowchart to identify
            country, form type, product type, and product subtype:
                {decision_tree_product_type_subtype}.

            - The objective is to guide the user to a path that ends with a question
            that says "None - represents end of this line of questioning". Start with
            question number 1 and ask the user the question from the "Question" column.
            Do not tell the user the question number; only the question itself.
            Based on the user's answer, follow the instructions in the "Instructions"
            column.

    '''
    # Haven't tested the training document references
            # - At each point in the process, remind the user that if they can't answer
            # the question or have doubts, they can ask you for training document
            # references to help them make the correct decision.

    #!!! Add reference page from Setup Type Guide for product type
    #!!! Add metadata filter to retriever
    #!!! Consider giving this bot access to the vectorstore
        # When you reach the end of a line of questioning, get a link to the
        # documentation using the '{RecipientTool.name()}' tool with
        # 'intended_recipient':'{vectorstore_agent_name}' and
        # 'content':'Document: Setup Type Guide, Country: '

    ,interactive=False
)

# Several things would need to be modified to give this agent direct access to nif_database_task.
# For now, rely on receptionist to interact with database agent.
# nifguide_task.add_sub_task(nif_database_task)

'''
!!! Add vectorstore search as well
nifguide_task.add_sub_task(vectorstore_task)

nifguide_task.run('What is Project Type?')
nifguide_task.run('How do I determine Product Type?')
'''

# =============================================================================
#### Receptionist agent
# =============================================================================
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

#%% TESTING

# agent_config_gpt4o = lr.ChatAgentConfig(llm=utils.azure_llm_gpt4o)

# test_agent = lr.ChatAgent(agent_config_gpt4o)

# # test_agent.enable_message(DoneTool)
# # test_agent.enable_message(DonePassTool)
# # test_agent.enable_message(AgentDoneTool)
# # test_agent.enable_message(RecipientTool)
# # Try: instruction to use recipienttool with 'intended_recipient':'USER' AND say DONE

# #!!! This worked: simple instruction to say 'DONE'. DoneTool was not working.
#     # ,system_message=f'''
#     #     You are an assistant for testing LLM agents.

#     #     Always say '{lrc.DONE}' at the start of your response.
#     # '''

# test_task = lr.Task(
#     test_agent
#     ,name='Tim'
#     ,system_message=f'''
#         You are an assistant for testing LLM agents.

#         Always say '{lrc.DONE}' at the start of your response.
#     '''
#         # Use the '{DoneTool.name()}' tool to respond to the user. Put the FULL TEXT of
#         # your response in the 'content' field of this tool.

#     # Setting interactive=False so that the user doesn't have to press enter after every step.
#     # This requires enable_message(RecipientTool) so that the bot addresses the user and waits when appropriate.
#     ,interactive=False

#     # Setting restart=False so that message history persists when task exits.
#     # This is essential because we only get a response to print in Dash when the task exits,
#     # so we have instructed the receptionist to exit whenever addressing the user.
#     ,restart=False
# )

# test_task.run('Who are you?')

#%% 4. LAYOUT
"This part is all about Dash and has been removed."

#%% 5. CALLBACKS
"This part is all about Dash and has been removed."

#%% 6. RUN APP
#############################################################################################################
"This part is all about Dash and has been removed."
