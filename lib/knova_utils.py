#%% ABOUT
# *****************************************************************************
'''
This is a collection of utility functions for interacting with LLMs and vector
stores.
'''
#%% PACKAGES
# *****************************************************************************
import os
import inspect
import re
import pickle
import base64
import chromadb
import chromadb.utils.embedding_functions as chembed
import langroid.language_models as lrlm
import sqlite3
import boto3
import json
from typing import Any, Dict, List, Optional

from dotenv import find_dotenv, load_dotenv, dotenv_values
dotenv_loaded = load_dotenv()
dotenv_dict = dotenv_values()
if dotenv_loaded:
	print(f"> Environment file loaded with {len(dotenv_dict)} variables.")
else:
	print("> Environment file is either empty or not found!")

#%% PATHS & CONSTANTS
# *****************************************************************************
try:
	CURRENT_FOLDER = os.path.dirname(os.path.realpath(__file__)) 	# Doesn't rely on working directory. Will throw NameError if run as a single line. Works only when running a cell or the whole file.
	print(f"> CURRENT_FOLDER set to location of this file: {CURRENT_FOLDER}")
except NameError:
	CURRENT_FOLDER = os.getcwd() 		 			# Relies on working directory being set to this program.
	print(f"> CURRENT_FOLDER set to current working directory: {CURRENT_FOLDER}")

PARENT_FOLDER = os.path.dirname(CURRENT_FOLDER)
GRANDPARENT_FOLDER = os.path.dirname(PARENT_FOLDER)

DOCUMENT_FOLDER = os.path.join(PARENT_FOLDER, 'assets', 'raw_docs')
IMAGE_FOLDER = os.path.join(PARENT_FOLDER, 'assets', 'doc_images_and_summaries')
VECTORSTORE_FOLDER = os.path.join(PARENT_FOLDER, 'vectorstore')
DATABASE_FOLDER = os.path.join(PARENT_FOLDER, 'database')
CONTROL_FOLDER = os.path.join(PARENT_FOLDER, 'control_docs')

# Lightweight in-process caches to avoid repeated disk/client setup for each query.
_VECTORSTORE_CLIENT_CACHE: Dict[str, chromadb.PersistentClient] = {}
_VECTORSTORE_COLLECTIONS_CACHE: Dict[str, List[str]] = {}
_EMBEDDING_FN_CACHE: Dict[str, Any] = {}

#%% CONFIGURE LLMS
# *****************************************************************************
# # Embedding model
# # Configured for Chroma
# openai_embedding_model_chroma = chembed.OpenAIEmbeddingFunction(
#     api_base=dotenv_dict.get('AZURE_API_BASE_POC', '<ENV_VAR_NOT_FOUND>')
#     ,api_key=dotenv_dict.get('AZURE_API_KEY_POC', '<ENV_VAR_NOT_FOUND>')
#     ,api_type='azure'
#     ,api_version='2024-10-21'
#     ,model_name='text-embedding-ada-002'
#     ,deployment_id='text-embedding-ada-002'
# )

# # GPT-4o
# # Configured for Langroid
# azure_llm_gpt4o = lrlm.AzureConfig(
#     ## Required
#     api_base=dotenv_dict.get('AZURE_API_BASE_POC', '<ENV_VAR_NOT_FOUND>')
#     ,api_key=dotenv_dict.get('AZURE_API_KEY_POC', '<ENV_VAR_NOT_FOUND>')
#     ,api_version='2024-12-01-preview'
#     ,deployment_name='gpt-4o-DCAI-KellanovaPOC'
#     ,model_name='gpt-4o'
#     ,stream=False

#     ## Optional
#     ,temperature=0
#     ,max_output_tokens=4096    # To get around Agent error complaining about max tokens
# )

# AWS Claude 4
'''
If running locally, these rely on the following environment variables set in .env:
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    AWS_BEARER_TOKEN_BEDROCK
    AWS_REGION
    
If running on EC2 Sandbox, these are not required.
UPDATE: Langroid requires these environment variables even on EC2.
'''
aws_llm_claude4 = lrlm.OpenAIGPTConfig(
    chat_model="litellm/bedrock/us.anthropic.claude-sonnet-4-20250514-v1:0"
    ,chat_context_length=1e6
    ,max_output_tokens=4096
    ,temperature=0.0
)

