#%% ABOUT
# *****************************************************************************
'''
This program prepares files for use with LLMs in a RAG application. It is meant
to be part of a general-use app where the user can upload files of various types.
It should have the following features:
    - Ability to handle multiple file types: CSV, Word, PDF, Excel, JPG.
    - Sensible defaults so it can be run without any arguments apart from the basics (filenames, folder locations).
    - Logging of progress including warnings and errors.

Want to be able to provide links to source documents in citations. In the past,
we have done this by uploading files to Azure blob storage. However, this may
be unnecessary. Ideally, the chat server will be able to serve up the documents
from the same place the user uploads are stored.

Important notes:
    - This will create new files. It needs write access to the disk.
    - Watch disk space. In addition to the files uploaded by the user, this will create:
        - A multivector retriever for each user-defined project. This contains a Chroma.db file, a docstore.pkl, and a set of binaries.
        - An image file for each page of each uploaded PDF.
        - A SQLite database for each uploaded Excel file (intelligent processing could put all Excel files for a project into a single database if needed).
    - We may want an automatic cleanup process, e.g., projects that haven't been used in 30 days have their uploaded documents (and the generated vector store, images, and databases) deleted.

Logging:
    - Ken's websocket code will read the file log.txt and show any lines starting with double underline (__) to the user.
    - Indicate the completion of a process with __complete (? ask Ken).

Docstore management
-------------------------------------
Exploring vectorstore management functions and developing user-friendly ways to do things like:
    - Browse the contents of a vectorstore by using base retriever or metadata search
    - Delete or replace a document, identifying it by its title
        - this must be translated into whatever document ID the vectorstore is using internally
    - Ability to remove individual documents from the vector store using Chroma's .delete method: https://python.langchain.com/docs/integrations/vectorstores/chroma/#update-and-delete
        - Must refer to documents by their id_key, which is auto-generated in fa.add_to_mvretriever() function. An alternative is to interact with Chroma directly.
        - Look up mdelete method

Using metadata filters during retrieval:
    retriever.invoke("Stealing from the bank", filter={"source": "news"})
'''

history = '''
Revision_history
================
    2025-1-9   jr   Initial version
    2025-4-17  jr   Begin work on conversion away from Langchain
    2025-4-30  jr   Mostly working with Chroma
'''

#%% PACKAGES & CONSTANTS
# *****************************************************************************
# =============================================================================
#### Packages
# =============================================================================
import os, sys, inspect
import importlib.metadata as implib
import lib.fa_lib as fa
import pandas as pd
import pdf2image
import sqlite3
import chromadb
import chromadb.utils.embedding_functions as chembed

# import langchain.text_splitter as lcsplit
# from langchain.retrievers.multi_vector import MultiVectorRetriever

# =============================================================================
#### Constants
# =============================================================================
CURRENT_FOLDER = os.getcwd()
PROJECTS_FOLDER = r'F:\First Analytics\Solutions\Dash-AI\Dash_App\projects'

# Define embedding model
# This points to FA's Azure service and produces an embedding model with the correct format for Chroma
azure_text_embedding_model_chroma = chembed.OpenAIEmbeddingFunction(
    api_key='19051dde4b354ec097946442529cf2d6'
    ,api_base='https://faoai-01.openai.azure.com/'
    ,api_type='azure'
    ,api_version='2024-10-21'
    ,model_name='text-embedding-ada-002'
    ,deployment_id='text-embedding-ada-002'
)

#%% HELPER FUNCTIONS
# *****************************************************************************
logit = fa.logit

def dirnamext(FULL_PATH_TO_FILE:str) -> tuple([str, str, str]):
    directory = os.path.dirname(FULL_PATH_TO_FILE)
    file_name_with_ext = os.path.basename(FULL_PATH_TO_FILE)
    name, extension = file_name_with_ext.split('.')
    return directory, name, extension

