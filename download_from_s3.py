import os
import boto3
import inspect

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

if __name__ == '__main__':
    sbx_bucket = 'knva-sbx-prj1-nifty-s3'
    download_from_s3(
        SOURCE_BUCKET=sbx_bucket
        ,SOURCE_PATH='nifty_input_data/nif_metadata/'
        ,DESTINATION_PATH='/home/ec2-user/knva-nifty/database'
        ,SOURCE_FILE='NIF Repository.xlsx'
    )
    download_from_s3(
        SOURCE_BUCKET=sbx_bucket
        ,SOURCE_PATH='nifty_input_data/nif_metadata/'
        ,DESTINATION_PATH='/home/ec2-user/knva-nifty/database'
        ,SOURCE_FILE='KNA NIF Create KNV Document Report.xlsx'
    )
    download_from_s3(
        SOURCE_BUCKET=sbx_bucket
        ,SOURCE_PATH='nifty_input_data/nif_metadata/'
        ,DESTINATION_PATH='/home/ec2-user/knva-nifty/database'
        ,SOURCE_FILE='Form Process and Task Report.xlsx'
    )