# AWS Claude 3.5 Haiku
aws_llm_claude35 = lrlm.OpenAIGPTConfig(
    chat_model="litellm/bedrock/us.anthropic.claude-3-5-haiku-20241022-v1:0"
    ,chat_context_length=1e6
    ,max_output_tokens=4096
    ,temperature=0.0
)

# AWS Claude 3.5 Sonnet
aws_llm_claude35_sonnet = lrlm.OpenAIGPTConfig(
    chat_model="litellm/bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    ,chat_context_length=1e6
    ,max_output_tokens=4096
    ,temperature=0.0
)

# AWS GPT
aws_llm_gptoss = lrlm.OpenAIGPTConfig(
    chat_model="litellm/bedrock/openai.gpt-oss-120b-1:0"
    ,chat_context_length=1e6
    ,max_output_tokens=4096
    ,temperature=0.0
)

# AWS Titan Embedding model
# Example usage
    # import chromadb

    # # Initialize the embedding function
    # embedding_fn = BedrockTitanEmbeddingFunction(
    #     region_name="us-east-1", dimensions=1024, normalize=True
    # )

    # # Create a Chroma client
    # client = chromadb.EphemeralClient()

    # # Create a collection with the custom embedding function
    # collection = client.create_collection(
    #     name="bedrock_documents", embedding_function=embedding_fn
    # )

    # # Add documents to the collection
    # documents = [
    #     "The Amazon Titan embedding model provides efficient text embeddings.",
    #     "AWS Bedrock makes it easy to use foundation models.",
    #     "ChromaDB is a vector database for storing embeddings.",
    # ]

    # ids = ["doc1", "doc2", "doc3"]

    # collection.add(ids=ids, documents=documents)

    # print("Documents added successfully!")

    # # Query the collection
    # query_text = "What does Bedrock offer?"
    # results = collection.query(query_texts=[query_text], n_results=2)

    # print(f"\nQuery: {query_text}")
    # print(f"Top results:")
    # for doc, distance in zip(results["documents"][0], results["distances"][0]):
    #     print(f"  - {doc} (distance: {distance:.4f})")
class BedrockTitanEmbeddingFunction(chromadb.EmbeddingFunction):
    """
    Embedding function that uses AWS Bedrock Titan Text Embeddings V2 model.
    """

    def __init__(
        self,
        region_name: str = "us-east-1",
        model_id: str = "amazon.titan-embed-text-v2:0",
        dimensions: int = 1024,
        normalize: bool = True,
    ):
        """
        Initialize the Bedrock Titan embedding function.

        Args:
            region_name: AWS region (default: us-east-1)
            model_id: Bedrock model ID (default: amazon.titan-embed-text-v2:0)
            dimensions: Output embedding dimensions (256, 512, or 1024)
            normalize: Whether to normalize embeddings (default: True)
        """
        self.region_name = region_name
        self.model_id = model_id
        self.dimensions = dimensions
        self.normalize = normalize
        self.bedrock_client = boto3.client(
            service_name="bedrock-runtime", region_name=region_name
        )

    def __call__(self, input: chromadb.Documents) -> chromadb.Embeddings:
        """
        Generate embeddings for the input documents using Bedrock Titan.

        Args:
            input: List of text documents to embed

        Returns:
            List of embeddings as lists of floats
        """
        embeddings = []

        for text in input:
            # Prepare the request body for Bedrock
            request_body = {
                "inputText": text,
                "dimensions": self.dimensions,
                "normalize": self.normalize,
            }

            # Invoke the model
            try:
                response = self.bedrock_client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body),
                    accept="application/json",
                    contentType="application/json",
                )

                # Parse the response
                response_body = json.loads(response["body"].read())
                embedding = response_body.get("embedding")

                if embedding is None:
                    raise ValueError(
                        f"No embedding returned for text: {text[:50]}..."
                    )

                embeddings.append(embedding)

            except Exception as e:
                print(f"Error generating embedding for text: {text[:50]}...")
                raise e

        return embeddings
    
#%% FUNCTIONS
# *****************************************************************************
# =============================================================================
#### Helper functions
# =============================================================================
def save_to_pickle(OBJ, FILENAME):
    with open(FILENAME, 'wb') as output:
        pickle.dump(OBJ, output, pickle.HIGHEST_PROTOCOL)
    return None