def validate_file_type(
        FULL_PATH_TO_FILE:str
        ,ACCEPTED_FILE_TYPES:list[str]      # List of valid file extensions. With or without periods. Upper, lower, or mixed case OK.
    ) -> tuple([int, str]):
    funcname = inspect.currentframe().f_code.co_name

    ACCEPTED_FILE_TYPES = [ext.upper() for ext in ACCEPTED_FILE_TYPES]              # Convert to uppercase
    ACCEPTED_FILE_TYPES = [ext.replace('.', '') for ext in ACCEPTED_FILE_TYPES]     # Remove periods

    file_dir, file_name, file_ext = dirnamext(FULL_PATH_TO_FILE)
    if file_ext.upper() not in ACCEPTED_FILE_TYPES:
        rc = 1
        message = f"Invalid file type: {file_ext.upper()}. Valid types are: {ACCEPTED_FILE_TYPES}."
    else:
        rc = 0
        message = f"Valid file type: {file_ext.upper()}."
    return rc, message

# To get the document IDs from a retriever based on a question, a metadata filter, or both.
def get_doc_ids(
        RETRIEVER:object                # Langchain Vector or Multivector retriever object
        ,QUESTION:str=None              # Natural language question - will return documents just like a user question
        ,METADATA_FILTER:dict=None      # Dictionary with one or more entries {'metadata key':'filter value'}
    ):
    funcname = inspect.currentframe().f_code.co_name
    return doc_ids

# This function uses SQLiteBiter to create a SQLite database from an input file.
# This will first check whether the SQLite database file already exists. If so,
# it will not be recreated unless OVERWRITE_DATABASE is set to True. If
# OVERWRITE_DATABASE is False, a new table will be appended to the existing
# database.
#
# This requires SQLiteBiter to be installed, which can be done with pip:
#   pip install sqlitebiter
#
# Input file can be Excel, CSV, JSON, HTML, or others. For the full list, see:
# https://sqlitebiter.readthedocs.io/en/latest/pages/usage/file/index.html#supported-data-formats
#
# Run time: about 10 minutes to create a 12MB database from a 10k row / 200 col Excel file in testing.

# Example usage:
#	create_database_from_flatfile(
#		SOURCE_FILE=os.path.join(RAWDATA_FOLDER ,'COST DATA.xlsx')
#		,DATABASE_FILE=os.path.join(PRODATA_FOLDER ,'cost_data.db')
#       ,OVERWRITE_DATABASE=True
#	)
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

