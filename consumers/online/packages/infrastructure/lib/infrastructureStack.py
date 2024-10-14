from aws_cdk import (
    Stack,
    StackProps,
    Fn,
)
from constructs import Construct
from .websiteAPIConstruct import WebsiteApiConstruct  # Adjust the import based on your project structure
from .websiteConstruct import WebsiteConstruct  # Adjust the import based on your project structure

class InfrastructureStackProps(StackProps):
    def __init__(self, ip_permit_list: list, project_name: str, model_endpoint_export_name_prefix: str, website_dist_path: str, **kwargs):
        super().__init__(**kwargs)
        self.ip_permit_list = ip_permit_list
        self.project_name = project_name
        self.model_endpoint_export_name_prefix = model_endpoint_export_name_prefix
        self.website_dist_path = website_dist_path

class InfrastructureStack(Stack):
    def __init__(self, scope: Construct, id: str, props: InfrastructureStackProps) -> None:
        super().__init__(scope, id, props)

        sage_maker_endpoint_arn = Fn.import_value(f"{props.model_endpoint_export_name_prefix}-{props.project_name}")
        sage_maker_endpoint_name = Fn.import_value(
            f"{props.model_endpoint_export_name_prefix}-Name-{props.project_name}"
        )

        api_construct = WebsiteApiConstruct(self, 'WebsiteAPIConstruct', {
            'ipCIDRBlocks': props.ip_permit_list,
            'sageMakeEndpointARN': sage_maker_endpoint_arn,
            'sageMakerEndpointName': sage_maker_endpoint_name,
        })

        WebsiteConstruct(self, 'WebsiteConstruct', {
            'websiteDistPath': props.website_dist_path,
            'api': api_construct.api,
        })