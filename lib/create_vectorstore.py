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
import os
import inspect
from datetime import datetime as dt
import pandas as pd
import urllib.parse

#%% PATHS & CONSTANTS
# *****************************************************************************
'''
These are defined in knova_utils.py.
'''
#%% NIF TRAINING DECK ONLY
# *****************************************************************************
# =============================================================================
#### Define folder for this vectorstore
# =============================================================================
vectorstore_folder = os.path.join(utils.VECTORSTORE_FOLDER, 'nif_training_deck_only')

chroma_database = utils.get_or_create_vectorstore(vectorstore_folder)
collection_1 = chroma_database.get_or_create_collection(name='nif_training_deck')

# =============================================================================
#### Full training deck
# =============================================================================
'''
Run time: 1h 34m
'''
doc_name = 'NIF Training Deck v4.pdf'

utils.timerstart('NIF Training Deck')
page_images, page_summaries = utils.embed_pdf_multimodal(
    DOC=os.path.join(utils.DOCUMENT_FOLDER, doc_name)
    ,COLLECTION=collection_1              # ChromaDB collection to write to
    ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
)
utils.save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, 'NIF Training Deck v4')
utils.timerstop()

'''
# Delete collections
chroma_database.delete_collection(name='rx_wip_setup_process')

# Clear the whole vectorstore
utils.clear_vectorstore(utils.VECTORSTORE_FOLDER)
'''

#%% QUICK REFERENCE DOCS
# *****************************************************************************
'''
Expanding the NIF Training Deck vectorstore by adding the other documents from 
the quick reference list.

NIF Training deck will remain in its own collection. The other documents will
be together in a second collection.

UPDATE: simplifying this to put all docs in a single collection.

UPDATE 2: added file modification date to metadata in embed_pdf_multimodal().
    Recreating vectorstore.
'''
# =============================================================================
#### Define folder for this vectorstore
# =============================================================================
# vectorstore_folder = os.path.join(utils.VECTORSTORE_FOLDER, 'quick_reference_docs')
# vectorstore_folder = os.path.join(utils.VECTORSTORE_FOLDER, 'quick_reference_docs_single_collection')
vectorstore_folder = os.path.join(utils.VECTORSTORE_FOLDER, 'quick_reference_docs_single_collection_fmoddate')

chroma_database = utils.get_or_create_vectorstore(vectorstore_folder)
# collection_1 = chroma_database.get_or_create_collection(name='nif_training_deck')
# collection_2 = chroma_database.get_or_create_collection(name='other_quick_ref')

collection_1 = chroma_database.get_or_create_collection(name='all_docs')

# =============================================================================
#### Full training deck
# =============================================================================
'''
Going in collection 1.

Run time: 1h 34m
'''
doc_name = 'NIF Training Deck v4.pdf'
doc_label, doc_ext = doc_name.split('.')

utils.timerstart(doc_name)
page_images, page_summaries = utils.embed_pdf_multimodal(
    DOC=os.path.join(utils.DOCUMENT_FOLDER, doc_name)
    ,COLLECTION=collection_1              # ChromaDB collection to write to
    ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
)
utils.save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, doc_label)
utils.timerstop()

# =============================================================================
#### NIF Initiator Checklist
# =============================================================================
'''
UPDATE: going in collection 1.
'''
doc_name = 'NIF Initiator Check List.pdf'
doc_label, doc_ext = doc_name.split('.')

utils.timerstart(doc_name)
page_images, page_summaries = utils.embed_pdf_multimodal(
    DOC=os.path.join(utils.DOCUMENT_FOLDER, doc_name)
    ,COLLECTION=collection_1              # ChromaDB collection to write to
    ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
)
utils.save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, doc_label)
utils.timerstop()

# =============================================================================
#### BOM Training Material
# =============================================================================
'''
UPDATE: going in collection 1.
'''
doc_name = 'BOM Training Material.pdf'
doc_label, doc_ext = doc_name.split('.')

