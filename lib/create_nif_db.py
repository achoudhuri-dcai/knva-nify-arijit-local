#%% ABOUT
# *****************************************************************************
'''
'''
#%% PACKAGES & FUNCTIONS
# *****************************************************************************
import os
import inspect
import pandas as pd
import numpy as np
import subprocess
import urllib.parse
import knova_utils as utils
import data_processing_utilities as dpu

# This function uses SQLiteBiter to create a SQLite database from an input file.
# This will first check whether the SQLite database file already exists. If so,
# it will not be recreated unless OVERWRITE_DATABASE is set to True. If
# OVERWRITE_DATABASE is False, a new table will be appended to the existing
# database.
#
# This requires SQLiteBiter to be installed, which can be done with pip:
#   pip install sqlitebiter
#
# For Excel files with multiple tabs, each tab will become a table in the database.
def create_database_from_flatfile(
        SOURCE_FILE:str             # String: full path to a source file. Can be .xlsx, .csv, .json, .html.
        ,DATABASE_FILE:str          # String: full path to a .db file. Will be created if it doesn't exist.
        ,OVERWRITE_DATABASE=False   # True: overwrite existing database. False: if database already exists, append table to it.
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Check if database file exists
    if os.path.isfile(DATABASE_FILE):   # If database exists...
        print(f"<{funcname}> File already exists: {DATABASE_FILE}.")
        if OVERWRITE_DATABASE:          # If overwrite=True...
            print(f"<{funcname}> Overwriting.")
            CMD = [
                'sqlitebiter'
                ,'-o'
                ,DATABASE_FILE
                ,'file'
                ,SOURCE_FILE
            ]
        else:                           # If overwrite=False...
            print(f"<{funcname}> Appending {SOURCE_FILE}.")
            CMD = [
                'sqlitebiter'
                ,'-o'
                ,DATABASE_FILE
                ,'-a'
                ,'file'
                ,SOURCE_FILE
            ]
    else:   # If database does not exist...
        print(f"<{funcname}> Creating file {DATABASE_FILE} from source {SOURCE_FILE}.")
        CMD = [
            'sqlitebiter'
            ,'-o'
            ,DATABASE_FILE
            ,'file'
            ,SOURCE_FILE
        ]

    # Run command and print return code
    print(f"<{funcname}> Running: {' '.join(CMD)}")
    cmd_status = subprocess.run(CMD, capture_output=True, shell=False)
    print(f"<{funcname}> Ended with returncode = {cmd_status.returncode}")
    if cmd_status.returncode == 3221225477:
        print(f"<{funcname}> This return code indicates that a file was not found. Check your working directory and folder locations.")

    # Print stderr and stdout messages, if any
    stderr_list = []
    stdout_list = []
    if cmd_status.stderr:
        stderr_txt  = cmd_status.stderr.decode()
        stderr_list = stderr_txt.strip().splitlines()
        print(f"\n<{funcname}> stderr messages:")
        for line in stderr_list:
            print(f"    {line}")
    if cmd_status.stdout:
        stdout_txt  = cmd_status.stdout.decode()
        stdout_list = stdout_txt.strip().splitlines()
    print(f"\n<{funcname}> stdout messages (limited to 99 lines):")
    for line in stdout_list[:99]:
        print(f"    {line}")

    return None

#%% PATHS & CONSTANTS
# *****************************************************************************
'''
These are defined in knova_utils.py.
'''
#%% READ DATA
# *****************************************************************************
#!!! For dev, using data from the POC
nifs_file = os.path.join(utils.DOCUMENT_FOLDER, 'NIFS.csv')

nifs_raw = pd.read_csv(nifs_file)
datetime_cols = [col for col in list(nifs_raw) if '_End' in col or '_Start' in col]
del nifs_raw

nifs_imp = pd.read_csv(
    nifs_file
    ,parse_dates=datetime_cols
)
# nifs_imp = dpu.cleancolnames(nifs_imp)
dpu.datainfo(nifs_imp)

#%% CALCS AND MERGE
# *****************************************************************************
# =============================================================================
#### Add column(s) with detail on stage where NIF is sitting
# =============================================================================
nifs_with_stage = nifs_imp.copy()

# This is based on Bev's document NIF Status Determination.xlsx
def check_requestor_initiate_status(r):
    if r.RQ == "C":
        return_string = 'Complete'
    elif r.RQ == "R" and r.Status == "Return to Req by LIM Phase 1":
        return_string = f"RETURNED TO {r.REQUESTOR} AFTER {r.LIMR_Start}"
    elif r.RQ == "R":
        return_string = f"RETURNED TO {r.REQUESTOR}"
    elif r.RQ == "X":
        return_string = f"IN PROCESS WITH {r.REQUESTOR} AS OF {r.Created}"
    else:
        return_string = 'N/A'
    return return_string
nifs_with_stage['check_requestor_initiate_status'] = nifs_with_stage.apply(check_requestor_initiate_status, axis=1)

def check_requestor_update_status(r):
    if r.RU == "C":
        return_string = 'Complete'
    elif r.RU == "R":
        return_string = f"RETURNED TO {r.REQUESTOR}"
    elif r.RU == "X":
        return_string = f"IN PROCESS WITH {r.REQUESTOR} AS OF {r.RU_Start}"
    else:
        return_string = 'N/A'
    return return_string
nifs_with_stage['check_requestor_update_status'] = nifs_with_stage.apply(check_requestor_update_status, axis=1)

def check_randd_quality_status(r):
    if r.RD == "C":
        return_string = 'Complete'
    elif r.RD == "X":
        return_string = f"IN PROCESS WITH {r.PR_RDQ} AS OF {r.RDQ_Start}"
    else:
        return_string = 'N/A'
    return return_string
nifs_with_stage['check_randd_quality_status'] = nifs_with_stage.apply(check_randd_quality_status, axis=1)

def check_nutrition_labeling_status(r):
    if r.NL == "C":
        return_string = 'Complete'
    elif r.NL == "X":
        return_string = f"IN PROCESS WITH {r.PR_NL} AS OF {r.NL_Start}"
    else:
        return_string = 'N/A'
    return return_string
nifs_with_stage['check_nutrition_labeling_status'] = nifs_with_stage.apply(check_nutrition_labeling_status, axis=1)

def check_packaging_tech_status(r):
    if r.PT == "C":
        return_string = 'Complete'
    elif r.PT == "R":
        return_string = f"RETURNED TO {str(r.PR_PT_MEN) + ' ' + str(r.PR_PT_BPS) + ' ' + str(r.PR_PT_CA)} AFTER {r.PT_Start}"
    elif r.PT == "X":
        return_string = f"IN PROCESS WITH {str(r.PR_PT_MEN) + ' ' + str(r.PR_PT_BPS) + ' ' + str(r.PR_PT_CA)} AS OF {r.PT_Start}"
    else:
        return_string = 'N/A'
    return return_string
nifs_with_stage['check_packaging_tech_status'] = nifs_with_stage.apply(check_packaging_tech_status, axis=1)

def check_epm_finance_status(r):
    if r.EF == "C":
        return_string = 'Complete'
    elif r.EF == "X":
        return_string = f"IN PROCESS WITH {r.PR_EPM} AS OF {r.EPM_Start}"
    else:
        return_string = 'N/A'
    return return_string
nifs_with_stage['check_epm_finance_status'] = nifs_with_stage.apply(check_epm_finance_status, axis=1)

def check_data_integrity_review_status(r):
    if r.DIR == "C":
        return_string = 'Complete'
    elif r.DIR == "X":
        return_string = f"IN PROCESS WITH {str(r.PR_DICA) + ' ' + str(r.PR_DI)} AS OF {r.DIR_Start}"
    else:
        return_string = 'N/A'
    return return_string
nifs_with_stage['check_data_integrity_review_status'] = nifs_with_stage.apply(check_data_integrity_review_status, axis=1)

def check_lim_update_status(r):
    if r.LM == "C":
        return_string = 'Complete'
    elif r.LM == "X":
        return_string = f"IN PROCESS WITH {r.LIM} AS OF {r.LIMU_Start}"
    else:
        return_string = 'N/A'
    return return_string
nifs_with_stage['check_lim_update_status'] = nifs_with_stage.apply(check_lim_update_status, axis=1)

def check_category_finance_status(r):
    if r.CF == "C":
        return_string = 'Complete'
    elif r.CF == "X":
        return_string = f"IN PROCESS WITH {r.PR_CF} AS OF {r.CF_Start}"
    else:
        return_string = 'N/A'
    return return_string
nifs_with_stage['check_category_finance_status'] = nifs_with_stage.apply(check_category_finance_status, axis=1)

def check_canada_tax_status(r):
    if r.CAT == "C":
        return_string = 'Complete'
    elif r.CAT == "X":
        return_string = f"IN PROCESS WITH Canada Tax"
    else:
        return_string = 'N/A'
    return return_string
nifs_with_stage['check_canada_tax_status'] = nifs_with_stage.apply(check_canada_tax_status, axis=1)

def check_data_integrity_hierarchy_status(r):
    if r.DIH == "C":
        return_string = 'Complete'
    elif r.DIH == "X":
        return_string = f"IN PROCESS WITH {str(r.PR_DICA) + ' ' + str(r.PR_DI)} AS OF {r.DIH_Start}"
    else:
        return_string = 'N/A'
    return return_string
nifs_with_stage['check_data_integrity_hierarchy_status'] = nifs_with_stage.apply(check_data_integrity_hierarchy_status, axis=1)

def check_lim_approval_dashboard_status(r):
    if r.DB == "C":
        return_string = 'Complete'
    elif r.DB == "X":
        if r.RQ != "X" and r.RU != "X" and r.RD != "X" and r.NL != "X" and r.PT != "X" and r.EF != "X" and r.DIR != "X" and r.LM != "X" and r.CF != "X" and r.CAT != "X" and r.DIH != "X":
            return_string = f"IN LIM APPROVAL WITH {r.LIM} AS OF {max(r.RU_End, r.RDQ_End, r.NL_End, r.PT_End, r.EPM_End, r.DIR_End, r.LIMU_End, r.CF_End, r.CAT_End, r.DIH_End)}"
        else:
            return_string = 'N/A'
    else:
        return_string = 'N/A'
    return return_string
nifs_with_stage['check_lim_approval_dashboard_status'] = nifs_with_stage.apply(check_lim_approval_dashboard_status, axis=1)

def check_masterfiles_status(r):
    if r.MF == "C":
        return_string = 'Complete'
    elif r.MF == "X":
        if r.RQ != "X" and r.RU != "X" and r.RD != "X" and r.NL != "X" and r.PT != "X" and r.EF != "X" and r.DIR != "X" and r.LM != "X" and r.CF != "X" and r.CAT != "X" and r.DIH != "X" and r.DB != "X":
            return_string = f"IN PROCESS WITH {r.PR_MF} AS OF {r.MF_Approval_Start_Date}"
        else:
            return_string = 'N/A'
    else:
        return_string = 'N/A'
    return return_string
nifs_with_stage['check_masterfiles_status'] = nifs_with_stage.apply(check_masterfiles_status, axis=1)

# Determine which detailed status to report
# - The first one that is not "Complete" or "N/A"
detailed_status_columns = [
    'check_requestor_initiate_status'
    ,'check_requestor_update_status'
    ,'check_randd_quality_status'
    ,'check_nutrition_labeling_status'
    ,'check_packaging_tech_status'
    ,'check_epm_finance_status'
    ,'check_data_integrity_review_status'
    ,'check_lim_update_status'
    ,'check_category_finance_status'
    ,'check_canada_tax_status'
    ,'check_data_integrity_hierarchy_status'
    ,'check_lim_approval_dashboard_status'
    ,'check_masterfiles_status'
]
def fill_detailed_status(r):
    for COL in detailed_status_columns:
        if r[COL] != 'Complete' and r[COL] != 'N/A':
            return_value = r[COL]
            break   # Once you have a value, exit the loop
        else:
            return_value = '<NOT FOUND>'
    return return_value
nifs_with_stage['Detailed Status'] = nifs_with_stage.apply(fill_detailed_status, axis=1)

# Check: crosstab detailed status with status_name. Don't worry about Canceled or Rejected.
check_detailed_status = nifs_with_stage[['Detailed Status', 'Status_Name']].value_counts()

# =============================================================================
#### Add pdf links
# =============================================================================
#!!! The sample Becky shared only has 100 NIFs. Will pull the full file from S3 when available.
#!!! Format these to open in a new tab. Either here or in Dash.
# Return a complete HTML anchor tag string with target="_blank"
# return f'<a href="{web_url}" target="_blank">{display_name}</a>'
nif_pdf_lookup = pd.read_excel(os.path.join(utils.DOCUMENT_FOLDER, 'NIF Repository (1).xlsx'))
nif_pdf_lookup = dpu.cleancolnames(nif_pdf_lookup)
dpu.datainfo(nif_pdf_lookup)

'''
Plan for merging PDF Links to NIF database:
    - Name looks like concatenation of <Material Number><Title>, where Title matches to NIF database
    - Parse these, and:
        1. Match on Material Number
        2. Check that Title matches
        3. Check that Modified date matches
'''
# Parse Name
# Take the first 14 characters (expected length of material number plus some buffer), then remove any non-numeric
nif_pdf_lookup['parsed_matnum'] = nif_pdf_lookup['name'].str[:14].replace(r'\D', '', regex=True)

# Remove the parsed material number to get the title
nif_pdf_lookup['parsed_title'] = nif_pdf_lookup.apply(lambda row: row['name'].replace(row['parsed_matnum'], ''), axis=1)
nif_pdf_lookup['parsed_title'] = nif_pdf_lookup['parsed_title'].str.replace('-', '').str.strip()

# Coerce to numeric
nif_pdf_lookup['parsed_matnum'] = pd.to_numeric(nif_pdf_lookup['parsed_matnum'], errors='coerce')

# Remove missing parsed_matnum
nif_pdf_lookup_tomerge = nif_pdf_lookup.dropna(subset='parsed_matnum')

# Merge
nifs_with_pdf = pd.merge(
    left=nifs_with_stage
    ,right=nif_pdf_lookup_tomerge
    ,left_on='Material_Number'
    ,right_on='parsed_matnum'
    ,how='left'
    ,indicator=True
)
nifs_with_pdf['_merge'].value_counts()

#%% WRITE DATABASE
# *****************************************************************************
# Output flat file
#! Filename here determines table name in database!
output_flatfile = os.path.join(utils.DOCUMENT_FOLDER ,'NIFS_prepped.csv')
nifs_with_pdf.to_csv(output_flatfile, index=False)

# Convert to database
#!!! Return code = 1, but no stderr messages?
create_database_from_flatfile(
    SOURCE_FILE=output_flatfile
    ,DATABASE_FILE=os.path.join(utils.DATABASE_FOLDER, 'NIFS_prepped.db')  # String: full path to a .db file. Will be created if it doesn't exist.
    ,OVERWRITE_DATABASE=True   # True: overwrite existing database. False: if database already exists, append table to it.
)

#%% OTHER DATABASES
# *****************************************************************************
# =============================================================================
#### Active Brands
# =============================================================================
# create_database_from_flatfile(
#     SOURCE_FILE=os.path.join(utils.DOCUMENT_FOLDER ,'KNV Active Brands 07-24-2024.xlsx')
#     ,DATABASE_FILE=os.path.join(utils.DATABASE_FOLDER, 'KNV_Active_Brands.db')  # String: full path to a .db file. Will be created if it doesn't exist.
#     ,OVERWRITE_DATABASE=True   # True: overwrite existing database. False: if database already exists, append table to it.
# )

# =============================================================================
#### NIF Field Lookup
# =============================================================================
'''
This is Bev's NIF field lookup table.

I have lightly modified the file for creating a database:
- Deleted the first two rows (containing notes)
- Deleted all tabs except for "All sections of NIF PDF"
'''
# create_database_from_flatfile(
#     SOURCE_FILE=os.path.join(utils.DOCUMENT_FOLDER, 'Kellogg Nifty - All sections of NIF v2 20250929 FOR APP.xlsx')
#     ,DATABASE_FILE=os.path.join(utils.DATABASE_FOLDER, 'NIF_field_lookup.db')  # String: full path to a .db file. Will be created if it doesn't exist.
#     ,OVERWRITE_DATABASE=True   # True: overwrite existing database. False: if database already exists, append table to it.
# )
