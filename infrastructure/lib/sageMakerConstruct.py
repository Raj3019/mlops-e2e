from constructs import Construct
from aws_cdk import (
    aws_s3 as s3,
    aws_iam as iam,
)

class SageMakerConstructProps:
    def __init__(self, data_bucket: s3.Bucket):
        self.data_bucket = data_bucket

class SageMakerConstruct(Construct):
    def __init__(self, scope: Construct, id: str, props: SageMakerConstructProps) -> None:
        super().__init__(scope, id)

        self.sagemaker_artifact_bucket = s3.Bucket(self, 'SageMakerArtifactBucket',
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        self.sagemaker_execution_role = iam.Role(self, 'SageMakerExecutionRole',
            assumed_by=iam.ServicePrincipal('sagemaker.amazonaws.com'),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name('AmazonSageMakerFullAccess')],
        )

        self.sagemaker_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=['s3:GetObject', 's3:ListBucket'],
                resources=[props.data_bucket.bucket_arn, f"{props.data_bucket.bucket_arn}/*"],
            )
        )

        self.sagemaker_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=['s3:GetObject', 's3:PutObject', 's3:ListBucket'],
                resources=[self.sagemaker_artifact_bucket.bucket_arn, f"{self.sagemaker_artifact_bucket.bucket_arn}/*"],
            )
        )