def dirnamext(FULL_PATH_TO_FILE:str) -> tuple([str, str, str]):
    directory = os.path.dirname(FULL_PATH_TO_FILE)
    file_name_with_ext = os.path.basename(FULL_PATH_TO_FILE)
    name, extension = file_name_with_ext.rsplit('.', 1) 	# Make one split starting from rightmost period. In case there are periods in filename.
    return directory, name, extension

# Encode an image as a base64 string
def encode_image(IMAGE_FILE:str):   # Provide full path to image file. PNG or JPG.
    with open(IMAGE_FILE, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

# A helper function for checking if a string is a base64 image
def looks_like_base64(STRING):
    return re.match("^[A-Za-z0-9+/]+[=]{0,2}$", STRING) is not None

def get_vectorstore_provider() -> str:
    provider = os.getenv("VECTORSTORE_LLM_PROVIDER", "bedrock").strip().lower()
    if provider not in {"bedrock", "openai"}:
        print(
            f"<get_vectorstore_provider> Invalid VECTORSTORE_LLM_PROVIDER={provider!r}. "
            "Using 'bedrock'."
        )
        return "bedrock"
    return provider

def get_openai_embedding_function():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. "
            "Set OPENAI_API_KEY when VECTORSTORE_LLM_PROVIDER=openai."
        )

    embed_model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large").strip()
    embed_dims_raw = os.getenv("OPENAI_EMBED_DIMENSIONS", "").strip()
    embed_dims = int(embed_dims_raw) if embed_dims_raw else None
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()

    return chembed.OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name=embed_model,
        api_base=base_url or None,
        dimensions=embed_dims,
    )


def _normalize_vectorstore_path(folder_path: str) -> str:
    return os.path.abspath(str(folder_path))


def get_cached_vectorstore(FOLDER_PATH: str, refresh: bool = False):
    """
    Return a cached Chroma PersistentClient for the given folder.
    """
    normalized_path = _normalize_vectorstore_path(FOLDER_PATH)
    if refresh or normalized_path not in _VECTORSTORE_CLIENT_CACHE:
        _VECTORSTORE_CLIENT_CACHE[normalized_path] = chromadb.PersistentClient(path=normalized_path)
        # Ensure collection cache refresh after client refresh.
        _VECTORSTORE_COLLECTIONS_CACHE.pop(normalized_path, None)
    return _VECTORSTORE_CLIENT_CACHE[normalized_path]


def get_cached_collection_names(FOLDER_PATH: str, refresh: bool = False) -> List[str]:
    """
    Return cached vectorstore collection names for a folder.
    """
    normalized_path = _normalize_vectorstore_path(FOLDER_PATH)
    if refresh or normalized_path not in _VECTORSTORE_COLLECTIONS_CACHE:
        chroma_database = get_cached_vectorstore(normalized_path, refresh=refresh)
        _VECTORSTORE_COLLECTIONS_CACHE[normalized_path] = [
            item.name for item in chroma_database.list_collections()
        ]
    return list(_VECTORSTORE_COLLECTIONS_CACHE.get(normalized_path, []))


def get_cached_retrieval_embedding_function(provider: Optional[str] = None):
    """
    Return a cached embedding function aligned to VECTORSTORE_LLM_PROVIDER.
    """
    provider_name = (provider or get_vectorstore_provider()).strip().lower()
    if provider_name == "openai":
        signature = "|".join(
            [
                "openai",
                os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large").strip(),
                os.getenv("OPENAI_EMBED_DIMENSIONS", "").strip(),
                os.getenv("OPENAI_BASE_URL", "").strip(),
            ]
        )
        if signature not in _EMBEDDING_FN_CACHE:
            _EMBEDDING_FN_CACHE[signature] = get_openai_embedding_function()
        return _EMBEDDING_FN_CACHE[signature]

    region_name = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1").strip()
    signature = f"bedrock|{region_name}|amazon.titan-embed-text-v2:0|1024|true"
    if signature not in _EMBEDDING_FN_CACHE:
        _EMBEDDING_FN_CACHE[signature] = BedrockTitanEmbeddingFunction(region_name=region_name)
    return _EMBEDDING_FN_CACHE[signature]

# To run a query on a SQLite database
def run_query(
        DATABASE:str    # Full path to a .db file
        ,QUERY:str      # The query to run (SQLite syntax)
    ):
    db = sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True)  # mode=ro means READ ONLY
    c = db.cursor()
    try:
        c.execute(QUERY)
        return c.fetchall()     # This is returned to the LLM! The LLM uses it to formulate a response to the user.
    except sqlite3.OperationalError as err:     # If there's an error, tell the LLM about it.
        return f"The following error occured: {str(err)}"

