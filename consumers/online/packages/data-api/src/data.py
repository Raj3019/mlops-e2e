import os
import boto3
from botocore.exceptions import ClientError

# Initialize AWS SDK clients
sagemaker_runtime = boto3.client('sagemaker-runtime', region_name=os.environ.get('AWS_REGION', ''))
dynamodb_client = boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION', ''))

# Environment variables
sageMakerEndpointName = os.environ.get('SAGEMAKER_ENDPOINT_NAME', '')
dataTableName = os.environ.get('DATA_TABLE_NAME', '')

def get_input(data):
    return f"{data['sex']},{data['length']},{data['diameter']},{data['height']},{data['wholeWeight']},{data['shuckedWeight']},{data['visceraWeight']},{data['shellWeight']}"

async def get_inference(id, data):
    input_string = get_input(data)
    print('Input data:', input_string)

    # Invoke SageMaker endpoint
    try:
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=sageMakerEndpointName,
            Body=input_string.encode('utf-8'),
            ContentType='text/csv',
            Accept='application/json'
        )
        predict = response['Body'].read().decode('utf-8')
        print('Prediction:', predict)

        # Write to DynamoDB with the predicted value
        record = {**data, 'id': id, 'predict': predict}
        dynamodb_client.put_item(
            TableName=dataTableName,
            Item={key: {'S': str(value)} for key, value in record.items()}
        )
        
        return record

    except ClientError as e:
        print(f"Error invoking SageMaker endpoint: {e}")
        return None

async def add_label(id, actual):
    update_expression = 'SET actual = :a'
    
    try:
        response = dynamodb_client.update_item(
            TableName=dataTableName,
            Key={'id': {'S': id}},
            UpdateExpression=update_expression,
            ExpressionAttributeValues={':a': {'S': actual}},
            ReturnValues='ALL_NEW'
        )
        
        return {k: v['S'] for k, v in response.get('Attributes', {}).items()}

    except ClientError as e:
        print(f"Error updating DynamoDB item: {e}")
        return {}