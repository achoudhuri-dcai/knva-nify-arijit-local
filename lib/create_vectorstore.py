#%% ABOUT
# *****************************************************************************
'''
This program creates the document vectorstore and database files for NIFTY, as
well as other data preparation steps that do not need to be run every time the
app starts.  This SHOULD be run whenever the databases or documents are updated.
'''
#%% PACKAGES & FUNCTIONS
# *****************************************************************************
import knova_utils as utils
import fa_lib as fa
import os
import inspect
import pandas as pd
import pdf2image
import urllib.parse
import botocore

def embed_pdf_multimodal(
        DOC:str                     # Full path to file
        ,COLLECTION:object          # ChromaDB collection to write to
        ,IMAGE_FOLDER:str           # Folder to store page images
        ,EMBEDDING_MODEL:object=utils.BedrockTitanEmbeddingFunction()     # Embedding model to use.
        ,SLEEP_IF_NEEDED:int=10     # Seconds to sleep between LLM calls, if there is a throttling exception
    ):
    funcname = inspect.currentframe().f_code.co_name

    print(f"<{funcname}> Processing document {DOC}...")

    # Create an image for each page
    file_dir, file_name, file_ext = utils.dirnamext(DOC)
    print(f"<{funcname}> Creating image for each page...")
    page_images = pdf2image.convert_from_path(
        DOC
        ,output_folder=IMAGE_FOLDER     # Write images to this folder
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

    page_summaries = []     # Initialize
    for i, path_to_page_image in enumerate(page_images):
        page_summary = '<NO SUMMARY>'   # Default
        retry = True
        page_retries = 0
        while retry:
            page_retries += 1 
            
            # Call the LLM to summarize the page
            print(f"<{funcname}> Creating summary for page {i+1} of {len(page_images)}...")
            try:
                page_summary = utils.query_multiple_images_bedrock([path_to_page_image], page_summary_prompt, page_summary_question)
                print(f"<{funcname}> Success!")
                retry = False   # Exit retry loop
            except botocore.exceptions.ClientError as error:
                if error.response['Error']['Code'] == 'ThrottlingException':
                    print(f"<{funcname}> LLM throttling exception.")
                    fa.sleep(SLEEP_IF_NEEDED)
                    # Will retry this page
                    if page_retries > 2:
                        print(f"<{funcname}> Max retries reached. Moving on.")
                        retry = False
                else:
                    print(f"<{funcname}> boto3 error: {error}")
                    print("Moving on.")
                    retry = False   # Error besides throttling. Exit retry loop.
            except Exception as e:
                print(f"<{funcname}> Exception: {e}")
                print("Moving on.")
                retry = False    # Another error processing this page. Move on to next page.
            
        page_summaries.append(page_summary)

        # Define document ID
        # Must be unique for each page
        pageimage_dir, pageimage_name, pageimage_ext = utils.dirnamext(path_to_page_image)
        doc_id = pageimage_name

        # Create embedding from page summary
        print(f"<{funcname}> Creating embedding for page {i+1} summary...")
        page_summary_embedded = EMBEDDING_MODEL([page_summary])

        # Simple: return the summary
        # relevant_document = page_summary

        # More complex: return the image for the single page to go with the summary
        relevant_document = path_to_page_image

        # # Still more complex: define dictionary to return when retriever finds a relevant page summary
        # # Return the image for that page and the pages on either side of it.
        # # Can also add a URL for the page, if you have it.
        # # This will be stored as a string in the vectorstore. You must tell the LLM to interpret it as a dictionary after retrieval.
        # relevant_document = {
        #     "Page summary":page_summary
        #     ,"Page images":page_images[start:end]
        #     ,"Page URL":link_to_page
        # }

        # Add to vectorstore
        # Upsert: if document IDs already exist in the vectorstore, replace. Otherwise, add new.
        COLLECTION.upsert(
            ids=doc_id
            ,embeddings=page_summary_embedded               # The thing to search with a user query
            ,documents=str(relevant_document)               # The thing to return when a query gets a hit. Note coercion to string.
            ,metadatas=[{                                   # Metadata
                "document_name":f"{file_name}.{file_ext}"   # File name
                ,"page_number":f"{i+1}"                     # Page number
            }]
        )
        print(f"<{funcname}> Page {i+1} from document {file_name}.{file_ext} added to vectorstore.")
                
    print(f"<{funcname}> Document {DOC} done.")

    return page_images, page_summaries

def save_page_summaries(
        PAGE_IMAGES:list[str]
        ,PAGE_SUMMARIES:list[str]
        ,OUTPATH:str
        ,LABEL:str
    ):
    funcname = inspect.currentframe().f_code.co_name

    page_images_with_summaries = {}
    for i, page_summary in enumerate(PAGE_SUMMARIES):
        page_images_with_summaries[PAGE_IMAGES[i]] = page_summary
    outfile = os.path.join(OUTPATH, f"{LABEL} PAGE SUMMARY LOOKUP.pkl.gz")
    utils.save_to_pickle(page_images_with_summaries, outfile)
    print(f"<{funcname}> {outfile} created.")

    page_summaries_prettystring = '\n\n   <<<PAGE BREAK>>>\n\n'.join(PAGE_SUMMARIES)
    outfile = os.path.join(OUTPATH, f"{LABEL} PAGE SUMMARY LOOKUP.pkl.gz")
    utils.save_to_pickle(page_summaries_prettystring, os.path.join(OUTPATH, f"{LABEL} PAGE SUMMARIES PLAINTEXT.txt"))
    print(f"<{funcname}> {outfile} created.")

    return None

# To turn a filename into a link to a local file
# Note this assumes a specific folder and local host port
local_host_with_port = '127.0.0.1:8052'
def get_web_url(filename):
    if str(filename) == 'nan':
        file_link = ''
    else:
        encoded_filename = urllib.parse.quote(filename)
        # encoded_filename = filename.replace(' ', '%20').replace('.', '%2E')
        # file_link = f"{local_host_with_port}/assets/raw_docs/{encoded_filename}"
        file_link = f"/assets/raw_docs/{encoded_filename}"
    return file_link

#%% PATHS & CONSTANTS
# *****************************************************************************
'''
These are defined in knova_utils.py.
'''
#%% CREATE OR LOAD VECTORSTORE
# *****************************************************************************
'''
Idea: create multiple collections. If you want to ensure you get results from
a variety of documents, put those documents in separate collections and submit
your query to all collections.
'''
chroma_database = utils.get_vectorstore(utils.VECTORSTORE_FOLDER)

'''
# Check vectorstore
utils.get_vectorstore(utils.VECTORSTORE_FOLDER)

# Delete collection
chroma_database.delete_collection(name='collection_3')
chroma_database.delete_collection(name='collection_4')
chroma_database.delete_collection(name='collection_5')

# Clear the whole vectorstore
utils.clear_vectorstore(utils.VECTORSTORE_FOLDER)
'''

#%% EMBED MULTIMODAL DOCS
# *****************************************************************************
'''
Want to handle PDFs and slides with full multimodal support.

UPDATE: for demo, using only 2 collections (full training deck and setup type guide).
'''
# =============================================================================
#### Full training deck
# =============================================================================
'''
Going in collection 1.

Run time: 1h 34m
'''
collection_1 = chroma_database.get_or_create_collection(name='nif_training_deck')

fa.timerstart('NIF Training Deck')
page_images, page_summaries = embed_pdf_multimodal(
    DOC=os.path.join(utils.DOCUMENT_FOLDER ,'NIF Training Deck v4.pdf')
    ,COLLECTION=collection_1              # ChromaDB collection to write to
    ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
)
save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, 'NIF Training Deck v4')
fa.timerstop()