# Download a file from an S3 bucket to the local machine
# Example usage:
    # download_from_s3(
    #     SOURCE_BUCKET='knva-sbx-prj1-nifty-s3'
    #     ,SOURCE_PATH='nifty_input_data/nif_metadata/'
    #     ,SOURCE_FILE='NIF Repository.xlsx'
    #     ,DESTINATION_PATH='/home/ec2-user/knva-nifty/database'           # Will create directory if needed
    #     ,DESTINATION_FILE=None      # If None, will use SOURCE_FILE
    # )
def download_from_s3(
        SOURCE_BUCKET:str               # e.g. 'knva-sbx-prj1-nifty-s3'
        ,SOURCE_PATH:str                # With or without trailing slash. e.g. 'nifty_input_data/nif_metadata/'
        ,SOURCE_FILE:str                # File name with extension, e.g. 'MATERIAL_PREFIX.xlsx'
        ,DESTINATION_PATH:str           # Will create directory if needed
        ,DESTINATION_FILE:str=None      # If None, will use SOURCE_FILE
    ):
    funcname = inspect.currentframe().f_code.co_name

    try:
        # Create S3 client (uses EC2 instance IAM role automatically)
        s3 = boto3.client("s3", region_name="us-east-1")
         
        # Define key
        # key = f"{SOURCE_PATH}/{SOURCE_FILE}"
        key = os.path.join(SOURCE_PATH, SOURCE_FILE)
         
        # Define destination
        os.makedirs(DESTINATION_PATH ,exist_ok=True)
        
        if not DESTINATION_FILE:
            local_filename = SOURCE_FILE
        else:
            local_filename = DESTINATION_FILE
            
        # local_filename_with_path = f"{DESTINATION_PATH}/{local_filename}"
        local_filename_with_path = os.path.join(DESTINATION_PATH, local_filename)
            
        # Download the file
        s3.download_file(SOURCE_BUCKET, key, local_filename_with_path)
        
        message = f"File {SOURCE_BUCKET}/{key} downloaded successfully to {local_filename_with_path}."
    
    except Exception as e:
        message = f"Exception: {e}"

    print(f"<{funcname}> {message}")
    
    return None