utils.timerstart(doc_name)
page_images, page_summaries = utils.embed_pdf_multimodal(
    DOC=os.path.join(utils.DOCUMENT_FOLDER, doc_name)
    ,COLLECTION=collection_1              # ChromaDB collection to write to
    ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
)
utils.save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, doc_label)
utils.timerstop()

# =============================================================================
#### RX Setup Types
# =============================================================================
'''
UPDATE: going in collection 1.
'''
doc_name = 'RX Setup Types March 2023.pdf'
doc_label, doc_ext = doc_name.split('.')

utils.timerstart(doc_name)
page_images, page_summaries = utils.embed_pdf_multimodal(
    DOC=os.path.join(utils.DOCUMENT_FOLDER, doc_name)
    ,COLLECTION=collection_1              # ChromaDB collection to write to
    ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
)
utils.save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, doc_label)
utils.timerstop()

# =============================================================================
#### RX WIP Quick Reference
# =============================================================================
'''
UPDATE: going in collection 1.
'''
# doc_name = 'RX WIP Set-up Process Quick Reference Guide.pdf'
# doc_label, doc_ext = doc_name.split('.')

# utils.timerstart(doc_name)
# page_images, page_summaries = utils.embed_pdf_multimodal(
#     DOC=os.path.join(utils.DOCUMENT_FOLDER, doc_name)
#     ,COLLECTION=collection_1              # ChromaDB collection to write to
#     ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
# )
# utils.save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, doc_label)
# utils.timerstop()

#%% EACH DOCUMENT IS A COLLECTION
# *****************************************************************************
'''
Idea: create multiple collections. If you want to ensure you get results from
a variety of documents, put those documents in separate collections and submit
your query to all collections.

Want to handle PDFs and slides with full multimodal support.
'''
# =============================================================================
#### Define folder for this vectorstore
# =============================================================================
# vectorstore_folder = os.path.join(utils.VECTORSTORE_FOLDER, 'one_collection_per_doc')
# chroma_database = utils.get_or_create_vectorstore(vectorstore_folder)

# =============================================================================
#### Full training deck
# =============================================================================
'''
Going in collection 1.

Run time: 1h 34m
'''
# collection_1 = chroma_database.get_or_create_collection(name='nif_training_deck')

# utils.timerstart('NIF Training Deck')
# page_images, page_summaries = utils.embed_pdf_multimodal(
#     DOC=os.path.join(utils.DOCUMENT_FOLDER ,'NIF Training Deck v4.pdf')
#     ,COLLECTION=collection_1              # ChromaDB collection to write to
#     ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
# )
# utils.save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, 'NIF Training Deck v4')
# utils.timerstop()

# =============================================================================
#### Product Setup Type Guide
# =============================================================================
'''
Going in collection 2
'''
# collection_2 = chroma_database.get_or_create_collection(name='setup_type_guide')

# page_images, page_summaries = utils.embed_pdf_multimodal(
#     DOC=os.path.join(utils.DOCUMENT_FOLDER ,'Setup Type Guide.pdf')
#     ,COLLECTION=collection_2              # ChromaDB collection to write to
#     ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
# )
# utils.save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, 'Setup Type Guide')

# =============================================================================
#### CASE NIF Training Deck
# =============================================================================
'''
Going in collection 3
'''
# collection_3 = chroma_database.get_or_create_collection(name='data_ops_case')
#
# page_images, page_summaries = utils.embed_pdf_multimodal(
#     DOC=os.path.join(utils.DOCUMENT_FOLDER, 'Data-Ops-NIF-Create-a-CASE-Training-Deck---11.24.pdf')
#     ,COLLECTION=collection_3              # ChromaDB collection to write to
#     ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
# )
# utils.save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, 'Data-Ops-NIF-Create-a-CASE-Training-Deck')

# =============================================================================
#### RX Guide
# =============================================================================
'''
Going in collection 4
'''
# collection_4 = chroma_database.get_or_create_collection(name='rx_guide')
#
# page_images, page_summaries = utils.embed_pdf_multimodal(
#     DOC=os.path.join(utils.DOCUMENT_FOLDER, 'RX Guide on Creating an NIF for RX BAR and RX WIP 5.8.25.pdf')
#     ,COLLECTION=collection_4              # ChromaDB collection to write to
#     ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
# )
# utils.save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, 'RX Guide on Creating an NIF for RX BAR')

