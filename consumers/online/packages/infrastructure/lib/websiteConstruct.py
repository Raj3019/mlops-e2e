import os
import json
from aws_cdk import (
    Duration,
    CfnOutput,
    CustomResource,
    Stack,
)
from constructs import Construct
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_nodejs as lambda_nodejs
from aws_cdk import aws_s3_deployment as s3_deployment
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import custom_resources as custom_resource
from aws_cdk import aws_logs as logs
from aws_cdk import aws_apigateway as apigateway

class WebsiteConstructProps:
    def __init__(self, website_dist_path: str, api: apigateway.RestApi):
        self.website_dist_path = website_dist_path
        self.api = api

class WebsiteConstruct(Construct):
    def __init__(self, scope: Construct, id: str, props: WebsiteConstructProps) -> None:
        super().__init__(scope, id)

        cloud_front_oia = cloudfront.CfnCloudFrontOriginAccessIdentity(self, 'OIA',
            cloud_front_origin_access_identity_config={
                'comment': 'OIA for website.'
            }
        )

        origin_access_identity = cloudfront.OriginAccessIdentity.from_origin_access_identity_name(
            self,
            'OriginAccessIdentity',
            cloud_front_oia.ref
        )

        source_bucket = s3.Bucket(self, 'WebsiteBucket',
            website_index_document='index.html',
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        cloud_front_logging_bucket = s3.Bucket(self, 'S3BucketForWebsiteLogging',
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
        )

        cloud_front_distribution = cloudfront.CloudFrontWebDistribution(self, 'WebsiteCloudFront',
            price_class=cloudfront.PriceClass.PRICE_CLASS_ALL,
            default_root_object='index.html',
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            logging_config={
                'bucket': cloud_front_logging_bucket,
            },
            origin_configs=[{
                's3_origin_source': {
                    's3_bucket_source': source_bucket,
                    'origin_access_identity': origin_access_identity,
                },
                'behaviors': [{'is_default_behavior': True}],
            }],
            error_configurations=[{
                'error_code': 404,
                'response_code': 200,
                'response_page_path': '/index.html',
                'error_caching_min_ttl': 0,
            }],
        )

        website_index_bucket = s3.Bucket(self, 'WebsiteIndexBucket',
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        build_website_index_function = lambda_nodejs.NodejsFunction(self, 'BuildWebsiteIndexFunction',
            runtime=lambda_.Runtime.NODEJS_18_X,
            handler='handler',
            entry=os.path.join(os.path.dirname(__file__), '../../website-index-builder/src/index.ts'),
            timeout=Duration.minutes(1),
        )

        website_index_bucket.grant_read_write(build_website_index_function)

        build_website_index_custom_resource_provider = custom_resource.Provider(
            self,
            'BuildWebsiteIndexCustomResourceProvider',
            on_event_handler=build_website_index_function,
            log_retention=logs.RetentionDays.ONE_DAY,
        )

        with open(os.path.join(props.website_dist_path, 'index.html'), 'r') as index_file:
            index_content = index_file.read()

        build_website_index_custom_resource = CustomResource(self, 'BuildWebsiteIndexCustomResource',
            service_token=build_website_index_custom_resource_provider.service_token,
            properties={
                's3BucketName': website_index_bucket.bucket_name,
                'template': index_content,
                'apiUrl': props.api.url,
            }
        )

        build_website_index_custom_resource.node.add_dependency(website_index_bucket)
        build_website_index_custom_resource.node.add_dependency(props.api)

        cached_deployment = s3_deployment.BucketDeployment(self, 'CachedDeployWebsite',
            sources=[s3_deployment.Source.asset(props.website_dist_path, exclude=['index.html', 'config.js', 'config.*.js'])],
            prune=False,
            destination_bucket=source_bucket,
            distribution=cloud_front_distribution,
        )

        uncached_deployment = s3_deployment.BucketDeployment(self, 'UncachedDeployWebsite',
            sources=[s3_deployment.Source.bucket(website_index_bucket, build_website_index_custom_resource.ref)],
            destination_bucket=source_bucket,
            prune=False,
            distribution=cloud_front_distribution,
            cache_control=[s3_deployment.CacheControl.no_cache()],
        )

        uncached_deployment.node.add_dependency(cached_deployment)
        uncached_deployment.node.add_dependency(build_website_index_custom_resource)

        CfnOutput(self, 'ModelConsumerOnlineWebsiteCloudfrontDistributionId', 
                  value=cloud_front_distribution.distribution_id, 
                  export_name='ModelConsumerOnlineWebsiteCloudfrontDistributionId')

        CfnOutput(self, 'ModelConsumerOnlineCloudfrontDistributionDomainName', 
                  value=cloud_front_distribution.distribution_domain_name, 
                  export_name='ModelConsumerOnlineCloudfrontDistributionDomainName')