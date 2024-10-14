import os
from aws_cdk import (
    Stack,
    StackProps,
    CfnParameter,
    CustomResource,
    CfnOutput,
    Duration,
)
from constructs import Construct
import aws_cdk.aws_iam as iam
import aws_cdk.aws_sagemaker as sagemaker
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_lambda_nodejs as lambda_nodejs
import aws_cdk.custom_resources as custom_resource
import aws_cdk.aws_logs as logs

class ModelDeploymentStackProps(StackProps):
    def __init__(self, model_endpoint_export_name_prefix: str, project_name: str, **kwargs):
        super().__init__(**kwargs)
        self.model_endpoint_export_name_prefix = model_endpoint_export_name_prefix
        self.project_name = project_name

class ModelDeploymentStack(Stack):
    def __init__(self, scope: Construct, id: str, props: ModelDeploymentStackProps) -> None:
        super().__init__(scope, id, props)

        model_package_name = CfnParameter(self, 'modelPackageName', type='String')

        endpoint_instance_type = CfnParameter(self, 'endpointInstanceType', type='String', default='ml.t2.medium')

        endpoint_instance_count = CfnParameter(self, 'endpointInstanceCount', type='Number', default=1, min_value=1)

        execution_role = iam.Role(self, 'SageMakerModelExecutionRole',
            assumed_by=iam.ServicePrincipal('sagemaker.amazonaws.com'),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name('AmazonSageMakerFullAccess')],
        )

        pipeline_model_function_role = iam.Role(self, 'DataFunctionRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole')],
        )

        pipeline_model_function_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=['sagemaker:CreateModel', 'sagemaker:DeleteModel', 'sagemaker:DescribeModelPackage'],
                resources=[
                    f'arn:aws:sagemaker:{self.region}:{self.account}:model/{props.project_name}*',
                    model_package_name.value_as_string,
                ],
            )
        )

        pipeline_model_function_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=['iam:PassRole'],
                resources=[execution_role.role_arn],
            )
        )

        # Get the current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Define the Lambda Layer
        pipeline_model_function_layer = lambda_.LayerVersion(self, 'PipelineModelFunctionLayer',
            code=lambda_.Code.from_asset(os.path.join(current_dir, '../layers/PipelineModelFunctionLayer.zip')),
            compatible_runtimes=[lambda_.Runtime.NODEJS_18_X],
            description='A Lambda layer for common dependencies',
        )

        # Define the Lambda Function with the Layer
        pipeline_model_function = lambda_nodejs.NodejsFunction(self, 'PipelineModelFunction',
            runtime=lambda_.Runtime.NODEJS_18_X,
            handler='handler',
            entry=os.path.join(current_dir, '../customResources/pipelineModel/index.py'),
            timeout=Duration.minutes(1),
            role=pipeline_model_function_role,
            layers=[pipeline_model_function_layer],
        )

        pipeline_model_custom_resource_provider = custom_resource.Provider(
            self,
            'PipelineModelCustomResourceProvider',
            on_event_handler=pipeline_model_function,
            log_retention=logs.RetentionDays.ONE_DAY,
        )

        pipeline_model_custom_resource = CustomResource(self, 'PipelineModelCustomResource',
            service_token=pipeline_model_custom_resource_provider.service_token,
            properties={
                'modelPackageName': model_package_name.value_as_string,
                'sagemakerExecutionRole': execution_role.role_arn,
                'projectName': props.project_name,
            },
        )

        pipeline_model_custom_resource.node.add_dependency(execution_role)

        endpoint_config = sagemaker.CfnEndpointConfig(self, 'SageMakerModelEndpointConfig',
            production_variants=[{
                'initialInstanceCount': endpoint_instance_count.value_as_number,
                'initialVariantWeight': 1.0,
                'instanceType': endpoint_instance_type.value_as_string,
                'modelName': pipeline_model_custom_resource.ref,
                'variantName': 'AllTraffic',
            }],
        )

        endpoint_config.node.add_dependency(pipeline_model_custom_resource)

        endpoint = sagemaker.CfnEndpoint(self, 'SageMakerModelEndpoint',
            endpoint_config_name=endpoint_config.get_att('EndpointConfigName').to_string(),
        )

        endpoint.node.add_dependency(endpoint_config)

        CfnOutput(self, 'ModelEndpointOutput',
                  value=endpoint.ref,
                  export_name=f"{props.model_endpoint_export_name_prefix}-{props.project_name}")

        CfnOutput(self, 'ModelEndpointNameOutput',
                  value=endpoint.get_att('EndpointName').to_string(),
                  export_name=f"{props.model_endpoint_export_name_prefix}-Name-{props.project_name}")
