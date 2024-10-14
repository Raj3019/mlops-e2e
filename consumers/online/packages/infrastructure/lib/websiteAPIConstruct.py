from aws_cdk import (
    Duration,
    Fn,
    Stack,
    StackProps,
)
from constructs import Construct
from aws_cdk import aws_iam as iam
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_nodejs as lambda_nodejs
import os

class WebsiteApiConstructProps:
    def __init__(self, ip_cidr_blocks: list, sage_make_endpoint_arn: str, sage_maker_endpoint_name: str):
        self.ip_cidr_blocks = ip_cidr_blocks
        self.sage_make_endpoint_arn = sage_make_endpoint_arn
        self.sage_maker_endpoint_name = sage_maker_endpoint_name

class WebsiteApiConstruct(Construct):
    def __init__(self, scope: Construct, id: str, props: WebsiteApiConstructProps) -> None:
        super().__init__(scope, id)

        # Create DynamoDB Table
        data_table = dynamodb.Table(self, 'DataTable',
            partition_key={'name': 'id', 'type': dynamodb.AttributeType.STRING},
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.DEFAULT,
            point_in_time_recovery=True,
        )

        # Create API Gateway Policy Document
        api_gateway_policy = iam.PolicyDocument(statements=[
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=['execute-api:Invoke'],
                resources=['execute-api:/*/*/*'],
                principals=[iam.AnyPrincipal()]
            ),
            iam.PolicyStatement(
                effect=iam.Effect.DENY,
                actions=['execute-api:Invoke'],
                resources=['execute-api:/*/*/*'],
                principals=[iam.AnyPrincipal()],
                conditions={
                    'NotIpAddress': {
                        'aws:SourceIp': props.ip_cidr_blocks,
                    }
                }
            )
        ])

        # Create API Gateway
        self.api = apigateway.RestApi(self, 'DataAPI',
            default_cors_preflight_options={
                'allow_origins': apigateway.Cors.ALL_ORIGINS,
                'allow_methods': apigateway.Cors.ALL_METHODS,
            },
            policy=api_gateway_policy,
            rest_api_name='Data API',
        )

        self.api.latest_deployment.add_to_logical_id(Fn.token_as_any(api_gateway_policy))

        # Add Usage Plan to API Gateway
        self.api.add_usage_plan('WebsiteDataAPIUsagePlan',
            name='WebsiteDataAPIUsagePlan',
            api_stages=[{'api': self.api, 'stage': self.api.deployment_stage}],
            throttle={'burst_limit': 500, 'rate_limit': 1000},
            quota={'limit': 10000000, 'period': apigateway.Period.MONTH},
        )

        # Create IAM Role for Lambda Function
        data_function_role = iam.Role(self, 'DataFunctionRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole')],
        )

        # Grant permissions to the Lambda function role
        data_function_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=['dynamodb:UpdateItem', 'dynamodb:PutItem', 'dynamodb:GetItem'],
            resources=[data_table.table_arn],
        ))

        data_function_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=['sagemaker:InvokeEndpoint'],
            resources=[props.sage_make_endpoint_arn],
        ))

        # Create Lambda Function
        data_function = lambda_nodejs.NodejsFunction(self, 'DataFunction',
            runtime=lambda_.Runtime.NODEJS_18_X,
            handler='handler',
            entry=os.path.join(os.path.dirname(__file__), '../../data-api/src/index.ts'),
            timeout=Duration.seconds(30),
            role=data_function_role,
            environment={
                'SAGEMAKER_ENDPOINT_NAME': props.sage_maker_endpoint_name,
                'DATA_TABLE_NAME': data_table.table_name,
            },
        )

        # Create API Gateway Integration with Lambda Function
        data_integration = apigateway.LambdaIntegration(data_function)

        # Add resource and method to the API Gateway
        data_endpoint = self.api.root.add_resource('data')
        data_endpoint.add_method('POST', data_integration)

        data_feedback_endpoint = data_endpoint.add_resource('{id}')
        data_feedback_endpoint.add_method('POST', data_integration)