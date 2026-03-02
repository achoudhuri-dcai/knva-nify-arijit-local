#%% ABOUT
# *****************************************************************************
"""
Library of helper functions for LLMs.

!!!SECURITY NOTE: THIS PROGRAM CONTAINS SENSITIVE INFORMATION SUCH AS AZURE ACCOUNT
ENDPOINTS AND API KEYS. DO NOT SHARE THIS PROGRAM OUTSIDE OF FIRST ANALYTICS.
THIS PROGRAM IS INCLUDED IN THE GITHUB REPOSITORY. THIS IS OK AS LONG AS THE
REPOSITORY STAYS PRIVATE (ONLY ACCESSIBLE BY FIRST ANALYTICS).

@author: Ken

!!!TODO: remove any Langchain functions and replace with Langroid
"""

history = '''
Revision_history
================
    2023-10-10 kma  Initial version
    2023-10-20 kma  Added logging
    2023-10-21 kma  Added throttling
    2023-11-07 kma  Modified activity calls to include chat_func, **chat_kwargs - to support different chat agents
                    Fixed bug in how load_all_configs chooses the default config directory
    2025-04-22 jdr  Copied from Gradio Demo repository and trimmed down for Dash repo
    2025-04-28 kma  Added iso time functions
                    Added project create/list/remove functions
'''
#%% PACKAGES & CONSTANTS
# *****************************************************************************

import base64
import getpass
import hashlib
import inspect
import json
# import langchain.agents as lcagents
# import langchain.chains as lc
# import langchain.document_loaders as lcload
# import langchain.memory as lcmem
# import langchain.storage as lcs
# import langchain_community.vectorstores as lcstore
# import langchain_openai as lco
import os
import pickle
import platform
import psutil
import pytz  # timezone
import re
import requests as req         # For sending HTTP requests
import shutil
import subprocess
import sys
import hashlib
import time
import uuid
import yaml

from addict import Dict
from datetime import datetime as dt, timedelta, timezone
from dotenv import load_dotenv, dotenv_values
from glob import glob
# from langchain.callbacks.base import BaseCallbackHandler
# from langchain.retrievers.multi_vector import MultiVectorRetriever
# from langchain_core.documents import Document
# from langchain_core.messages import HumanMessage, SystemMessage
from pathlib import Path
import langroid as lr
import langroid.language_models as lrlm
from langroid.language_models import Role, LLMMessage

# import langchain.document_loaders as lcload
# import langchain.memory as lcmem
# from langchain.retrievers.multi_vector import MultiVectorRetriever
# import langchain.storage as lcs
# import langchain_community.vectorstores as lcstore
# from langchain_core.documents import Document

from queue import Queue
from threading import Thread
from tzlocal import get_localzone

# =============================================================================
#### CONSTANTS
# =============================================================================
local_timezone   = 'America/Denver'

# =============================================================================
#### Load environment variables
# =============================================================================
dotenv_loaded = load_dotenv()
if dotenv_loaded: print('> Environment file loaded')

# =============================================================================
#### CONSTANTS
# =============================================================================
CONFIG_FILE_NAME = 'projects.yaml'
SETTINGS_FILE_NAME = 'settings.json'

# =============================================================================
#### Azure storage
# =============================================================================
# Not currently using separate Azure storage
#!!! To use with Dash AI repo, create an Azure storage location for that project and fill in details here.
# azure_account_name = 'gradiodemo'
# azure_account_key  = '<REDACTED_SECRET>'
# azure_document_container = 'uploaded-documents'
# azure_image_container = 'images'

#%% BASIC FUNCTIONS
# *****************************************************************************

try:
    local_timezone = str(get_localzone())
except:
    print("ERROR getting time zone information.")
    sys.exit()

def utc_now() -> dt:
    '''input none. returns current UTC time as datetime object'''
    return dt.now(timezone.utc)

def iso_now() -> dt:
    '''input none. returns current UTC time as isoformat eg. 2025-02-25T01:10:10.180414Z'''
    return dt.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def local_time():
    return dt.now(pytz.timezone(local_timezone))

def hash256(string):
    return hashlib.sha256(string.encode()).hexdigest()