# =============================================================================
#### Product Setup Type Guide
# =============================================================================
'''
Going in collection 2
'''
collection_2 = chroma_database.get_or_create_collection(name='setup_type_guide')

page_images, page_summaries = embed_pdf_multimodal(
    DOC=os.path.join(utils.DOCUMENT_FOLDER ,'Setup Type Guide.pdf')
    ,COLLECTION=collection_2              # ChromaDB collection to write to
    ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
)
save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, 'Setup Type Guide')

# =============================================================================
#### CASE NIF Training Deck
# =============================================================================
'''
Going in collection 3
'''
# collection_3 = chroma_database.get_or_create_collection(name='collection_3')
#
# page_images, page_summaries = embed_pdf_multimodal(
#     DOC=os.path.join(utils.DOCUMENT_FOLDER, 'Data-Ops-NIF-Create-a-CASE-Training-Deck---11.24.pdf')
#     ,COLLECTION=collection_3              # ChromaDB collection to write to
#     ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
# )
# save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, 'Data-Ops-NIF-Create-a-CASE-Training-Deck')

# =============================================================================
#### RX Guide
# =============================================================================
'''
Going in collection 4
'''
# collection_4 = chroma_database.get_or_create_collection(name='collection_4')
#
# page_images, page_summaries = embed_pdf_multimodal(
#     DOC=os.path.join(utils.DOCUMENT_FOLDER, 'RX Guide on Creating an NIF for RX BAR and RX WIP 5.8.25.pdf')
#     ,COLLECTION=collection_4              # ChromaDB collection to write to
#     ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
# )
# save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, 'RX Guide on Creating an NIF for RX BAR')

