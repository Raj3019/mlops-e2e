from aws_cdk import (
    Stack,
    StackProps,
    CfnOutput,
)
from constructs import Construct
# Ensure the module name and path are correct
from .codePipelineConstruct import CodePipelineConstruct, CodePipelineConstructPropsBase  # Adjusted import path
from .dataSourceConstruct import DataSourceConstruct
from .sageMakerConstruct import SageMakerConstruct

class InfrastructureStack(Stack):
    def __init__(self, scope: Construct, id: str, props: CodePipelineConstructPropsBase) -> None:
        super().__init__(scope, id, props)

        # Create Data Source Construct
        data_source = DataSourceConstruct(self, "DataSource")

        # Create SageMaker Construct
        sage_maker = SageMakerConstruct(self, "SageMakerConstruct",
            data_bucket=data_source.data_bucket,
        )

        # Create Code Pipeline Construct
        code_pipeline = CodePipelineConstruct(self, "CodePipeline",
            **props,
            data_manifest_bucket=data_source.data_manifest_bucket,
            sage_maker_artifact_bucket=sage_maker.sagemaker_artifact_bucket,
            sage_maker_execution_role=sage_maker.sagemaker_execution_role,
        )

        # Output the Code Pipeline name
        CfnOutput(self, "CodePipelineOutput",
            value=code_pipeline.pipeline.pipeline_name,
        )

        # Output the Data Bucket name
        CfnOutput(self, "DataBucketOutput",
            value=data_source.data_bucket.bucket_name,
            export_name="MLOpsE2EDemo-DataBucket",
        )

        # Output the Data Manifest Bucket name
        CfnOutput(self, "DataManifestBucketOutput",
            value=data_source.data_manifest_bucket.bucket_name,
        )

        # Output the SageMaker Artifact Bucket name
        CfnOutput(self, "SageMakerArtifactBucketOutput",
            value=sage_maker.sagemaker_artifact_bucket.bucket_name,
            export_name="MLOpsE2EDemo-SageMakerArtifactBucket",
        )

        # Output the SageMaker Execution Role ARN
        CfnOutput(self, "SageMakerExecutionRoleOutput",
            value=sage_maker.sagemaker_execution_role.role_arn,
            export_name="MLOpsE2EDemo-SageMakerExecutionRole",
        )