def get_ts(length=19, use_iso=True, secsep='.') -> str:
    '''input length(defaut=19), use_iso (default True)
    secsep is sparator between seconds and milliseconds with "." as default'
    returns local time formatted as YYYYmmdd_HHMMSS_mmmmmm and truncated to length'''
    if use_iso:
        return f'{utc_now():%Y%m%d_%H%M%S{secsep}%f}'[:length]
    else:
        return f'{local_time():%Y%m%d_%H%M%S{secsep}%f}'[:length]

def dt_from_iso(iso_str) -> dt:
    return dt.fromisoformat(iso_str)


def logit(*args):
    text = ' '.join(map(str,args))
    for txt in text.split('\n'):
        print(f'[{get_ts()}] {txt}')

pgmPath    = os.path.realpath(__file__)
pgmdir     = os.path.dirname(pgmPath)
pgmPathParent = str(Path(pgmdir).parent)

logit('-'*120)
logit('fa.lib loading')
logit('-'*120)
logit(f'program path:    {pgmPath}')
logit(f'program dir:     {pgmdir}')
logit(f'parent dir:      {pgmPathParent}')
logit(f'local timezone:  {local_timezone}')
logit(history)

# =============================================================================
#%% timers
# =============================================================================
# To print a number in old LCD style. Can also handle times (:, ., 'am' or 'pm').
def print_lcd_style(number):
    # LCD patterns for each digit
    lcd_patterns = {
        '0': [
            " _ ",
            "| |",
            "|_|",
            "   "
        ],
        '1': [
            "   ",
            "  |",
            "  |",
            "   "
        ],
        '2': [
            " _ ",
            " _|",
            "|_ ",
            "   "
        ],
        '3': [
            " _ ",
            " _|",
            " _|",
            "   "
        ],
        '4': [
            "   ",
            "|_|",
            "  |",
            "   "
        ],
        '5': [
            " _ ",
            "|_ ",
            " _|",
            "   "
        ],
        '6': [
            " _ ",
            "|_ ",
            "|_|",
            "   "
        ],
        '7': [
            " _ ",
            "  |",
            "  |",
            "   "
        ],
        '8': [
            " _ ",
            "|_|",
            "|_|",
            "   "
        ],
        '9': [
            " _ ",
            "|_|",
            " _|",
            "   "
        ],
        '-': [
            "   ",
            " _ ",
            "   ",
            "   "
        ],
        ':': [
            " ",
            "o",
            "o",
            " "
        ],
        '.': [
            " ",
            " ",
            "o",
            " "
        ],
        'p': [
            "   ",
            " _ ",
            "|_|",
            "|  "
        ],
        'a': [
            " _ ",
            "|_|",
            "| |",
            "   "
        ],
        'm': [
            "     ",
            " _ _ ",
            "| | |",
            "     "
        ],
    }

    # Convert number to string to handle each digit
    number_str = str(number).lower()

    # Build each row of the LCD display
    nrows = len(lcd_patterns['0'])
    rows = [''] * nrows

    for digit in number_str:
        if digit in lcd_patterns:
            for i in range(nrows):
                rows[i] += lcd_patterns[digit][i] + " "

    # Print each row
    for row in rows:
        print(row.rstrip())  # Remove trailing spaces

    return None

# To time a piece of code
# Usage:
    # timerstart('My timer')
    # <code>
    # timerstop()
def timerstart(LABEL:str=None):      # Optionally add a label to the printed timer messages
    global _timerstart ,_timerstart_label
    funcname = inspect.currentframe().f_code.co_name
    _timerstart = dt.now()
    _timerstart_label = LABEL
    _timerstart_formatted = f"{_timerstart :%I:%M:%S %p}"
    if _timerstart_label:
        print(f"\n<{funcname}> {_timerstart_label}")
    print(f"\n<{funcname}> {_timerstart_formatted}")
    print_lcd_style(_timerstart_formatted)
    return None

