#%% PACKAGES
# *****************************************************************************
'''
When running on local, these rely on the following environment variables set in
.env:
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    AWS_BEARER_TOKEN_BEDROCK
    AWS_REGION

When running on the EC2 instance, these are not required if an IAM role has been
setup for the app server to access Bedrock.
'''
from dotenv import find_dotenv, load_dotenv, dotenv_values
dotenv_loaded = load_dotenv()
dotenv_dict = dotenv_values()
if dotenv_loaded:
    print('> Environment file loaded.')
else:
    print('> Environment file is either empty or not found!')

#%% TEST WITH BOTO3
# *****************************************************************************                        
import boto3
import json

try:
    # Create an Amazon Bedrock client
    client = boto3.client(
        service_name="bedrock-runtime",
        region_name="us-east-1" # If you've configured a default region, you can omit this line
    )
    
    # Define the model and message
    messages = [{"role": "user", "content": [{"text": "Suggest me a good restaurant in bangalore?"}]}]
    messages_2 = [{"role": "user", "content": [{"text": "Suggest me a good restaurant in los angeles?"}]}]
    messages_3 = [{"role": "user", "content": [{"text": "Suggest me a good restaurant in boston?"}]}]
    
	# -------------------------------------------------------------------------
    # Claude 4
	# -------------------------------------------------------------------------
    print(f"\n> Testing boto3 with Claude 4:")
    print('='*50)
    model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    response = client.converse(
        modelId=model_id,
        messages=messages,
    )
    print(response)
    
    # response = client.converse(
    #     modelId=model_id,
    #     messages=messages_2,
    # )
    # print(response)

    # response = client.converse(
    #     modelId=model_id,
    #     messages=messages_3,
    # )
    # print(response)
    
	# -------------------------------------------------------------------------
    # GPT-OSS
	# -------------------------------------------------------------------------
    print(f"\n> Testing boto3 with GPT-OSS:")
    print('='*50)
    model_id = 'openai.gpt-oss-120b-1:0'
    response = client.converse(
        modelId=model_id,
        messages=messages,
    )
    print(response)
    
	# -------------------------------------------------------------------------
    # Claude 3.5 Haiku
	# -------------------------------------------------------------------------
    print(f"\n> Testing boto3 with Claude 3.5 Haiku:")
    print('='*50)
    model_id = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
    response = client.converse(
        modelId=model_id,
        messages=messages,
    )
    print(response)
    
	# -------------------------------------------------------------------------
    # Claude 3.5 Sonnet
	# -------------------------------------------------------------------------
    print(f"\n> Testing boto3 with Claude 3.5 Sonnet:")
    print('='*50)
    model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    response = client.converse(
        modelId=model_id,
        messages=messages,
    )
    print(response)

	# -------------------------------------------------------------------------
    # Titan Text Embedding
	# -------------------------------------------------------------------------
    print(f"\n> Testing boto3 with Titan Text Embedding:")
    print('='*50)
    
    test_text = "This is a test sentence for embedding."
    
    # Prepare the request body
    request_body = {
        "inputText": test_text
    }
    
    # Invoke the model
    model_id = "amazon.titan-embed-text-v2:0"
    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(request_body)
    )
    
    # Parse the response
    response_body = json.loads(response['body'].read())
    embedding = response_body.get('embedding')
    
    # Display results
    print("✓ Connection successful!")
    print(f"✓ Model invoked successfully")
    print(f"✓ Embedding dimension: {len(embedding)}")
    print(f"✓ First 5 values: {embedding[:5]}")

except Exception as e:
    print(f"Exception: {e}")

#%% USING LITELLM
# *****************************************************************************              
from litellm import completion

try:
    # Claude 4
    print(f"\n> Testing litellm with Claude 4:")
    print('='*50)
    response = completion(
      model="bedrock/us.anthropic.claude-sonnet-4-20250514-v1:0",
      messages=[{ "content": "Hello, how are you?","role": "user"}]
    )
    print(response)
    
    # GPT-OSS
    print(f"\n> Testing litellm with GPT-OSS:")
    print('='*50)
    response = completion(
      model="bedrock/openai.gpt-oss-120b-1:0",
      messages=[{ "content": "Hello, how are you?","role": "user"}]
    )
    print(response)

    # Claude 3.5 Haiku
    print(f"\n> Testing litellm with Claude 3.5 Haiku:")
    print('='*50)
    response = completion(
      model="bedrock/us.anthropic.claude-3-5-haiku-20241022-v1:0",
      messages=[{ "content": "Hello, how are you?","role": "user"}]
    )
    print(response)

except Exception as e:
    print(f"Exception: {e}")

#%% USING WITH LANGROID
# *****************************************************************************   
import langroid as lr
import langroid.language_models as lrlm
    
try:       
    # Claude 4
    print(f"\n> Testing langroid agent with Claude 4:")
    print('='*50)
    aws_llm_claude4 = lrlm.OpenAIGPTConfig(
        chat_model="litellm/bedrock/us.anthropic.claude-sonnet-4-20250514-v1:0"
        
        # Model parameters
        ,chat_context_length=100000
        ,max_output_tokens=4096
        ,temperature=0.0
    )
    agent_config_claude4 = lr.ChatAgentConfig(llm=aws_llm_claude4)
    test_agent_claude4 = lr.ChatAgent(agent_config_claude4)
    test_agent_claude4.llm_response("who is Taylor Swift?")
    
    # GPT-OSS
    print(f"\n> Testing langroid agent with GPT-OSS:")
    print('='*50)
    aws_llm_gptoss = lrlm.OpenAIGPTConfig(
        chat_model="litellm/bedrock/openai.gpt-oss-120b-1:0"
        ,api_base="https://bedrock-runtime.us-east-1.amazonaws.com"
        
        # Model parameters
        ,chat_context_length=100000
        ,max_output_tokens=4096
        ,temperature=0.0
    )
    agent_config_gptoss = lr.ChatAgentConfig(llm=aws_llm_gptoss)
    test_agent_gptoss = lr.ChatAgent(agent_config_gptoss)
    test_agent_gptoss.llm_response("who is Taylor Swift?")

    # Claude 3.5 Haiku
    print(f"\n> Testing langroid agent with Claude 3.5 Haiku:")
    print('='*50)
    aws_llm_claude35 = lrlm.OpenAIGPTConfig(
        chat_model="litellm/bedrock/us.anthropic.claude-3-5-haiku-20241022-v1:0"
        ,api_base="https://bedrock-runtime.us-east-1.amazonaws.com"
        
        # Model parameters
        ,chat_context_length=100000
        ,max_output_tokens=4096
        ,temperature=0.0
    )
    agent_config_claude35 = lr.ChatAgentConfig(llm=aws_llm_claude35)
    test_agent_claude35 = lr.ChatAgent(agent_config_claude35)
    test_agent_claude35.llm_response("who is Taylor Swift?")

except Exception as e:
    print(f"Exception: {e}")
