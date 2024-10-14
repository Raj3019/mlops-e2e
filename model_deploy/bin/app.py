#!/usr/bin/env python
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os
from aws_cdk import App
from lib.modelDeploymentStack import ModelDeploymentStack  # Adjust the import based on your project structure

# Load project configuration
with open('../../configuration/projectConfig.json') as config_file:
    project_config = json.load(config_file)

app = App()

ModelDeploymentStack(app, f"Deployment-{project_config['projectName']}", **project_config)