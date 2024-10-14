# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import os
import json
import boto3
import zipfile
import tempfile
import logging

s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION'))
s3_bucket_name = os.environ.get('DATA_MANIFEST_BUCKET_NAME', '')

def build_manifest_file_content(records):
    data_file_list = [
        {
            'bucketName': r['s3']['bucket']['name'],
            'objectKey': r['s3']['object']['key']
        }
        for r in records if 's3' in r
    ]
    
    return json.dumps({'data': data_file_list})

def create_zip_file_content(object_key, file_content):
    file_path = os.path.join(tempfile.gettempdir(), object_key)
    
    with zipfile.ZipFile(file_path, 'w') as archive:
        archive.writestr('manifest.json', file_content)
    
    with open(file_path, 'rb') as f:
        return f.read()

def upload_to_s3(zip_file_content):
    s3_client.put_object(
        Bucket=s3_bucket_name,
        Key='manifest.json.zip',
        Body=zip_file_content
    )

def lambda_handler(event, context):
    logging.info('Event: %s', json.dumps(event, indent=2))
    try:
        if 'Records' in event and len(event['Records']) > 0:
            message = json.loads(event['Records'][0]['Sns']['Message'])
            records = message.get('Records', [])
            if records:
                logging.info('Updating the data manifest file')
                file_content = build_manifest_file_content(records)
                zip_file_content = create_zip_file_content(context.aws_request_id, file_content)
                upload_to_s3(zip_file_content)
    except Exception as e:
        logging.error('Error: %s', e)
        raise e