#%% VECTORSTORE FUNCTIONS
# *****************************************************************************
# To query a vectorstore
def query_vectorstore(
        PROJECTS_FOLDER:str     # Full path to app folder containing projects
        ,PROJECT_NAME:str       # The project name
        ,QUERY:str              # Query
        ,N_RESULTS:int=3        # Number of relevant docs to return
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Get project vectorstore
    project_folder = os.path.join(PROJECTS_FOLDER, PROJECT_NAME)
    project_vectorstore_folder = os.path.join(project_folder, 'vectorstore')
    chroma_database = chromadb.PersistentClient(path=os.path.join(project_vectorstore_folder, 'chromadb'))
    collection_list = chroma_database.list_collections()

    # Embed text with explicit call to embedding model
    query_texts = [QUERY]
    embedded_query_texts = azure_text_embedding_model_chroma(query_texts)

    # Do it
    if len(collection_list) == 0:
        logit(f"<{funcname}> Project vectorstore is empty. Exiting.")
    else:
        for collection_i in collection_list:    # If there are multiple collections, loop through
            collection = chroma_database.get_collection(name=collection_i.name)

            retrieved_docs = collection.query(
                query_embeddings=embedded_query_texts
                ,n_results=N_RESULTS

                # # Optional: add filters on metadata and keywords found in document
                # ,where={"metadata_field": "is_equal_to_this"}
                # ,where_document={"$contains":"search_string"}   # Can also do: {"$not_contains": "search_string"}
            )
            logit(f"<{funcname}> Collection {collection.name} returned {len(retrieved_docs['ids'][0])} documents:")
            logit(f"    Documents IDs: {retrieved_docs['ids'][0]}")

    return retrieved_docs

'''
test_query = 'operational tests'
test_retrieval = query_vectorstore(
    PROJECTS_FOLDER = 'F:\\First Analytics\\Solutions\\Dash-AI\\Dash_App\\projects'
    ,PROJECT_NAME='jr_test'
    ,QUERY=test_query
)
'''

# To print some basic information about a project's vectorstore.
def check_vectorstore(
        PROJECT_NAME:str            # The project name
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Get project vectorstore
    project_folder = os.path.join(PROJECTS_FOLDER, PROJECT_NAME)
    project_vectorstore_folder = os.path.join(project_folder, 'vectorstore')
    chroma_database = chromadb.PersistentClient(path=os.path.join(project_vectorstore_folder, 'chromadb'))

    # Do it
    collection_list = chroma_database.list_collections()
    logit(f"<{funcname}> Project {PROJECT_NAME} vectorstore contains {len(collection_list)} collection(s).")

    for collection_i in collection_list:    # If there are multiple collections, loop through
        collection = chroma_database.get_collection(name=collection_i.name)
        logit(f"<{funcname}> Collection '{collection.name}' contains {collection.count()} items.")

    return None

'''
PROJECTS_FOLDER = 'F:\\First Analytics\\Solutions\\Dash-AI\\Dash_App\\projects'
check_vectorstore(
    PROJECT_NAME='jr_test'
)
'''

# To remove individual documents from the project vectorstore.
# Note this requires that the vectorstore was created with metadata field
# 'document_name'.
#!!! Test: what does it do if document doesn't exist?
def remove_docs_from_vectorstore(
        PROJECT_NAME:str            # The project name
        ,REMOVE_DOCS:list[str]      # List of document names to remove
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Get project vectorstore
    project_folder = os.path.join(PROJECTS_FOLDER, PROJECT_NAME)
    project_vectorstore_folder = os.path.join(project_folder, 'vectorstore')
    chroma_database = chromadb.PersistentClient(path=os.path.join(project_vectorstore_folder, 'chromadb'))

    # Do it
    collection_list = chroma_database.list_collections()
    if len(collection_list) == 0:
        logit(f"<{funcname}> WARNING: Project vectorstore is empty. Exiting.")
    elif len(collection_list) > 1:
        logit(f"<{funcname}> WARNING: Project vectorstore contains multiple collections. Exiting.")
    else:
        collection = chroma_database.get_collection(name=collection_list[0].name)
        logit(f"<{funcname}> Before removal, vector store contains {collection.count()} items.")
        for doc_name in REMOVE_DOCS:
            collection.delete(
                # If no ids are supplied, delete all items in the collection that match the where filter
            	where={"document_name":doc_name}
            )
            logit(f"<{funcname}> All items for document {doc_name} removed from vectorstore.")
        logit(f"<{funcname}> After removal, vector store contains {collection.count()} items.")

    return None

'''
PROJECTS_FOLDER = 'F:\\First Analytics\\Solutions\\Dash-AI\\Dash_App\\projects'
remove_docs_from_vectorstore(
    PROJECT_NAME='jr_test'
    ,REMOVE_DOCS=['small_pdf']
)
'''

# To clear out the project vectorstore by removing all collections.
#!!! This does not delete the ChromaDB files from disk. Look into this.
# This is a known bug. See:
    # https://github.com/chroma-core/chroma/issues/1245
    # https://github.com/chroma-core/chroma/pull/1313
def clear_vectorstore(
        PROJECT_NAME:str            # The project name
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Get project vectorstore
    project_folder = os.path.join(PROJECTS_FOLDER, PROJECT_NAME)
    project_vectorstore_folder = os.path.join(project_folder, 'vectorstore')
    chroma_database = chromadb.PersistentClient(path=os.path.join(project_vectorstore_folder, 'chromadb'))

    # Do it
    collection_list = chroma_database.list_collections()
    if len(collection_list) == 0:
        logit(f"<{funcname}> Project vectorstore is empty. Exiting.")
    else:
        for collection_i in collection_list:    # If there are multiple collections, loop through
            logit(f"<{funcname}> Removing collection {collection_i.name} with {collection_i.count()} items.")
            chroma_database.delete_collection(collection_i.name)

    return None

'''
PROJECTS_FOLDER = 'F:\\First Analytics\\Solutions\\Dash-AI\\Dash_App\\projects'
clear_vectorstore(
    PROJECT_NAME='jr_test'
)
'''

#%% TEXT FILES
# *****************************************************************************
'''
Standard chunking and vector store.

TODO: Remove langchain functions.
'''
# def process_text_file(
#         DOC:str                     # Full path to file
#         ,WRITE_TO_RETRIEVER:object  # Langchain Multivector retriever object to write to
#         ,CHUNK_SIZE:int=1000
#         ,CHUNK_OVERLAP:int=100
#     ):
#     funcname = inspect.currentframe().f_code.co_name

#     # Check file type
#     accepted_file_types = ['.csv', '.doc', '.docx']    # Any case OK, with or without periods
#     type_rc, type_message = validate_file_type(DOC, accepted_file_types)
#     if type_rc != 0: raise Exception(type_message)

#     # Split document
#     chunk_size = CHUNK_SIZE
#     chunk_overlap = CHUNK_OVERLAP
#     doc_splitter = lcsplit.RecursiveCharacterTextSplitter(
#         chunk_size=chunk_size
#         ,chunk_overlap=chunk_overlap
#         ,separators=['\n\n' ,'\n' ,'\. ']
#     )
#     logit(f"<{funcname}> Processing document {DOC}...")
#     logit(f"<{funcname}> Splitting document into chunks...")
#     fa.timerstart()
#     doc_chunks = doc_splitter.split_documents(DOC)
#     fa.timerstop()
#     logit(f"<{funcname}> Document {DOC} done. {len(doc_chunks)} chunks created.")

#     logit(f"<{funcname}> See a sample of chunks below.")
#     for i in range(3):
#         logit("\n>", "-" * 50)
#         logit(f">    Chunk {i+1} of {len(doc_chunks)}")
#         logit(f">    Original file: {doc_chunks[i].metadata['source']}")
#         logit(f">    Original page: {doc_chunks[i].metadata['page']}")
#         logit('> Text:')
#         logit(doc_chunks[i].page_content)

#     # Add to MultiVectorRetriever
#     fa.add_to_mvretriever(
#         WRITE_TO_RETRIEVER
#         ,doc_chunks     # Searching document chunks
#         ,doc_chunks     # Returning document chunks
#     )

#     return None

#%% PDF
# *****************************************************************************
'''
All PDFs are handled the same, which is fully multimodal. We do not try to
determine whether they contain charts and images or text only.
'''
def process_pdf_file(
        DOC:str                     # Full path to file
        ,IMAGE_FOLDER:str           # Folder to store page images
        ,COLLECTION:object          # ChromaDB collection to write to
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Check file type
    accepted_file_types = ['.pdf']    # Any case OK, with or without periods
    type_rc, type_message = validate_file_type(DOC, accepted_file_types)
    if type_rc != 0: raise Exception(type_message)

    logit(f"<{funcname}> Processing document {DOC}...")

    # Create an image for each page
    file_dir, file_name, file_ext = dirnamext(DOC)
    logit(f"<{funcname}> Creating image for each page...")
    page_images = pdf2image.convert_from_path(
        DOC
        ,output_folder=IMAGE_FOLDER     # Write image to this folder
        ,output_file=file_name          # Base file name for images - use original file name
        ,paths_only=True                # True: do not store image in memory, only path to image
        ,fmt='jpeg'
        ,size=1200                      # Set longest side to 1200 pixels
    )

    page_summary_prompt = '''
    You are an AI assistant tasked with summarizing documents based on images of
    their pages. The pages may contain text, charts, and images. These summaries
    will be searched to find relevant documents to answer user questions. Give a
    concise summary of the document which is well optimized for search, being sure
    to mention all important elements including text, charts, and images. Include
    the document name and page number if available.
    '''
    page_summary_question = 'Summarize this page.'

    all_page_summaries = []     # Initialize
    for i, page_image in enumerate(page_images):

        # Call the LLM to summarize each page of the document
        logit(f"<{funcname}> Creating summary for page {i+1} of {len(page_images)}...")
        page_summary = fa.query_multiple_images_azureoai([page_image], page_summary_prompt, page_summary_question)
        all_page_summaries.append(page_summary)

        # Define document ID
        doc_id = page_image        # Use page image filename as unique ID

        # Create embedding from page summary
        logit(f"<{funcname}> Creating embedding for page {i+1} summary...")
        page_summary_embedded = azure_text_embedding_model_chroma([page_summary])

        # Simple: return the summary
        relevant_document = page_summary

        # More complex: return the image for the single page to go with the summary
        # relevant_document = page_image

        # # Return the image for that page and the pages on either side of it
        # # Define dictionary to return when retriever finds a relevant page summary
        # # This will be stored as a string in the vectorstore. You must tell the LLM to interpret it as a dictionary after retrieval.
        # start = max(i-1, 0)
        # end = min(i+2, len(all_page_summaries))
        # relevant_document = {
        #     "Source document":file_name
        #     ,"Page summary":page_summary
        #     ,"Page images":page_images[start:end]
        # }

        # Add to vectorstore
        # Upsert: if document IDs already exist in the vectorstore, replace. Otherwise, add new.
        COLLECTION.upsert(
            ids=doc_id
            ,embeddings=page_summary_embedded           # The thing to search with a user query
            ,documents=str(relevant_document)           # The thing to return when a query gets a hit. Note coercion to string.
            ,metadatas=[                                # File name goes in metadata
                {"document_name":file_name}
            ]
        )
        logit(f"<{funcname}> Page {i+1} from document {file_name} added to vectorstore.")
    logit(f"<{funcname}> Document {DOC} done.")

    return None

'''
test_file = 'F:\\First Analytics\\Solutions\\Dash-AI\\Dash_App\\projects\\jr_test\\upload\\small_pdf.pdf'
image_folder = 'F:\\First Analytics\\Solutions\\Dash-AI\\Dash_App\\projects\\jr_test\\workspace'

chroma_database = chromadb.PersistentClient(path='F:\\First Analytics\\Solutions\\Dash-AI\\Dash_App\\projects\\jr_test\\vectorstore\\chromadb')
collection_list = chroma_database.list_collections()
collection = chroma_database.get_collection(name=collection_list[0].name)

process_pdf_file(
    DOC=test_file               # Full path to file
    ,IMAGE_FOLDER=image_folder  # Folder to store page images
    ,COLLECTION=collection      # ChromaDB collection to write to
)
'''
#%% EXCEL
# *****************************************************************************
'''
Excel files are converted into SQLite databases. For now, we do not try to
"clean up" the file; we assume the first row is column headings

TODO: If it does not follow this format, throw an error.
'''
def process_excel_file(
        DOC:str                     # Full path to file
        ,OUTPUT_DATABASE:str        # Full path to database file (.db). Will be created if it doesn't exist. Otherwise, current document will be added as a new table.
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Check file type
    accepted_file_types = ['.xls', '.xlsx']    # Any case OK, with or without periods
    type_rc, type_message = validate_file_type(DOC, accepted_file_types)
    if type_rc != 0: raise Exception(type_message)

    logit(f"<{funcname}> Processing document {DOC}...")

    # Read file and write to database
    create_database_from_flatfile(
        SOURCE_FILE=DOC             # String: full path to a source file. Can be .xlsx, .csv, .json, .html.
        ,DATABASE_FILE=OUTPUT_DATABASE          # String: full path to a .db file. Will be created if it doesn't exist.
        ,OVERWRITE_DATABASE=False    # True: overwrite existing database. False: if database already exists, append table to it.
    )
    logit(f"<{funcname}> Document {DOC} done.")

    return None

#%% IMAGE
# *****************************************************************************
'''
We use an LLM to summarize each image. This summary is stored in a multivector
store for searching. Relevant hits return both the summary and the image.
'''
def process_image_file(
        DOC:str                     # Full path to file
        ,COLLECTION:object          # ChromaDB collection to write to
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Check file type
    accepted_file_types = ['.jpg', '.jpeg', '.png']    # Any case OK, with or without periods
    type_rc, type_message = validate_file_type(DOC, accepted_file_types)
    if type_rc != 0: raise Exception(type_message)

    logit(f"<{funcname}> Processing document {DOC}...")

    # Call the LLM to summarize the image
    image_summary_prompt = '''
    You are an AI assistant tasked with summarizing images. These summaries will
    be searched to find relevant images to answer user questions. Give a concise
    summary of the image which is well optimized for search.
    '''
    image_summary_question = 'Summarize this image.'
    logit(f"<{funcname}> Creating summary for image {DOC}...")
    image_summary = fa.query_multiple_images_azureoai([DOC], image_summary_prompt, image_summary_question)

    # Create embedding from image summary
    logit(f"<{funcname}> Creating embedding for image summary...")
    image_summary_embedded = azure_text_embedding_model_chroma([image_summary])

    # Define dictionary to return when retriever finds a relevant image summary
    image_with_summary = {
        "Image summary":image_summary
        ,"Image":DOC
    }

    # Add to vectorstore
    # Upsert: if document IDs already exist in the vectorstore, replace. Otherwise, add new.
    COLLECTION.upsert(
        ids=DOC
        ,embeddings=image_summary_embedded           # The thing to search with a user query
        ,documents=str(image_with_summary)          # The thing to return when a query gets a hit. Note coercion to string.
    )
    logit(f"<{funcname}> Document {DOC} added to vectorstore.")

    return None

#%% MAIN PROCESS
# *****************************************************************************
'''
The main function that handles files uploaded by the user. Its primary job is
to assign each file to the appropriate processing function.

Version 0 will pass one file at a time to each file handler. Later versions
could pass a list of files to each handler - need to ensure that each handler
can take list input.

Also consider executing all file handlers in parallel.

We can expect the web server to provide a list of files that are being uploaded.
Need to periodically recheck for files that have finished uploading.
If a file cannot be processed, move on to the next one and log it. Consider how
to notify user or project owner.

See KMA_Private_AI_Chat_Dash_UI_v04.py on Ken's branch.

See project properties: uploaded_files and uploaded_file_sizes
    current_project_metadata.

See Dash callback handle_uploads. Insert this function there to be kicked off.
'''
def process_files(
        FILE_LIST:list[str]             # List of uploaded file names (without path)
        ,PROJECT_NAME:str               # Name of project folder to put processed files in
        ,TRIES_PER_FILE:int=3           # Number of times to check whether a file exists (has finished uploading) before moving on to the next
        ,SLEEP_BETWEEN_TRIES:int=10     # Sleep this many seconds between checks for whether file exists
    ):
    funcname = inspect.currentframe().f_code.co_name

    # -------------------------------------------------------------------------
    # Initialize project folders, vector store, and database
    # -------------------------------------------------------------------------
    project_folder = os.path.join(PROJECTS_FOLDER, PROJECT_NAME)
    project_upload_folder = os.path.join(project_folder, 'upload')
    project_vectorstore_folder = os.path.join(project_folder, 'vectorstore')
    project_database_folder = os.path.join(project_folder, 'database')
    project_workspace_folder = os.path.join(project_folder, 'workspace')

    # Define ChromaDB location for this project
    chroma_database = chromadb.PersistentClient(path=os.path.join(project_vectorstore_folder, 'chromadb'))

    # Check if a Chroma collection already exists. If so, load it. If not, create it.
    collection_list = chroma_database.list_collections()
    if len(collection_list) > 0:
        logit(f"<{funcname}> Loading existing vectorstore.")
        collection = chroma_database.get_collection(name=collection_list[0].name)
        logit(f"<{funcname}> Vectorstore loaded with {collection.count()} items.")
    else:
        logit(f"<{funcname}> Creating new vectorstore.")
        collection = chroma_database.create_collection(
            name='collection_1'
            ,embedding_function=azure_text_embedding_model_chroma
        )

    # # Create vectorstore folder if needed
    # # Will also create project_folder if needed
    # try:
    #     os.makedirs(project_vectorstore_folder, exist_ok=False)     # exist_ok = False: throw an error if the directory already exists.
    #     logit(f"<{funcname}> New vectorstore folder created: {project_vectorstore_folder}.")
    # except FileExistsError:
    #     logit(f"<{funcname}> Using existing vectorstore folder: {project_vectorstore_folder}.")

    # # Create database folder if needed
    # try:
    #     os.makedirs(project_database_folder, exist_ok=False)     # exist_ok = False: throw an error if the directory already exists.
    #     logit(f"<{funcname}> New database folder created: {project_database_folder}.")
    # except FileExistsError:
    #     logit(f"<{funcname}> Using existing database folder: {project_database_folder}.")
    #!!! project_database = os.path.join(project_database_folder, 'database.db')

    # # Create workspace folder if needed
    # try:
    #     os.makedirs(project_workspace_folder, exist_ok=False)     # exist_ok = False: throw an error if the directory already exists.
    #     logit(f"<{funcname}> New image folder created: {project_workspace_folder}.")
    # except FileExistsError:
    #     logit(f"<{funcname}> Using existing image folder: {project_workspace_folder}.")

    # -------------------------------------------------------------------------
    # Loop through uploaded files, calling appropriate file processing function
    # -------------------------------------------------------------------------
    logit(f"<{funcname}> Processing {len(FILE_LIST)} uploaded files:")
    logit(f"    {[fname for fname in FILE_LIST]}")
    for i, filename in enumerate(FILE_LIST):
        logit(f"<{funcname}> Processing file {i+1} of {len(FILE_LIST)}: {filename}...")
        file_with_path = os.path.join(project_upload_folder, filename)

        tries = 0
        while tries < TRIES_PER_FILE:
            tries += 1
            if os.path.exists(file_with_path):
                logit(f"<{funcname}> File found, processing...")

                # Each file processing function first checks whether the given file is of the correct type. It wouldn't be any faster to check before trying the function.
                #TODO: Add error messages from each processing function
                try:
                    process_text_file(file_with_path, collection)
                    break
                except:
                    try:
                        process_pdf_file(file_with_path, project_workspace_folder, collection)
                        break
                    except:
                        try:
                            process_excel_file(file_with_path, project_database)
                            break
                        except:
                            try:
                                process_image_file(file_with_path, collection)
                                break
                            except:
                                logit(f"<{funcname}> Error processing file.")

            else:                   # If file does not exist, assume it hasn't finished uploading yet. Wait and try again.
                logit(f"<{funcname}> File not found, waiting for upload to finish...")
                fa.sleep(SLEEP_BETWEEN_TRIES)
                continue

        else:                       # Enough tries on that file, go to next one
            logit(f"<{funcname}> File {file_with_path} not found, moving on to next one.")
            if i+1 == len(FILE_LIST):
                logit(f"<{funcname}> End of file upload list.")
            continue

    logit(f"<{funcname}> Project vectorstore contains {collection.count()} items.")

    return None

'''
test_files = [
    'test1.csv'         # This one doesn't exist
    ,'small_pdf.pdf'
]
process_files(test_files, 'jr_test', SLEEP_BETWEEN_TRIES=2)
'''