# =============================================================================
#### RX WIP Quick Reference
# =============================================================================
'''
Going in collection 5
'''
# collection_5 = chroma_database.get_or_create_collection(name='rx_wip_setup_process')

# utils.timerstart('RX WIP Setup Guide')
# page_images, page_summaries = utils.embed_pdf_multimodal(
#     DOC=os.path.join(utils.DOCUMENT_FOLDER ,'RX WIP Set-up Process Quick Reference Guide.pdf')
#     ,COLLECTION=collection_5              # ChromaDB collection to write to
#     ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
# )
# utils.save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, 'RX WIP Set-up Process Quick Reference Guide')
# utils.timerstop()

#%% Testing
# *****************************************************************************
if __name__ == '__main__':
    # test_query = 'What does subtype mean?'
    # test_query = 'What does product type mean?'
    # test_query = 'What does brand name mean?'
    # test_query = 'How do I know what the brand is?'
    # test_query = 'What is a planning variant?'
    # test_query = 'How do I select the correct product type and subtype?'
    test_query = 'Find documents on club products in Canada.'
    test_query = 'What is the winshuttle form?'
    test_query = 'What are the RX Setup Types?'
    
    # test_query = 'What are the RX WIP setup steps?'
    
    # Testing base retriever
    test_retrieval = utils.query_vectorstore(
        FOLDER_PATH=os.path.join(utils.VECTORSTORE_FOLDER, 'quick_reference_docs_single_collection_fmoddate')
        ,QUERY=test_query
        ,N_RESULTS_PER_COLLECTION=3
    )
    print(test_retrieval)
    
    num_collections_used = len(test_retrieval['documents'])
    
    document_1 = test_retrieval['documents'][0][0]   # First index selects collection. Second index selects document from that collection.
    test_retrieval['metadatas'][0][0]['document_name']
    test_retrieval['metadatas'][0][0]['page_number']
    modified_date = test_retrieval['metadatas'][0][0]['modified_date']
    dt.strptime(modified_date, "%Y%m%d").date()
    test_retrieval['distances'][0]
    
    image_file_without_path = os.path.basename(document_1)
    path, image_file_without_path = os.path.split(document_1)
    image_file_without_path = Path(document_1).name
    os.path.join(utils.IMAGE_FOLDER, image_file_without_path)
    
    def get_filename(path):
        # Replace backslashes with forward slashes for consistency
        path = path.replace('\\', '/')
        # Split on forward slash and get the last element
        return path.split('/')[-1]

    image_file_without_path = get_filename(document_1)

    # =============================================================================
    #### Testing image query function using all retrieved docs
    # =============================================================================
    retrieved_page_images = []      # Initialize
    retrieved_page_links = []       # Initialize
    for i, CLCT in enumerate(test_retrieval['documents']):          # Collection i
        for j, DOC in enumerate(test_retrieval['documents'][i]):    # Document j
            # Get link to page image
            ret_image = test_retrieval['documents'][i][j]
            image_file_without_path = os.path.basename(ret_image)
            image_file_new_path = os.path.join(utils.IMAGE_FOLDER, image_file_without_path)
            retrieved_page_images.append(image_file_new_path)
    
            # Get link to page in PDF viewer
            doc_name = test_retrieval['metadatas'][i][j]['document_name']
            page_num = test_retrieval['metadatas'][i][j]['page_number']
            encoded_doc_name = urllib.parse.quote(doc_name)
            link_to_page = os.path.join(utils.DOCUMENT_FOLDER, f"{encoded_doc_name}#page={page_num}")
            retrieved_page_links.append(link_to_page)
    
    # Call image query function to generate answer based on page images
    image_query_prompt = "You will be given a set of images of pages from documents. The pages may contain text, tables, graphs, and images. Use them to answer the user's question."
    
    answer_from_images = utils.query_multiple_images_bedrock(
        retrieved_page_images
        ,image_query_prompt
        ,test_query
        ,MODEL_ID = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    )
