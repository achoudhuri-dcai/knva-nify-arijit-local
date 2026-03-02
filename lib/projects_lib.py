#%% ABOUT
# *****************************************************************************
"""
Library of helper functions for AI Workbench projects.
"""

history = '''
Revision_history
================
    2025-04-29 kma  Initial version - derived from the fa_lib used in Gradio Demo and Dash-AI
                    Added write_uploaded_files function
'''
#%% PACKAGES & CONSTANTS
# *****************************************************************************

import base64
import getpass
import hashlib
import json

import os
import pytz  # timezone
import shutil
import sys
import time

from addict import Dict
from datetime import datetime as dt, timezone
from glob import glob
from pathlib import Path
from tzlocal import get_localzone

# =============================================================================
#### CONSTANTS
# =============================================================================

try:
    local_timezone = str(get_localzone())
except:
    local_timezone   = 'America/Denver'
    print("ERROR getting time zone information from the OS. Using {local_timezone}")


# =============================================================================
#### CONSTANTS
# =============================================================================
SETTINGS_FILE_NAME = 'settings.json'

#%% BASIC FUNCTIONS
# *****************************************************************************

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
logit('projects_lib loading')
logit('-'*120)
logit(f'program path:    {pgmPath}')
logit(f'program dir:     {pgmdir}')
logit(f'parent dir:      {pgmPathParent}')
logit(f'local timezone:  {local_timezone}')
logit(history)


# =============================================================================
#%% Project functions
# =============================================================================

def get_app_dir():
    max_levels_to_search = 4
    # pgm_path    = os.path.realpath(__file__)
    # pgm_dir     = os.path.dirname(pgm_path)
    pgm_dir = pgmdir  # definded in fa_lib as global variable
    dirs_at_top = ['assets', 'logs']  # the top level of the AI Workbench has these directories - and others
    # find the app_dir - the directory containing all parts of this app - this is the directory where the projects folder belongs
    # initialize app_dir to pgm_dir
    app_dir = pgm_dir
    for parent_level in range(1,9):  # a limited range
        if all(dirname in os.listdir(app_dir) for dirname in dirs_at_top):
            # logit(f'found {dirs_at_top} in {app_dir}  --  this dir assumed to be the top directory of the app')
            return app_dir
        if parent_level >= max_levels_to_search:
            logit('ERROR. Unable to find a directory that contains {dirs_at_top}')
            sys.exit(1)
        app_dir = str(Path(app_dir).parent)

def get_project_dir():
    return os.path.join(get_app_dir(), 'projects')

def get_logs_dir():
    return os.path.join(get_app_dir(), 'logs')

def create_new_project(settings, projects_dir=None):
    """ creates a project:
            a new directory in the "projects" directory
            a json file containing the setting, within the new directory
            an empty vector_store directory
            an empty uploaded files directory
    """
    if not projects_dir:
        projects_dir = get_project_dir()
    if not os.path.exists(projects_dir):
        os.mkdir(projects_dir)

    project_id = get_ts(secsep='_')   # project ID is simply the timestamp in YYYYMMDD_hhmmss_fff format
    new_proj_path = os.path.join(projects_dir, project_id)

    # make sure the id is not already used.  If exists, get another, else make directory
    while os.path.exists(new_proj_path):
        time.sleep(0.005)
        project_id = get_ts(secsep='_')   # project ID is
        new_proj_path = os.path.join(projects_dir, project_id) # get another path if one already exists
    os.mkdir(new_proj_path)

    # write the settings as json to the new project directory
    settings_path = os.path.join(new_proj_path, SETTINGS_FILE_NAME)
    with open(settings_path, 'wt') as fp:
        json.dump(settings, fp)

    # make some directories
    dirs_to_make = ['archive', 'database', 'upload', 'vector_store', 'workspace']
    for new_dir in dirs_to_make:
        os.mkdir(os.path.join(new_proj_path, new_dir))

    #update the project list
    write_project_list()

    # finish up
    logit(f'Created project {project_id}')
    return project_id