# =============================================================================
#### Vectorstore functions
# =============================================================================
# To load a project's vectorstore and print some basic information about it
# Run without assigning the result to simply check the vectorstore
def get_vectorstore(
        FOLDER_PATH:str   # Full path to folder containing chroma.sqlite file
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Get vectorstore
    chroma_database = get_cached_vectorstore(FOLDER_PATH)

    # Summarize
    collection_list = chroma_database.list_collections()
    print(f"<{funcname}> Loaded vectorstore in {FOLDER_PATH}.")
    print(f"<{funcname}> Vectorstore contains {len(collection_list)} collection(s).")

    for collection_i in collection_list:    # If there are multiple collections, loop through
        collection = chroma_database.get_collection(name=collection_i.name)
        print(f"<{funcname}>     Collection '{collection.name}' contains {collection.count()} items.")

    return chroma_database

# To clear out the project vectorstore by removing all collections.
#!!! This does not delete the ChromaDB files from disk!
# This is a known bug. See:
    # https://github.com/chroma-core/chroma/issues/1245
    # https://github.com/chroma-core/chroma/pull/1313
def clear_vectorstore(
        FOLDER_PATH:str   # Full path to folder containing chroma.sqlite file
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Get vectorstore
    chroma_database = get_vectorstore(FOLDER_PATH)

    # Do it
    collection_list = chroma_database.list_collections()
    if len(collection_list) == 0:
        print(f"<{funcname}> Project vectorstore is empty. Exiting.")
    else:
        for collection_i in collection_list:    # If there are multiple collections, loop through
            print(f"<{funcname}> Removing collection {collection_i.name} with {collection_i.count()} items.")
            chroma_database.delete_collection(collection_i.name)

    normalized_path = _normalize_vectorstore_path(FOLDER_PATH)
    _VECTORSTORE_COLLECTIONS_CACHE.pop(normalized_path, None)

    return None

# To query a vectorstore
# Note EMBEDDING_MODEL must be the same one used when building the vectorstore
def query_vectorstore(
        FOLDER_PATH:str             # Full path to folder containing chroma.sqlite file
        ,QUERY:str                  # Plain text query. Will be embedded with EMBEDDING_MODEL before submitting to vectorstore.
        ,N_RESULTS:int=3            # Number of relevant docs to return
        ,EMBEDDING_MODEL:object=None     # Embedding model to use. Must be the same one used to create the vectorstore.
        ,COLLECTION_NAMES:Optional[List[str]]=None
        ,USE_CACHE:bool=True
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Get project vectorstore
    normalized_path = _normalize_vectorstore_path(FOLDER_PATH)
    if USE_CACHE:
        chroma_database = get_cached_vectorstore(normalized_path)
        if COLLECTION_NAMES:
            collection_names = [str(name) for name in COLLECTION_NAMES if str(name).strip()]
        else:
            collection_names = get_cached_collection_names(normalized_path)
    else:
        chroma_database = chromadb.PersistentClient(path=normalized_path)
        if COLLECTION_NAMES:
            collection_names = [str(name) for name in COLLECTION_NAMES if str(name).strip()]
        else:
            collection_names = [item.name for item in chroma_database.list_collections()]

    # Check for empty vectorstore
    if len(collection_names) == 0:
        emsg = 'Project vectorstore is empty. Exiting.'
        print(f"<{funcname}> {emsg}")
        raise Exception(emsg)

    # Retrieve docs
    else:
        if EMBEDDING_MODEL is None:
            EMBEDDING_MODEL = get_cached_retrieval_embedding_function()

        # Embed text with explicit call to embedding model
        query_texts = [QUERY]
        embedded_query_texts = EMBEDDING_MODEL(query_texts)
        retrieved_docs_all_collections = None

        for i, collection_name in enumerate(collection_names):    # If there are multiple collections, loop through
            collection = chroma_database.get_collection(name=collection_name)

            # Retrieve docs
            retrieved_docs = collection.query(
                query_embeddings=embedded_query_texts
                ,n_results=N_RESULTS

                # # Optional: add filters on metadata and keywords found in document
                # ,where={"metadata_field": "is_equal_to_this"}
                # ,where_document={"$contains":"search_string"}   # Can also do: {"$not_contains": "search_string"}
            )
            print(f"<{funcname}> Collection {collection.name} returned {len(retrieved_docs['ids'][0])} documents:")
            print(f"    Documents IDs: {retrieved_docs['ids'][0]}")

            # Append results to aggregate dictionary
            # Note each element in retrieved_docs is a list. Extend each list with the results from the next collection.
            if retrieved_docs_all_collections is None:
                retrieved_docs_all_collections = {}
                for key, value in retrieved_docs.items():
                    if isinstance(value, list):
                        retrieved_docs_all_collections[key] = list(value)
                    else:
                        retrieved_docs_all_collections[key] = value
            else:
                for key, value in retrieved_docs.items():
                    if (
                        key in retrieved_docs_all_collections
                        and isinstance(retrieved_docs_all_collections[key], list)
                        and isinstance(value, list)
                    ):
                        retrieved_docs_all_collections[key] = retrieved_docs_all_collections[key] + value
                    elif key not in retrieved_docs_all_collections:
                        retrieved_docs_all_collections[key] = value

        if retrieved_docs_all_collections is None:
            return {
                "ids": [],
                "documents": [],
                "metadatas": [],
                "distances": [],
            }

        return retrieved_docs_all_collections


def flatten_vectorstore_results(retrieved_docs_all_collections: dict) -> List[Dict[str, Any]]:
    """
    Convert Chroma nested per-collection query results to one flat ranked list.
    """
    flat_hits: List[Dict[str, Any]] = []
    if not isinstance(retrieved_docs_all_collections, dict):
        return flat_hits

    docs_by_collection = retrieved_docs_all_collections.get("documents") or []
    metadata_by_collection = retrieved_docs_all_collections.get("metadatas") or []
    ids_by_collection = retrieved_docs_all_collections.get("ids") or []
    distances_by_collection = retrieved_docs_all_collections.get("distances") or []

    for collection_idx, docs_for_collection in enumerate(docs_by_collection):
        if not isinstance(docs_for_collection, list):
            continue

        metadata_for_collection = (
            metadata_by_collection[collection_idx]
            if collection_idx < len(metadata_by_collection)
            and isinstance(metadata_by_collection[collection_idx], list)
            else []
        )
        ids_for_collection = (
            ids_by_collection[collection_idx]
            if collection_idx < len(ids_by_collection)
            and isinstance(ids_by_collection[collection_idx], list)
            else []
        )
        distances_for_collection = (
            distances_by_collection[collection_idx]
            if collection_idx < len(distances_by_collection)
            and isinstance(distances_by_collection[collection_idx], list)
            else []
        )

        for rank_in_collection, doc_value in enumerate(docs_for_collection):
            metadata_value = (
                metadata_for_collection[rank_in_collection]
                if rank_in_collection < len(metadata_for_collection)
                else {}
            )
            if not isinstance(metadata_value, dict):
                metadata_value = {}

            id_value = (
                ids_for_collection[rank_in_collection]
                if rank_in_collection < len(ids_for_collection)
                else None
            )
            distance_raw = (
                distances_for_collection[rank_in_collection]
                if rank_in_collection < len(distances_for_collection)
                else None
            )
            try:
                distance_value = float(distance_raw) if distance_raw is not None else None
            except (TypeError, ValueError):
                distance_value = None

            flat_hits.append(
                {
                    "collection_index": collection_idx,
                    "rank_in_collection": rank_in_collection,
                    "id": id_value,
                    "document": doc_value,
                    "metadata": metadata_value,
                    "distance": distance_value,
                }
            )
    return flat_hits


def select_vectorstore_hits(
    retrieved_docs_all_collections: dict,
    max_total_results: int = 4,
    max_distance: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Rank and filter retrieval hits to reduce noisy/duplicate context.
    """
    try:
        max_total_results = int(max_total_results)
    except Exception:
        max_total_results = 4
    max_total_results = max(1, max_total_results)

    try:
        max_distance = float(max_distance) if max_distance is not None else None
    except Exception:
        max_distance = None

    candidates = flatten_vectorstore_results(retrieved_docs_all_collections)

    if max_distance is not None:
        known_distance_candidates = [
            item for item in candidates if isinstance(item.get("distance"), (float, int))
        ]
        if known_distance_candidates:
            candidates = [
                item
                for item in known_distance_candidates
                if float(item["distance"]) <= max_distance
            ]
        else:
            candidates = [item for item in candidates if item.get("distance") is None]

    candidates.sort(
        key=lambda item: (
            item.get("distance") is None,
            float(item["distance"]) if item.get("distance") is not None else float("inf"),
            int(item.get("collection_index", 0)),
            int(item.get("rank_in_collection", 0)),
        )
    )

    selected: List[Dict[str, Any]] = []
    seen_keys = set()
    for item in candidates:
        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        dedupe_key = (
            str(metadata.get("document_name", "")).strip().lower(),
            str(metadata.get("page_number", "")).strip(),
            str(item.get("document", "")).strip(),
        )
        if dedupe_key in seen_keys:
            continue
        selected.append(item)
        seen_keys.add(dedupe_key)
        if len(selected) >= max_total_results:
            break

    return selected

# =============================================================================
#### LLM functions
# =============================================================================
# To invoke an LLM and pass it one or more images along with a question.
# Note: this does not use Langroid or Langchain. It uses the openai package to
# call AzureOpenAI directly so we can pass the base64 encoded images using
# GPT's native message format.
# def query_multiple_images_azureoai(
#         IMAGE_LIST:list[str]            # List of image strings. May be either full paths to image files or base64-encoded images.
#         ,SYSTEM_PROMPT:str              # System prompt
#         ,USER_QUESTION:str              # User question
#         ,DEPLOYMENT_NAME:str="gpt-4o-DCAI-KellanovaPOC"   # The name of the deployment to use (defined in Azure OpenAI console). Must be an LLM that can interpret images.
#     ):
#     # Create Azure client
#     # This requires environment variables AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and OPENAI_API_VERSION to be set. Check the .env file.
#     # Alternatively, you can pass azure_endpoint, api_key, and api_version as arguments to AzureOpenAI().
#     from openai import AzureOpenAI
#     azure_client = AzureOpenAI(
#         azure_endpoint=dotenv_dict.get('AZURE_API_BASE_POC', '<ENV_VAR_NOT_FOUND>')
#         ,api_key=dotenv_dict.get('AZURE_API_KEY_POC', '<ENV_VAR_NOT_FOUND>')
#         ,api_version='2024-12-01-preview'
#     )

#     # Prepare images
#     images_for_chatbot = []     # Initialize
#     for image in IMAGE_LIST:
#         if looks_like_base64(image):
#             image_b64 = image
#         else:
#             # Encode image as base64
#             image_b64 = encode_image(image)

#         # Append to list of dictionaries formatted for chatbot
#         images_for_chatbot.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}})

#     # Pass images to chat with prompt
#     messages_with_images = [
#         {"role":"system", "content":[{"type":"text", "text":SYSTEM_PROMPT}]}
#         ,{"role":"user", "content":[{"type":"text", "text":USER_QUESTION}] + images_for_chatbot}
#     ]
#     response = azure_client.chat.completions.create(
#         model=DEPLOYMENT_NAME
#         ,messages=messages_with_images
#     )
#     return response.choices[0].message.content

def query_multiple_images_bedrock(
        IMAGE_LIST: list[str]       # List of image strings. May be either full paths to image files or base64-encoded images.
        ,SYSTEM_PROMPT: str         # System prompt
        ,USER_QUESTION: str         # User question
        ,MODEL_ID: str = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"  # AWS Bedrock model ID for Claude 3.5 Sonnet
        ,REGION_NAME: str = "us-east-1"     # AWS region
    ):
    import boto3
    import base64
    import json
    
    # Create Bedrock client
    # This requires AWS credentials to be configured (via environment variables, .env file, or IAM role).
    # Recommended: Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_DEFAULT_REGION environment variables.
    bedrock_client = boto3.client('bedrock-runtime', region_name=REGION_NAME)
    
    # Prepare images
    image_content = []  # Initialize
    for image in IMAGE_LIST:
        if looks_like_base64(image):
            image_b64 = image
        else:
            # Encode image as base64
            image_b64 = encode_image(image)
        
        # Append to list formatted for Bedrock (Claude)
        # Bedrock expects images in source.bytes format
        image_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": image_b64
            }
        })
    
    # Build messages for Bedrock API
    user_content = [{"type": "text", "text": USER_QUESTION}] + image_content
    
    messages = [
        {"role": "user", "content": user_content}
    ]
    
    # Call Bedrock API
    response = bedrock_client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": messages
        })
    )
    
    # Parse response
    response_body = json.loads(response['body'].read())
    
    return response_body['content'][0]['text']

def query_multiple_images_openai(
        IMAGE_LIST: list[str]       # List of image strings. May be either full paths to image files or base64-encoded images.
        ,SYSTEM_PROMPT: str         # System prompt
        ,USER_QUESTION: str         # User question
        ,MODEL_ID: str = None       # Optional OpenAI model ID override
    ):
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. "
            "Set OPENAI_API_KEY when VECTORSTORE_LLM_PROVIDER=openai."
        )

    vision_model = MODEL_ID or os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    if base_url:
        client = OpenAI(api_key=api_key, base_url=base_url)
    else:
        client = OpenAI(api_key=api_key)

    image_content = []
    for image in IMAGE_LIST:
        if looks_like_base64(image):
            image_b64 = image
        else:
            image_b64 = encode_image(image)
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

#%% TESTS
# *****************************************************************************
if __name__ == '__main__':
    
    import langroid as lr
    
    print(f"> Testing Langroid agent with azure_llm_gpt4o:")
    agent_config_gpt4o = lr.ChatAgentConfig(llm=azure_llm_gpt4o)
    test_agent_gpt4o = lr.ChatAgent(agent_config_gpt4o)
    test_agent_gpt4o.llm_response("who is Taylor Swift?")

    print(f"> Testing Langroid agent with aws_llm_claude4:")
    agent_config_claude4 = lr.ChatAgentConfig(llm=aws_llm_claude4)
    test_agent_claude4 = lr.ChatAgent(agent_config_claude4)
    test_agent_claude4.llm_response("who is Taylor Swift?")

    print(f"> Testing Langroid agent with aws_llm_claude35:")
    agent_config_claude35 = lr.ChatAgentConfig(llm=aws_llm_claude35)
    test_agent_claude35 = lr.ChatAgent(agent_config_claude35)
    test_agent_claude35.llm_response("who is Taylor Swift?")

    print(f"> Testing Langroid agent with aws_llm_gptoss:")
    agent_config_gptoss = lr.ChatAgentConfig(llm=aws_llm_gptoss)
    test_agent_gptoss = lr.ChatAgent(agent_config_gptoss)
    test_agent_gptoss.llm_response("who is Taylor Swift?")
