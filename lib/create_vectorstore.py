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
import pandas as pd
import pdf2image
import urllib.parse
import botocore
import time
import json
import boto3
import chromadb.utils.embedding_functions as chembed
import mimetypes
import base64

def timerstart(label: str) -> float:
    start = time.time()
    print(f"<timerstart> {label} started.")
    return start

def timerstop(start: float, label: str) -> None:
    elapsed_seconds = time.time() - start
    print(f"<timerstop> {label} completed in {elapsed_seconds / 60:.2f} minutes.")

def _get_openai_client():
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. "
            "Set OPENAI_API_KEY in .env when using VECTORSTORE_LLM_PROVIDER=openai."
        )
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)

def make_openai_embedding_function():
    embed_model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large")
    embed_dims_raw = os.getenv("OPENAI_EMBED_DIMENSIONS", "").strip()
    embed_dims = int(embed_dims_raw) if embed_dims_raw else None
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()

    return chembed.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name=embed_model,
        api_base=base_url or None,
        dimensions=embed_dims,
    )

def query_multiple_images_openai(
        IMAGE_LIST: list[str]
        ,SYSTEM_PROMPT: str
        ,USER_QUESTION: str
        ,MODEL_ID: str | None = None
    ):
    vision_model = MODEL_ID or os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
    client = _get_openai_client()

    image_content = []
    for image in IMAGE_LIST:
        if utils.looks_like_base64(image):
            image_b64 = image
        else:
            image_b64 = utils.encode_image(image)
        image_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
            }
        )

    messages = [
        {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
        {"role": "user", "content": [{"type": "text", "text": USER_QUESTION}] + image_content},
    ]
    response = client.chat.completions.create(
        model=vision_model,
        messages=messages,
        max_tokens=1024,
    )
    return (response.choices[0].message.content or "").strip()

def assert_bedrock_connectivity(
        REGION_NAME:str=None
    ):
    funcname = inspect.currentframe().f_code.co_name

    region_name = REGION_NAME or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    print(f"<{funcname}> Starting AWS/Bedrock preflight checks for region '{region_name}'...")

    # -------------------------------------------------------------------------
    # 1) Verify AWS credentials are present and valid.
    # -------------------------------------------------------------------------
    try:
        sts_client = boto3.client("sts", region_name=region_name)
        caller = sts_client.get_caller_identity()
        print(
            f"<{funcname}> STS OK. Account={caller.get('Account')}, "
            f"Arn={caller.get('Arn')}."
        )
    except botocore.exceptions.EndpointConnectionError as err:
        raise RuntimeError(
            f"<{funcname}> Could not reach AWS STS endpoint in region '{region_name}'.\n"
            "This is a network/DNS/VPN/proxy issue, not a Claude key format issue.\n"
            "Verify outbound access to sts.amazonaws.com and bedrock-runtime endpoints.\n"
            f"Original error: {err}"
        ) from err
    except Exception as err:
        raise RuntimeError(
            f"<{funcname}> AWS credential check failed.\n"
            f"Set valid AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY "
            f"(and AWS_SESSION_TOKEN if temporary creds).\n"
            f"Original error: {err}"
        ) from err

    bedrock_client = boto3.client("bedrock-runtime", region_name=region_name)

    # -------------------------------------------------------------------------
    # 2) Verify Bedrock Titan embedding call succeeds (used for vector embeddings).
    # -------------------------------------------------------------------------
    try:
        titan_request = {
            "inputText": "bedrock preflight check",
            "dimensions": 256,
            "normalize": True,
        }
        titan_response = bedrock_client.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=json.dumps(titan_request),
            accept="application/json",
            contentType="application/json",
        )
        titan_body = json.loads(titan_response["body"].read())
        embedding = titan_body.get("embedding")
        if not embedding:
            raise RuntimeError("Titan response did not include an embedding.")
        print(f"<{funcname}> Titan embedding OK. Returned {len(embedding)} dimensions.")
    except botocore.exceptions.EndpointConnectionError as err:
        raise RuntimeError(
            f"<{funcname}> Could not reach Bedrock endpoint in region '{region_name}'.\n"
            "Check DNS/network/VPN/proxy and verify Bedrock endpoint access.\n"
            f"Original error: {err}"
        ) from err
    except Exception as err:
        raise RuntimeError(
            f"<{funcname}> Bedrock Titan embedding preflight failed.\n"
            "Confirm your IAM permissions include bedrock:InvokeModel for "
            "'amazon.titan-embed-text-v2:0' and that this model is enabled in the region.\n"
            f"Original error: {err}"
        ) from err

    # -------------------------------------------------------------------------
    # 3) Verify Bedrock Claude call succeeds (used for page summarization).
    # -------------------------------------------------------------------------
    try:
        claude_request = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 8,
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Reply with OK"}]}],
        }
        claude_response = bedrock_client.invoke_model(
            modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            body=json.dumps(claude_request),
            accept="application/json",
            contentType="application/json",
        )
        claude_body = json.loads(claude_response["body"].read())
        content = claude_body.get("content", [])
        if not content:
            raise RuntimeError("Claude response did not include content.")
        print(f"<{funcname}> Claude summarization OK.")
    except botocore.exceptions.EndpointConnectionError as err:
        raise RuntimeError(
            f"<{funcname}> Could not reach Bedrock endpoint in region '{region_name}'.\n"
            "Check DNS/network/VPN/proxy and verify Bedrock endpoint access.\n"
            f"Original error: {err}"
        ) from err
    except Exception as err:
        raise RuntimeError(
            f"<{funcname}> Bedrock Claude preflight failed.\n"
            "Confirm your IAM permissions include bedrock:InvokeModel for "
            "'us.anthropic.claude-3-5-sonnet-20241022-v2:0' and that this model is enabled in the region.\n"
            f"Original error: {err}"
        ) from err

    print(f"<{funcname}> All preflight checks passed.")