def make_settings(**kwargs):
    """ makes a dictionary of project settings, with either defaults or values provided as keyword args
    """
    settings = Dict(
                    description='NIFTY - A New Item Form assistant.',
                    display_name = 'NIF',
                    project_type = 'Normal',
                    created_by = getpass.getuser(),
                    created_date = iso_now(),
                    last_used_date = iso_now(),
                    hidden = False,
                    chat_history = [],
                    llm_model = 'gpt-4o-mini',
                    greeting = "Which form field may I help you with today?",
                    system_prompt = "",
                    system_instruction = """You are an AI assistant developed to help project team members navigate and accurately populate the New Item Form(NIF).""",
                    )
    return settings | kwargs  # merge settings and kwargs - with kwargs overriding if same key in both


def create_template_project():
    return create_new_project(make_settings())


def create_test_projects(count=1, start=1, name_template='Test {i:03}'):
    project_ids_created = []
    for i in range(1,count+1):
        name = name_template.format(**locals())
        project_id = create_new_project(make_settings(description='For testing', display_name=name))
        project_ids_created.append(project_id)
    return project_ids_created


def get_projects(projects_dir=None):
    ''' returns Dict of projects and properties. Dict has keys by project type and "all" '''
    if not projects_dir:
        projects_dir = get_project_dir()
    projects = Dict()
    project_paths = glob(os.path.join(projects_dir, '2*'))  # only get directories starting with "2"
    for proj_path in project_paths:
        with open(os.path.join(proj_path, SETTINGS_FILE_NAME)) as fp:
            settings = Dict(json.load(fp))
        proj_type = settings.project_type
        uploaded_files_dir = os.path.join(proj_path, 'upload')
        uploaded_files = os.listdir(uploaded_files_dir)
        uploaded_file_sizes = [os.path.getsize(os.path.join(uploaded_files_dir, path)) for path in uploaded_files]

        if proj_type:
            project_id = os.path.split(proj_path)[-1]
            projects[proj_type] += [Dict(path=proj_path, project_id=project_id,uploaded_files=uploaded_files,
                                         uploaded_file_sizes=uploaded_file_sizes, settings=settings)]
            projects['All']  += [Dict(path=proj_path, project_id=project_id, uploaded_files=uploaded_files,
                                      uploaded_file_sizes=uploaded_file_sizes, settings=settings)]
        else:
            logit(f'\nWARNING. Project {proj_path} is missing project_type property\n')
    return projects


def write_project_list(projects_dir=None, descending=True):
    import pprint
    if not projects_dir:
        projects_dir = get_project_dir()
    project_list_path = os.path.join(projects_dir, 'project_list.txt')
    with open(project_list_path, 'wt') as fp:
        fp.write(pprint.pformat(get_projects_sorted(descending=descending)))


def get_projects_sorted(by='last_used_date', descending=True, project_type='All'):
    '''
    get a dict of projects

    Parameters
    ----------
    by : TYPE, optional
        DESCRIPTION. The default is 'last_used_date'.
    descending : TYPE, optional
        DESCRIPTION. The default is True.
    project_type : TYPE, optional
        DESCRIPTION. The default is 'All'.

    Returns
    -------
    dict
        DESCRIPTION. A dict with key=project_id, value=dict of project properties and settings. Entries will be in sorted order.

    '''
    projects = get_projects()
    if project_type not in projects:
        logit(f'Warning.  get_projects_sorted() finds NO projects with type={project_type}  ')
        return []
    key_ndx = [(proj.settings[by], i) for i, proj in enumerate(projects[project_type])]
    proj_ordered = [projects[project_type][ndx] for _, ndx in sorted(key_ndx, reverse=descending)]
    return Dict({project.project_id: project for project in proj_ordered})

def initialize_projects(test_project_count=3, name_template='Test {i:03}', fail_if_exists=False):
    """ This will create a projects folder within the top level directory of the AI Workshop app.
    The folder will be populated with <test_project_count> test projects.
    """
    projects_dir = get_project_dir()
    if os.path.exists(projects_dir):
        ## are there any projects?
        existing_projects = get_projects_sorted()
        project_count = len(existing_projects)
        if project_count and fail_if_exists:
            logit('initialize_projects: WARNING. ',
                  f'\t{project_count} projects already exist and {fail_if_exists=} was specified')
            return [proj.project_id for proj in existing_projects]  # return the ids
    ids_created = create_test_projects(count=test_project_count, start=1, name_template=name_template)
    return ids_created

