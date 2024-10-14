#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
from aws_cdk import App
from lib.infrastractureStack import InfrastractureStack
import json

with open('../../configuration/projectConfig.json') as config_file:
    project_config = json.load(config_file)

app = App()
InfrastractureStack(app, f'MLOpsInfrastractureStack-{project_config["projectName"]}', {
    'projectName': project_config['projectName'],
    'repoType': 'git' if project_config['repoType'] == 'git' else 'codecommit',
    'git': project_config['git'],
})

app.synth()