def assert_openai_connectivity():
    funcname = inspect.currentframe().f_code.co_name

    embed_model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large")
    vision_model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")

    print(
        f"<{funcname}> Starting OpenAI preflight checks "
        f"(embed='{embed_model}', vision='{vision_model}')..."
    )
    try:
        client = _get_openai_client()
    except Exception as err:
        raise RuntimeError(f"<{funcname}> OpenAI client initialization failed: {err}") from err

    # -------------------------------------------------------------------------
    # 1) Verify embeddings endpoint (used for vector embeddings).
    # -------------------------------------------------------------------------
    try:
        emb = client.embeddings.create(model=embed_model, input=["openai preflight check"])
        first_embedding = emb.data[0].embedding if emb.data else None
        if not first_embedding:
            raise RuntimeError("Embedding response did not include vectors.")
        print(f"<{funcname}> OpenAI embeddings OK. Returned {len(first_embedding)} dimensions.")
    except Exception as err:
        if err.__class__.__name__ == "APIConnectionError":
            raise RuntimeError(
                f"<{funcname}> Could not reach OpenAI endpoint.\n"
                "This is usually a network/DNS/proxy issue.\n"
                "Check outbound access to api.openai.com (or OPENAI_BASE_URL if set).\n"
                f"Original error: {err}"
            ) from err
        raise RuntimeError(
            f"<{funcname}> OpenAI embedding preflight failed.\n"
            "Check OPENAI_API_KEY, OPENAI_EMBED_MODEL, account permissions, and outbound access to api.openai.com.\n"
            f"Original error: {err}"
        ) from err

    # -------------------------------------------------------------------------
    # 2) Verify vision-capable chat endpoint (used for page summarization).
    # -------------------------------------------------------------------------
    try:
        vision_test_image = os.getenv(
            "OPENAI_VISION_TEST_IMAGE",
            os.path.join(utils.IMAGE_FOLDER, "NIF Training Deck v40001-001.jpg"),
        ).strip()

        # Prefer a real local image (mirrors actual runtime behavior).
        if os.path.isfile(vision_test_image):
            mime, _ = mimetypes.guess_type(vision_test_image)
            mime = mime or "image/jpeg"
            with open(vision_test_image, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
            image_url = f"data:{mime};base64,{image_b64}"
        else:
            # Fallback if the configured image is missing.
            tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAgMBgJPfH2YAAAAASUVORK5CYII="
            image_url = f"data:image/png;base64,{tiny_png}"

        resp = client.chat.completions.create(
            model=vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Reply with OK"},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            max_tokens=8,
        )
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            raise RuntimeError("Vision chat response was empty.")
        print(f"<{funcname}> OpenAI vision chat OK.")
    except Exception as err:
        if "unsupported image" in str(err).lower():
            raise RuntimeError(
                f"<{funcname}> OpenAI vision preflight failed with unsupported image.\n"
                "Set OPENAI_VISION_TEST_IMAGE to a valid local JPG/PNG path that your endpoint accepts,\n"
                "or check if your OPENAI_BASE_URL gateway supports image_url data URLs.\n"
                f"Current OPENAI_VISION_TEST_IMAGE={vision_test_image!r}\n"
                f"Original error: {err}"
            ) from err
        if err.__class__.__name__ == "APIConnectionError":
            raise RuntimeError(
                f"<{funcname}> Could not reach OpenAI endpoint.\n"
                "This is usually a network/DNS/proxy issue.\n"
                "Check outbound access to api.openai.com (or OPENAI_BASE_URL if set).\n"
                f"Original error: {err}"
            ) from err
        raise RuntimeError(
            f"<{funcname}> OpenAI vision preflight failed.\n"
            "Check OPENAI_VISION_MODEL and ensure your account can use a vision-capable model.\n"
            f"Original error: {err}"
        ) from err

    print(f"<{funcname}> All preflight checks passed.")

def embed_pdf_multimodal(
        DOC:str                     # Full path to file
        ,COLLECTION:object          # ChromaDB collection to write to
        ,IMAGE_FOLDER:str           # Folder to store page images
        ,SUMMARY_FN:object=utils.query_multiple_images_bedrock
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
                page_summary = SUMMARY_FN([path_to_page_image], page_summary_prompt, page_summary_question)
                print(f"<{funcname}> Success!")
                retry = False   # Exit retry loop
            except botocore.exceptions.ClientError as error:
                if error.response['Error']['Code'] == 'ThrottlingException':
                    print(f"<{funcname}> LLM throttling exception.")
                    time.sleep(SLEEP_IF_NEEDED)
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
VECTORSTORE_LLM_PROVIDER = os.getenv("VECTORSTORE_LLM_PROVIDER", "bedrock").strip().lower()

if VECTORSTORE_LLM_PROVIDER not in ("bedrock", "openai"):
    raise RuntimeError(
        "VECTORSTORE_LLM_PROVIDER must be one of: 'bedrock', 'openai'. "
        f"Got: {VECTORSTORE_LLM_PROVIDER!r}"
    )

# Fail fast on auth/network/model access before starting long PDF processing.
if VECTORSTORE_LLM_PROVIDER == "bedrock":
    assert_bedrock_connectivity()
    summary_fn = utils.query_multiple_images_bedrock
    embedding_model = utils.BedrockTitanEmbeddingFunction()
else:
    assert_openai_connectivity()
    summary_fn = query_multiple_images_openai
    embedding_model = make_openai_embedding_function()

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

training_deck_timer = timerstart('NIF Training Deck')
page_images, page_summaries = embed_pdf_multimodal(
    DOC=os.path.join(utils.DOCUMENT_FOLDER ,'NIF Training Deck v4.pdf')
    ,COLLECTION=collection_1              # ChromaDB collection to write to
    ,IMAGE_FOLDER=utils.IMAGE_FOLDER      # Folder to store page images
    ,SUMMARY_FN=summary_fn
    ,EMBEDDING_MODEL=embedding_model
)
save_page_summaries(page_images, page_summaries, utils.IMAGE_FOLDER, 'NIF Training Deck v4')
timerstop(training_deck_timer, 'NIF Training Deck')

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
    ,SUMMARY_FN=summary_fn
    ,EMBEDDING_MODEL=embedding_model
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