def timerstop():
    global _timerstop
    funcname = inspect.currentframe().f_code.co_name
    if '_timerstart' in globals():
        _timerstop = dt.now()
        elapsed = _timerstop - _timerstart
        hours = (elapsed.days * 24) + (elapsed.seconds // 3600)
        minutes = (elapsed.seconds % 3600) // 60
        seconds = (elapsed.seconds % 60) + (elapsed.microseconds / 1e6)
        _timerstop_formatted = f"{_timerstop :%I:%M:%S %p}"
        print_lcd_style(_timerstop_formatted)
        print(f"<{funcname}> {_timerstop_formatted}")
        if _timerstart_label:
            print(f"<{funcname}> {_timerstart_label} Elapsed {hours}h: {minutes}m: {seconds :.1f}s \n")
        else:
            print(f"<{funcname}> Elapsed {hours}h: {minutes}m: {seconds :.1f}s \n")
    else:
        print(f"<{funcname}> Error: no start time defined. Call timerstart() first.")
    return None

# To sleep for a given duration
# Usage: sleep(10)
def sleep(SEC):
    funcname = inspect.currentframe().f_code.co_name
    print(f"<{funcname}> Sleeping for {SEC} seconds...")
    time.sleep(SEC)
    print(f"<{funcname}> Waking up.")
    return None

def save_to_pickle(OBJ, FILENAME):
    with open(FILENAME, 'wb') as outp:
        pickle.dump(OBJ, outp, pickle.HIGHEST_PROTOCOL)
    return None

def load_from_pickle(FILENAME):
    with open(FILENAME, 'rb') as file:
        return pickle.load(file)

#%% USER & SYSTEM ACTIVITY
# *****************************************************************************

def write_chat_history(*args, project_id='unknown', note=''):
    hist_dir = os.path.join(pgmPathParent, 'chat_history', project_id)
    if not os.path.exists(hist_dir):
        os.makedirs(hist_dir, mode=0o777, exist_ok=True)
        logit(f'Created {hist_dir}')
    text = ' '.join(map(str,args))
    chat_path = f'chat_{get_ts(8)}.txt'
    with open(os.path.join(hist_dir, chat_path), 'at') as f:
        f.write(f'[{get_ts()}]{note}\n{text}\n')
    if platform.system().lower() == 'linux':  # for linux gradio server
        os.chmod(os.path.join(hist_dir, chat_path), mode=0o777)
    logit(f'Chat history written to {os.path.join(hist_dir, chat_path)}.')

def log_system_info(writer=logit, only_memory=False):
    if not only_memory:
        process = psutil.Process()
        writer(f'Process ID of this process:     {process.pid}')
        writer(f'Username of the process owner:  {process.username()}')
        create_time = dt.fromtimestamp(process.create_time()).strftime("%Y-%m-%d %H:%M:%S")
        writer(f'Process create time:            {create_time}')
        writer(f'Memory used by this process:    {process.memory_info().rss:15,} bytes')
    writer(f'System memory available:       {psutil.virtual_memory().available:15,} bytes')

log_system_info()
"""
def get_ucid(request, user_activity, system_activity, chat_func, verbose=False, **chat_kwargs):
    if verbose: logit('get_ucid request.headers.__dict__', request.headers.__dict__)
    if verbose: logit(f'{"clientaddress" in request.headers=}')
    print(f'request= {request}')
    headers = request.headers
    print(f'headers= {headers}')
    host = headers["clientaddress"] if "clientaddress" in headers else headers["host"]
    print(f'host= {host}')
    try:
        ucid = host + '-' + hash256(headers.get('user-agent', 'no-user-agent'))[:8]
    except AttributeError:
        ucid = host + '-' + hash256(headers['user-agent'])[:8]
    except KeyError:
        ucid = host + '-' + hash256('no-user-agent')[:8]
    create_my_activity(ucid, user_activity, chat_func, **chat_kwargs)  # make a new my_activity if needed
    return ucid

def create_my_activity(ucid, user_activity, chat_func, **chat_kwargs):
    '''
    Create a new entry (if not previously existing) in the user_activity dictionary, including a new chatbot object

    ucid: the user's id
    user_activity: the Dict() that tracks all user activity and user chatbot object. Instantiated in the calling program, the user's entry modified here
    chat_func: a method in the mendable or LangChain library that instantiates a chatbot.
    chat_kwargs: arguments needed by the chat_func, eg. api_key=mendable_api_key or llm=openai_chat_model
    '''
    # create my_activity if first time
    if ucid not in user_activity:
        user_activity[ucid].begun = local_time()
        my_activity = user_activity[ucid]
        logit(f'{ucid} New user activity object created.')
        my_activity.last_click = local_time()
        my_activity.last_resp = local_time()
        my_activity.total_count = 0
        my_activity.fast_count = 0
        my_activity.consecutive_fast = 0
        my_activity.suspended_dt = None
        my_activity.prior_question = ''
        my_activity.ucid = ucid
        my_activity.suspended_until = None
        my_activity.suspended_reason = ''
        my_activity.chatbot_begun = local_time()
        my_activity.chatbot_last_used = local_time()

        # Create chatbot with user-specific memory
        user_chat_memory = lcmem.ConversationBufferMemory(
            memory_key='chat_history'
            ,return_messages=True
            ,output_key='output'
        )
        chat_kwargs["output_key"] = 'output'    # Set output_key to what memory will look for
        chat_kwargs["memory"] = user_chat_memory
        # logit(f'{chat_kwargs=}')
        my_activity.chatbot_obj = chat_func(**chat_kwargs)

        # Clear memory
        # May not want to do this all the time
        # try:    # Not all chatbots have memory
        #     logit(f"{ucid} Before clearing chat history it was {len(my_activity.chatbot_obj.memory.buffer_as_str):,} characters.")
        #     logit(f"{ucid} First 200 characters are: {my_activity.chatbot_obj.memory.buffer_as_str[:200]}.")
        #     my_activity.chatbot_obj.memory.clear()
        # except AttributeError:
        #     pass

def activity_tracking(request, user_activity, system_activity, chat_func, **chat_kwargs):

    logit('-'*60)
    ucid = get_ucid(request, user_activity, system_activity, chat_func, **chat_kwargs)  # will also create new my_activity object if ucid does not have one
    now = local_time()  ## base the daily rollover of counters on local time zone
    msg = ''
    my_activity = user_activity[ucid]

    # Reset counters if the hour crossed midnight, ie was last query yesterday, or earlier

    if my_activity.last_click.day != now.day:
        logit(f'{ucid} Day changed. Was {my_activity.last_click.minute//5}, now {now.minute//5}. '
              f'Reinitialize user counters, remove suspensions.')
        my_activity.fast_count = 0
        my_activity.total_count = 0
        my_activity.suspended_dt = None
        my_activity.suspended_until = None
        my_activity.suspended_reason = ''
        my_activity.last_click = now

    if system_activity.total_count_last_reset.day != now.day:
        logit(f'{ucid} Day changed. Resetting system_activity counters')
        system_activity.total_count_last_reset = now
        system_activity.total_count = 0

    # check suspension
    if my_activity.suspended_dt:
        suspended_until = my_activity.suspended_until
        logit(f'{ucid} suspended until {suspended_until}')
        if suspended_until > now:  # suspended_until a future date?  Yes >> still suspended
            msg = f'   --- suspended until {suspended_until:%b %d %I:%M:S %p %Z} ---'
            #update history
            my_activity.history += f'{local_time()} {ucid} {msg}\n'
            time.sleep(10)
            return ucid, my_activity   # no further activity processing.  This user suspended.
        else:
            logit(f'{ucid} Suspension ended.')
            my_activity.suspended_dt = None
            my_activity.suspended_until = None

    # this error was seen once.  Unable to reproduce.
    if not isinstance(my_activity.total_count, int):
        logit(f'ERROR my_activity.total_count type is not "int", but rather {type(my_activity.total_count)}')
        logit('Setting  my_activity.total_count = ')
        my_activity.total_count = 0

    # increment counts
    my_activity.total_count += 1
    system_activity.total_count += 1

    think_time = max(0, (now - my_activity.last_resp).total_seconds())  # sometimes negative on startup

    # update activity
    if think_time < system_activity.fast_think_threshold:
        my_activity.fast_count += 1
        my_activity.consecutive_fast += 1
        msg = ''  # 'Slow down !!' if my_activity.total_count > 0 else ''
    else:
        my_activity.consecutive_fast = 0
        msg = ''

    if my_activity.consecutive_fast >= system_activity.max_consecutive_fast:
        logit(f'{ucid} Suspended. Too many consecutive fast queries')
        my_activity.suspended_dt = now
        my_activity.suspended_until = now + timedelta(seconds=system_activity.suspended_duration)
        my_activity.suspended_reason = 'because of load limits on the system. Please come back later.'
    elif  my_activity.total_count >= system_activity.max_daily_per_user:
        logit(f'{ucid} Suspended. Total query count exceeds {system_activity.max_daily_per_user=}')
        my_activity.suspended_dt = now
        seconds_until_tomorrow = 24 * 3600 - now.hour * 3600 - now.minute * 60 - now.second + 1
        my_activity.suspended_until = now + timedelta(seconds=seconds_until_tomorrow)
        my_activity.suspended_reason = 'because we must limit the daily use per user.  Please come back tomorrow.'
    elif  system_activity.total_count >= system_activity.max_daily_all_users:
        logit(f'{ucid} Suspended. System wide query count exceeds {system_activity.max_daily_all_users=}')
        my_activity.suspended_dt = now
        seconds_until_tomorrow = 24 * 3600 - now.hour * 3600 - now.minute * 60 - now.second + 1
        my_activity.suspended_until = now + timedelta(seconds=seconds_until_tomorrow)
        my_activity.suspended_reason = 'because we must limit the system-wide daily usage.  Please come back tomorrow.'

    logit(f'{ucid} {system_activity.total_count=} last_reset={system_activity.total_count_last_reset}')
    logit(f'{ucid} {think_time=:.3f} count={my_activity.total_count} fast_count={my_activity.fast_count} '
          f'cons_fast={my_activity.consecutive_fast} sys_total_count={system_activity.total_count}')

    # report memory usage every now and then
    if not system_activity.total_count % 25:  # every 25 queries - to not clutter the logs
        log_system_info(only_memory=True)

    return ucid, my_activity

def set_system_activity(system_activity, my_config):
    system_activity.fast_think_threshold = my_config.fast_think_threshold
    system_activity.max_consecutive_fast = my_config.max_consecutive_fast
    system_activity.max_daily_per_user = my_config.max_daily_per_user
    system_activity.max_daily_all_users = my_config.max_daily_all_users
    system_activity.suspended_sleep_sec = my_config.suspended_sleep_sec
    system_activity.suspended_duration = my_config.suspended_duration
    system_activity.startup = local_time()

    system_activity.total_count = 0  # all users
    system_activity.total_count_last_reset = local_time()  # all users
    system_activity.mendable_api_key = my_config.mendable_api_key

    for key in sorted(system_activity):
        logit(f"{key+':':22} {system_activity[key]}")


#%% YAML LOADING FUNCTIONS
# *****************************************************************************

def load_yaml(path, writer=logit, verbose=False, raw_only=False):
    '''

    Parameters
    ----------
    path : str
        Full path to the yaml file.
    verbose : bool, optional
        Causes info messages. The default is False.

    Returns
    -------
    Object
        An object, such as dict or list, of the parsed yaml.

    Errors
    ------
    Throws an error if the file does not exist or it contains improperly formed yaml

    '''
    with open(path, encoding='UTF-8') as f: raw = f.read()
    if raw_only:
        return raw
    doc = yaml.safe_load(raw)
    if verbose: writer(f'loaded {len(raw)} bytes from {path}')
    return Dict(doc)

def load_all_configs(config_dir=None, config_filename=None, verbose=False, raw_only=False):
    '''

    Parameters
    ----------
    config_dir : str, optional
        The directory, a sibling of the code directory. The default is None. If None, CONFIG_DIRECTORY is used.
        If the file is not found in config_dir, then the directory where this lib is located is used.
        If still not found, an error occurs.
    config_filename : str, optional
        The filename. The default is None.  If None, CONFIG_FILE_NAME is used.
    verbose : bool, optional
        Causes info messages. The default is False.

    Returns
    -------
    A dict of project properties  'project1': {'property1': 'spam', ...}, ...
        The dict supports 3 types of lookup: projects[proj_id], projects.get(proj_id, 'na'), projects.proj_id.property_name


    '''
    # set defaults
    if config_filename is None:
        config_filename = CONFIG_FILE_NAME
    if config_dir is None:
        config_dir = os.path.dirname(os.path.realpath(__file__)) # same directory as this file.  kma 20231107
    # set paths
    pgmPath    = os.path.realpath(__file__)
    pgmdir     = os.path.dirname(pgmPath)
    pgmPathParent = str(Path(pgmdir).parent)
    config_path = os.path.join(pgmPathParent, config_dir, config_filename)
    # read the config file
    if verbose:
        logit(f'{config_path=}')
    if not os.path.exists(config_path):
        msg = f'Config file not found {config_path}'
        print(msg)
        raise Exception(msg)
    return load_yaml(config_path, verbose=verbose, raw_only=raw_only)

def load_my_config(my_project_ID, config_dir=None, config_filename=None, verbose=False):
    '''

    Parameters
    ----------
    my_project_ID : str, required
        the id of the project
    config_dir : str, optional
        The directory, a sibling of the code directory. The default is None. If None, CONFIG_DIRECTORY is used.
    config_filename : str, optional
        The filename. The default is None.  If None, CONFIG_FILE_NAME is used.
    verbose : bool, optional
        Causes info messages. The default is False.

    Returns
    -------
    None if id not found, else a dict of project properties  'project1': {'property1': 'spam', ...}, ...
        The dict supports 3 types of lookup: projects[proj_id], projects.get(proj_id, 'na'), projects.proj_id.property_name

    '''
    # get all the configs then return only my_project_ID
    config = load_all_configs(config_dir, config_filename, verbose=verbose).get(my_project_ID, None)
    if project_config_has_required_keys(my_project_ID):
        return config
"""

def run_cmd(cmd, verbose=False):
    if verbose: print(f'run_cmd: {cmd}')
    sys.stdout.flush()
    result = subprocess.run(cmd, shell=True, capture_output=True)
    out_txt = result.stdout.decode()
    err_txt = result.stderr.decode()
    if verbose:
        if err_txt.strip():
            print('stderr:' + err_txt)
        if out_txt:
            print('stdout:' + out_txt)
    return out_txt, err_txt

"""
def project_config_has_required_keys(project_ID):
    my_config = load_all_configs().get(project_ID, None)
    req_keys = set([
         'description',
         'active',
         'port',
         'root_path',
         'subdomain',
         'program_name',
         # 'mendable_api_key',  # JR: not all projects require this
         'auth_name',
         'auth_passwd',
         'fast_think_threshold',
         'max_consecutive_fast',
         'max_daily_per_user',
         'max_daily_all_users',
         'suspended_sleep_sec',
         'suspended_duration'])
    my_keys = set(my_config)
    missing_keys = req_keys - my_keys
    if missing_keys:
        msg = f'Some keys are missing from {project_ID} in projects.yaml'
        logit(msg)
        for key in sorted(missing_keys):
            logit(f'   {key}')
        raise Exception(msg+' See log.')
    return not missing_keys

load_config = load_my_config  # an alias
"""

#%% OPENAI & CHAT FUNCTIONS
# *****************************************************************************
# =============================================================================
#### Azure OpenAI LLMs
# =============================================================================
'''
These rely on environment variables AZURE_OPENAI_API_VERSION,
AZURE_OPENAI_API_BASE, and AZURE_OPENAI_API_KEY being set. Check your .env file.

Alternatively, you can specify arguments api_base, api_key, and api_version in
lrlm.AzureConfig().

API details are from First Analytics' Azure AI Foundry deployments (ai.azure.com).

api_base and api_key can be retrieved from the "Models + endpoints" page two ways:
    - Click on the "Get endpoint" button for a deployment. If several models are
    deployed under the same service, they all have the same api_base and api_key.
    - Click on the deployment name, taking you to the deployment details screen.
    This has the advantage of also providing the deployment name and model name.

API version must be updated periodically. Check https://learn.microsoft.com/en-us/azure/ai-services/openai/api-version-deprecation.
'''
# GPT-4o
azure_gpt4o_config = lrlm.AzureConfig(
    # Required
    deployment_name='GPT-4o'
    ,model_name='gpt-4o'

    # Optional
    ,temperature=0
    ,max_output_tokens=4096    # To get around Agent error complaining about max tokens
)
azure_gpt4o = lrlm.AzureGPT(azure_gpt4o_config)
# azure_gpt4o.chat('Hello!', max_tokens=None)

# GPT-4o-mini
azure_gpt4o_mini_config = lrlm.AzureConfig(
    # Required
    deployment_name='gpt-4o-mini'
    ,model_name='gpt-4o-mini'

    # Optional
    ,temperature=0
    ,max_output_tokens=4096    # To get around Agent error complaining about max tokens
)
azure_gpt4o_mini = lrlm.AzureGPT(azure_gpt4o_mini_config)
# azure_gpt4o_mini.chat('Hello!', max_tokens=None)

# GPT-3.5-turbo
azure_gpt35_config = lrlm.AzureConfig(
    # Required
    deployment_name='GPT-35-turbo-01'
    ,model_name='gpt-35-turbo'

    # Optional
    ,temperature=0
    ,max_output_tokens=4096    # To get around Agent error complaining about max tokens
)
azure_gpt35 = lrlm.AzureGPT(azure_gpt35_config)
# azure_gpt35.chat('Hello!', max_tokens=None)

# Text Embedding
azure_embed_config = lrlm.AzureConfig(
    # Required
    deployment_name='text-embedding-ada-002'
    ,model_name='text-embedding-ada-002'
)
azure_embed = lrlm.AzureGPT(azure_embed_config)

# Text Embedding Large
azure_embed_large_config = lrlm.AzureConfig(
    # Required
    deployment_name='text-embedding-3-large'
    ,model_name='text-embedding-3-large'
)
azure_embed_large = lrlm.AzureGPT(azure_embed_large_config)

# =============================================================================
#### LLM Utility Functions
# =============================================================================
# To pass a block of text to an LLM along with a prompt.
# Useful for asking the LLM to summarize a block of text.
# This uses a basic chat that does not keep chat history.
#!!! Rewrite without langchain
# def query_text(
#         TEXT:str                        # The full text. If larger than the LLM's context window, will throw an error.
#         ,SYSTEM_PROMPT:str              # System prompt
#         ,USER_QUESTION:str              # User question
#         ,LLM=azure_gpt4o                # The LLM to use
#         ,MAX_ANSWER_LENGTH=None         # Optional: maximum tokens for answer
#     ):
#     msg = LLM.invoke([
#         SystemMessage(content=(SYSTEM_PROMPT))
#         ,HumanMessage(content=[{"type": "text", "text": USER_QUESTION + TEXT}])
#     ])
#     return msg.content

# A helper function for checking if a string is a base64 image
def looks_like_base64(STRING):
    return re.match("^[A-Za-z0-9+/]+[=]{0,2}$", STRING) is not None

# To invoke an LLM and pass it one or more images along with a question.
# Note: this does not use Langroid or Langchain. It uses the openai package to
# call AzureOpenAI directly so we can pass the base64 encoded images using
# GPT's native message format.
def query_multiple_images_azureoai(
        IMAGE_LIST:list[str]            # List of image strings. May be either full paths to image files or base64-encoded images.
        ,SYSTEM_PROMPT:str              # System prompt
        ,USER_QUESTION:str              # User question
        ,DEPLOYMENT_NAME:str="gpt-4o"   # The name of the deployment to use (defined in Azure OpenAI console). Must be an LLM that can interpret images.
    ):
    # Create Azure client
    # This requires environment variables AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and OPENAI_API_VERSION to be set. Check the .env file.
    # Alternatively, you can pass azure_endpoint, api_key, and api_version as arguments to AzureOpenAI().
    from openai import AzureOpenAI
    azure_client = AzureOpenAI()

    # Prepare images
    images_for_chatbot = []     # Initialize
    for image in IMAGE_LIST:
        if looks_like_base64(image):
            image_b64 = image
        else:
            # Encode image as base64
            image_b64 = encode_image(image)

        # Append to list of dictionaries formatted for chatbot
        images_for_chatbot.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}})

    # Pass images to chat with prompt
    messages_with_images = [
        {"role":"system", "content":[{"type":"text", "text":SYSTEM_PROMPT}]}
        ,{"role":"user", "content":[{"type":"text", "text":USER_QUESTION}] + images_for_chatbot}
    ]
    response = azure_client.chat.completions.create(
        model=DEPLOYMENT_NAME
        ,messages=messages_with_images
    )
    return response.choices[0].message.content

#%% TESTING
# *****************************************************************************

if  __name__ == "__main__" :
    pass
    # # testing load_config, which also tests the alias, load_my_config, load_yaml, load_all_configs
    # logit('\nTesting...\n')
    # project = 'demo1' # 'rob1'
    # my_config = load_config(project, verbose=True)
    # assert my_config, f'NOT FOUND: {project=}'
    # if my_config:
    #     if project_config_has_required_keys(project):
    #         logit(f'{project=} exists and has all its required keys.')



logit('-'*120)  # end of lib loading
