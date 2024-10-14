from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_iam as iam,
    aws_sns as sns,
    aws_codecommit as codecommit,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
)
from constructs import Construct

class CodePipelineConstructPropsBase:
    def __init__(self, project_name: str, repo_type: str):
        self.project_name = project_name
        self.repo_type = repo_type

class CodePipelineConstructPropsGithubSource(CodePipelineConstructPropsBase):
    def __init__(self, project_name: str, github_connection_arn: str, github_repo_owner: str, github_repo_name: str, github_repo_branch: str = 'main'):
        super().__init__(project_name, 'git')
        self.github_connection_arn = github_connection_arn
        self.github_repo_owner = github_repo_owner
        self.github_repo_name = github_repo_name
        self.github_repo_branch = github_repo_branch

class CodePipelineConstructPropsCodeCommitSource(CodePipelineConstructPropsBase):
    def __init__(self, project_name: str):
        super().__init__(project_name, 'codecommit')

class CodePipelineConstructProps:
    def __init__(self, data_manifest_bucket: s3.Bucket, sage_maker_artifact_bucket: s3.Bucket, sage_maker_execution_role: iam.Role, repo_props: CodePipelineConstructPropsBase):
        self.data_manifest_bucket = data_manifest_bucket
        self.sage_maker_artifact_bucket = sage_maker_artifact_bucket
        self.sage_maker_execution_role = sage_maker_execution_role
        self.repo_props = repo_props

