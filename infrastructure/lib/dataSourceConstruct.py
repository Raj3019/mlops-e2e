import os
from aws_cdk import (
    Stack,
    Duration,
    aws_s3 as s3,
    aws_iam as iam,
    aws_sns as sns,
    aws_lambda as lambda_,
    aws_lambda_nodejs as lambda_nodejs,
    aws_s3_notifications as s3_notifications,
    aws_sns_subscriptions as sns_subscriptions,
)
from constructs import Construct

class DataSourceConstruct(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # IAM Role for Lambda Function
        data_source_monitor_function_role = iam.Role(self, "DataFunctionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")]
        )

        # S3 Bucket for Data
        self.data_bucket = s3.Bucket(self, "DataBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            public_read_access=False
        )

        self.data_bucket.grant_read(data_source_monitor_function_role)

        # S3 Bucket for Data Manifest
        self.data_manifest_bucket = s3.Bucket(self, "DataManifestBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=True,
            public_read_access=False
        )

        self.data_manifest_bucket.grant_write(data_source_monitor_function_role)

        # SNS Topic for New Data Notifications
        new_data_topic = sns.Topic(self, "NewDataTopic")

        # Add S3 Notification to SNS Topic
        self.data_bucket.add_object_created_notification(s3_notifications.SnsDestination(new_data_topic))

        # Lambda Function for Monitoring Data Source
        data_monitor_function = lambda_nodejs.NodejsFunction(self, "DataSourceMonitorFunction",
            runtime=lambda_.Runtime.NODEJS_18_X,
            handler="handler",
            entry=os.path.join(os.path.dirname(__file__), "../functions/dataSourceMonitor/src/index.py"),
            timeout=Duration.minutes(1),
            role=data_source_monitor_function_role,
            environment={
                "DATA_MANIFEST_BUCKET_NAME": self.data_manifest_bucket.bucket_name
            }
        )

        # Subscribe Lambda Function to SNS Topic
        new_data_topic.add_subscription(sns_subscriptions.LambdaSubscription(data_monitor_function))