def remove_project(project_id, archive=True):
    '''
    Remove a project either by moving it to archive (the default) or deleting it.

    Parameters
    ----------
    project_id : TYPE
        DESCRIPTION.
    archive : TYPE, optional
        DESCRIPTION. The default is True.

    Returns
    -------
    status_code : TYPE int
        DESCRIPTION.  Error count.  Zero is succesful removal.

    '''
    try:
        projects_dir = get_project_dir()
        proj_path = os.path.join(projects_dir, project_id)
        archive_dir = os.path.join(projects_dir, 'archive')
        if not os.path.exists(archive_dir):
            os.mkdir(archive_dir)
            logit(f'remove_project:  Created archive directory {archive_dir}')
        if not os.path.exists(proj_path):
            logit(f'remove_project:  ERROR. Project "{project_id}" not found.')
            return 1
        if archive:
            # move to archive
            shutil.move(proj_path, archive_dir)
            logit(f'remove_project:  Moved project "{project_id}" to {archive_dir}')
        else:
            shutil.rmtree(proj_path)
            logit(f'remove_project:  Deleted {proj_path}')
        write_project_list()  # update project list file to reflect the change
        return 0
    except Exception as error:
        logit(f'remove_project:  ERROR: {error}')
        return 99
#%%
def get_project_metadata(project_id):
    projects_dir = get_project_dir()
    proj_path = os.path.join(projects_dir, project_id)
    if not os.path.exists(proj_path):
        logit(f'get_project_metadata: ERROR. {proj_path} not found.')
    proj_meta_path = os.path.join(proj_path, SETTINGS_FILE_NAME)
    if not os.path.exists(proj_meta_path):
        logit(f'get_project_metadata: ERROR. {proj_meta_path} not found.')
    with open(proj_meta_path) as fp:
        settings = json.load(fp)
    uploaded_files_dir = os.path.join(proj_path, 'upload')
    uploaded_files = os.listdir(uploaded_files_dir)
    uploaded_file_sizes = [os.path.getsize(os.path.join(uploaded_files_dir, path)) for path in uploaded_files]
    metadata = Dict(path=proj_path, project_id=project_id,
                    uploaded_files=uploaded_files, uploaded_file_sizes=uploaded_file_sizes, settings=settings)
    return metadata


def update_project_metadata(metadata):
    if not isinstance(metadata, Dict):
        logit('update_project_metadata: WARNING. The metadata arg is not of type addict.Dict')
        if not isinstance(metadata, dict):
            logit('update_project_metadata: ERROR. The metadata arg must be Dict or dict')
            return
        metadata = Dict(metadata) # change the dict to Dict
    path = metadata.path
    settings = metadata.settings
    # write the settings as json to the new project directory
    settings_path = os.path.join(path, SETTINGS_FILE_NAME)
    with open(settings_path, 'wt') as fp:
        json.dump(settings, fp)
    write_project_list()
    logit(f'update_project_metadata: Updated {settings_path}')


def write_uploaded_files(project_id, list_of_contents, list_of_names, list_of_dates):
    '''
    writes out files using the data returned by dash dcc.Upload
    returns the updated metadata for the project
    '''
    uploaded = [list_of_contents, list_of_names, list_of_dates]
    min_len = min(map(len, uploaded))
    max_len = min(map(len, uploaded))
    if min_len != max_len:
        logit(f'write_uploaded_files: ERROR. args are different lengths: {list(map(len,uploaded))}  No files are written.')
        sys.exit(2)
    projects_dir = get_project_dir()
    proj_path = os.path.join(projects_dir, project_id)
    uploaded_files_dir = os.path.join(proj_path, 'upload')

    for content, name, date in zip(*uploaded):
        content_type, content_string = content.split(',')
        decoded = base64.b64decode(content_string)
        uploaded_file_path = os.path.join(uploaded_files_dir, name)
        # TODO check for duplicate  -  possible calc a hash to determine if 2 files with same name have same contents
        with open(uploaded_file_path, 'wb') as fp:
            fp.write(decoded)
            logit(f'{len(decoded)} bytes written to {uploaded_file_path}')

    metadata = get_project_metadata(project_id)
    update_project_metadata(metadata)
    return metadata



#%% TESTING
# *****************************************************************************

if  __name__ == "__main__" :
    pass

logit('-'*120)  # end of lib loading