class CodePipelineConstruct(Construct):
    def __init__(self, scope: Construct, id: str, props: CodePipelineConstructProps):
        super().__init__(scope, id)

        self.pipeline = codepipeline.Pipeline(self, 'MLOpsPipeline', restart_execution_on_update=True)

        source_code_output = codepipeline.Artifact('SourceCodeOutput')
        source_data_output = codepipeline.Artifact('SourceDataOutput')
        build_output = codepipeline.Artifact('BuildOutput')
        pipeline_output = codepipeline.Artifact('PipelineOutput')

        # Source Code
        if props.repo_props.repo_type == 'git':
            source_code = codepipeline_actions.CodeStarConnectionsSourceAction(
                action_name='SourceCode',
                output=source_code_output,
                owner=props.repo_props.github_repo_owner,
                repo=props.repo_props.github_repo_name,
                branch=props.repo_props.github_repo_branch,
                connection_arn=props.repo_props.github_connection_arn,
            )
        else:
            source_repo = codecommit.Repository(self, 'SourceRepository', repository_name='MLOpsE2EDemo')
            source_code = codepipeline_actions.CodeCommitSourceAction(
                action_name='SourceCode',
                output=source_code_output,
                repository=source_repo,
                branch='main',
            )

        # Source Data
        source_data = codepipeline_actions.S3SourceAction(
            action_name='SourceData',
            output=source_data_output,
            bucket=props.data_manifest_bucket,
            bucket_key='manifest.json.zip',
        )

        self.pipeline.add_stage(stage_name='Source', actions=[source_code, source_data])

        # CI
        build_project = codebuild.PipelineProject(self, 'CIBuild',
            build_spec=codebuild.BuildSpec.from_source_filename('./buildspecs/build.yml'),
            environment={
                'build_image': codebuild.LinuxBuildImage.STANDARD_6_0,
                'privileged': True,
            },
        )

        build = codepipeline_actions.CodeBuildAction(
            action_name='CIBuild',
            project=build_project,
            input=source_code_output,
            extra_inputs=[source_data_output],
            outputs=[build_output],
        )

        self.pipeline.add_stage(stage_name='CI', actions=[build])

        # ML Pipeline
        ml_pipeline_role = iam.Role(self, 'MLPipelineRole', assumed_by=iam.ServicePrincipal('codebuild.amazonaws.com'))

        ml_pipeline_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=['s3:CreateBucket', 's3:GetObject', 's3:PutObject', 's3:ListBucket'],
            resources=[props.sage_maker_artifact_bucket.bucket_arn, f"{props.sage_maker_artifact_bucket.bucket_arn}/*"],
        ))

        ml_pipeline_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                'sagemaker:CreatePipeline',
                'sagemaker:ListTags',
                'sagemaker:AddTags',
                'sagemaker:UpdatePipeline',
                'sagemaker:DescribePipeline',
                'sagemaker:StartPipelineExecution',
                'sagemaker:DescribePipelineExecution',
                'sagemaker:ListPipelineExecutionSteps',
            ],
            resources=[
                f"arn:aws:sagemaker:{Stack.of(self).region}:{Stack.of(self).account}:pipeline/{props.repo_props.project_name}",
                f"arn:aws:sagemaker:{Stack.of(self).region}:{Stack.of(self).account}:pipeline/{props.repo_props.project_name}/*",
            ],
        ))

        ml_pipeline_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=['iam:PassRole'],
            resources=[props.sage_maker_execution_role.role_arn],
        ))

        ml_pipeline_project = codebuild.PipelineProject(self, 'MLPipeline',
            build_spec=codebuild.BuildSpec.from_source_filename('./buildspecs/pipeline.yml'),
            role=ml_pipeline_role,
            environment={
                'build_image': codebuild.LinuxBuildImage.STANDARD_6_0,
            },
        )

        ml_pipeline = codepipeline_actions.CodeBuildAction(
            action_name='MLPipeline',
            project=ml_pipeline_project,
            input=build_output,
            outputs=[pipeline_output],
            environment_variables={
                'SAGEMAKER_ARTIFACT_BUCKET': {
                    'type': codebuild.BuildEnvironmentVariableType.PLAINTEXT,
                    'value': props.sage_maker_artifact_bucket.bucket_name,
                },
                'SAGEMAKER_PIPELINE_ROLE_ARN': {
                    'type': codebuild.BuildEnvironmentVariableType.PLAINTEXT,
                    'value': props.sage_maker_execution_role.role_arn,
                },
                'SAGEMAKER_PROJECT_NAME': {
                    'type': codebuild.BuildEnvironmentVariableType.PLAINTEXT,
                    'value': props.repo_props.project_name,
                },
                'PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION': {
                    'type': codebuild.BuildEnvironmentVariableType.PLAINTEXT,
                    'value': 'python',
                },
            },
        )

        self.pipeline.add_stage(stage_name='MLPipeline', actions=[ml_pipeline])

        # Deploy
        deployment_approval_topic = sns.Topic(self, 'ModelDeploymentApprovalTopic', topic_name='ModelDeploymentApprovalTopic')

        manual_approval_action = codepipeline_actions.ManualApprovalAction(
            action_name='Approval',
            run_order=1,
            notification_topic=deployment_approval_topic,
            additional_information=f"A new version of the model for project {props.repo_props.project_name} is waiting for approval",
            external_entity_link=f"https://{Stack.of(self).region}.console.aws.amazon.com/sagemaker/home?region={Stack.of(self).region}#/studio/",
        )

        deploy_role = iam.Role(self, 'DeployRole', assumed_by=iam.ServicePrincipal('codebuild.amazonaws.com'))

        deploy_role.add_to_policy(iam.PolicyStatement(
            conditions={'ForAnyValue:StringEquals': {'aws:CalledVia': ['cloudformation.amazonaws.com']}},
            actions=['lambda:*Function*'],
            resources=[f"arn:aws:lambda:{Stack.of(self).region}:{Stack.of(self).account}:function:Deployment-{props.repo_props.project_name}*"],
        ))

        deploy_role.add_to_policy(iam.PolicyStatement(
            conditions={'ForAnyValue:StringEquals': {'aws:CalledVia': ['cloudformation.amazonaws.com']}},
            actions=['sagemaker:*Endpoint*'],
            resources=['*'],
        ))

        deploy_role.add_to_policy(iam.PolicyStatement(
            conditions={'ForAnyValue:StringEquals': {'aws:CalledVia': ['cloudformation.amazonaws.com']}},
            actions=['iam:*Role', 'iam:*Policy*', 'iam:*RolePolicy'],
            resources=[f"arn:aws:iam::{Stack.of(self).account}:role/Deployment-{props.repo_props.project_name}-*"],
        ))

        deploy_role.add_to_policy(iam.PolicyStatement(
            actions=[
                'cloudformation:DescribeStacks',
                'cloudformation:CreateChangeSet',
                'cloudformation:DescribeChangeSet',
                'cloudformation:ExecuteChangeSet',
                'cloudformation:DescribeStackEvents',
                'cloudformation:DeleteChangeSet',
                'cloudformation:GetTemplate',
            ],
            resources=[
                f"arn:aws:cloudformation:{Stack.of(self).region}:{Stack.of(self).account}:stack/CDKToolkit/*",
                f"arn:aws:cloudformation:{Stack.of(self).region}:{Stack.of(self).account}:stack/Deployment-{props.repo_props.project_name}/*",
            ],
        ))

        deploy_role.add_to_policy(iam.PolicyStatement(
            actions=['s3:*Object', 's3:ListBucket', 's3:GetBucketLocation'],
            resources=['arn:aws:s3:::cdktoolkit-stagingbucket-*'],
        ))

        deploy_role.add_to_policy(iam.PolicyStatement(
            actions=['ssm:GetParameter'],
            resources=[f"arn:aws:ssm:{Stack.of(self).region}:{Stack.of(self).account}:parameter/cdk-bootstrap/*"],
        ))

        deploy_role.add_to_policy(iam.PolicyStatement(
            actions=['sts:AssumeRole', 'iam:PassRole'],
            resources=[f"arn:aws:iam::{Stack.of(self).account}:role/cdk*"],
        ))

        deploy_project = codebuild.PipelineProject(self, 'DeployProject',
            build_spec=codebuild.BuildSpec.from_source_filename('./buildspecs/deploy.yml'),
            role=deploy_role,
            environment={
                'build_image': codebuild.LinuxBuildImage.STANDARD_6_0,
                'privileged': True,
            },
        )

        deploy = codepipeline_actions.CodeBuildAction(
            action_name='Deploy',
            run_order=2,
            project=deploy_project,
            input=build_output,
            extra_inputs=[pipeline_output],
        )

        self.pipeline.add_stage(stage_name='Deploy', actions=[manual_approval_action, deploy])