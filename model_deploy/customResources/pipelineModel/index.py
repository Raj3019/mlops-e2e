import os
import json
import boto3
from botocore.exceptions import ClientError
import datetime

sagemaker_client = boto3.client('sagemaker', region_name=os.environ['AWS_REGION'])

class CustomResourceEvent:
    def __init__(self, request_type: str, physical_resource_id: str, resource_properties: dict):
        self.RequestType = request_type
        self.PhysicalResourceId = physical_resource_id
        self.ResourceProperties = resource_properties

async def create_model(project_name: str, model_package_name: str, execution_role_arn: str):
    date = datetime.datetime.utcnow()
    model_name = f"{project_name}-{date.year}-{date.month}-{date.day}-{date.hour}-{date.minute}-{date.second}-{date.microsecond}"
    print(f"Creating model {model_name} for modelPackageName: {model_package_name} with role {execution_role_arn}")

    model_package = sagemaker_client.describe_model_package(ModelPackageName=model_package_name)

    await sagemaker_client.create_model(
        ModelName=model_name,
        Containers=[
            {
                'Image': container['Image'],
                'ModelDataUrl': container['ModelDataUrl'],
                'Environment': container.get('Environment', {})
            }
            for container in model_package['InferenceSpecification']['Containers']
        ],
        ExecutionRoleArn=execution_role_arn
    )

    return {
        'PhysicalResourceId': model_name,
    }

async def delete_model(model_name: str):
    print('Deleting model:', model_name)
    await sagemaker_client.delete_model(ModelName=model_name)
    print('Deleted model:', model_name)
    return {}

async def dispatch(event: CustomResourceEvent, request_type: str):
    props = event.ResourceProperties
    resource_id = event.PhysicalResourceId

    if request_type in ['Create', 'Update']:
        return await create_model(props['projectName'], props['modelPackageName'], props['sagemakerExecutionRole'])
    elif request_type == 'Delete':
        return await delete_model(resource_id)
    else:
        raise Exception('Unsupported RequestType')

async def handler(event: CustomResourceEvent):
    print('Event:\n', json.dumps(event, indent=2))
    
    try:
        request_type = event['RequestType']
        data = await dispatch(event, request_type)
        print('Response:', data)
        return data
    except Exception as e:
        print('Error:', e)
        raise e