# =============================================================================
#### RX WIP Quick Reference
# =============================================================================
'''
Going in collection 5
'''
# collection_5 = chroma_database.get_or_create_collection(name='collection_5')
#
# page_images, page_summaries = embed_pdf_multimodal(
#     DOC=os.path.join(utils.DOCUMENT_FOLDER ,'RX WIP Set-up Process Quick Reference Guide.pdf')
#     ,COLLECTION=collection_5              # ChromaDB collection to write to
#     ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
# )
# save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, 'RX WIP Set-up Process Quick Reference Guide')

# =============================================================================
#### Testing
# =============================================================================
'''
test_query = 'What does subtype mean?'
test_query = 'What does product type mean?'
test_query = 'What does brand name mean?'
test_query = 'How do I know what the brand is?'
test_query = 'What is a planning variant?'

test_query = 'How do I select the correct product type and subtype?'

test_query = 'Find documents on club products in Canada.'

test_retrieval = utils.query_vectorstore(
    FOLDER_PATH=utils.VECTORSTORE_FOLDER
    ,QUERY=test_query
    ,N_RESULTS=3
)

num_collections_used = len(test_retrieval['documents'])

test_retrieval['documents'][0][0]   # First index selects collection. Second index selects document from that collection.
test_retrieval['metadatas'][0][0]['document_name']
test_retrieval['metadatas'][0][0]['page_number']

# Testing image query function
base_path_images = '/assets/doc_images_and_summaries'
base_path_docs = '/assets/raw_docs'

retrieved_page_images = []  # Initialize
retrieved_page_links = []         # Initialize
for i, CLCT in enumerate(test_retrieval['documents']):
    for j, DOC in enumerate(test_retrieval['documents'][i]):
        # Get link to page image
        ret_image = test_retrieval['documents'][i][j]
        image_file_without_path = os.path.basename(ret_image)
        image_file_new_path = f"{base_path_images}/{image_file_without_path}"
        retrieved_page_images.append(image_file_new_path)

        # Get link to page in PDF viewer
        doc_name = test_retrieval['metadatas'][i][j]['document_name']
        page_num = test_retrieval['metadatas'][i][j]['page_number']
        encoded_doc_name = urllib.parse.quote(doc_name)
        link_to_page = f"{base_path_docs}/{encoded_doc_name}#page={page_num}"
        retrieved_page_links.append(link_to_page)

# Call image query function to generate answer based on page images
image_query_prompt = "You will be given a set of images of pages from documents. The pages may contain text, tables, graphs, and images. Use them to answer the user's question."

answer_from_images = utils.query_multiple_images_azureoai(retrieved_page_images, image_query_prompt, test_query)
'''
