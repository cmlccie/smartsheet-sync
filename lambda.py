#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""SmartSheet Sync Lambda Function."""


from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *

import logging
import os
import sys
from base64 import b64decode

import boto3

import ssdbsync


__author__ = "Chris Lunsford"
__author_email__ = "chrlunsf@cisco.com"
__copyright__ = "Copyright (c) 2017 Cisco Systems, Inc."
__license__ = "MIT"


# Add vendor directory to module search path
parent_dir = os.path.abspath(os.path.dirname(__file__))
vendor_dir = os.path.join(parent_dir, 'vendor')
sys.path.append(vendor_dir)


# Constants
LOG_LEVEL = os.getenv('LOG_LEVEL')
ENCRYPTED_SMARTSHEET_ACCESS_TOKEN = os.getenv('ENCRYPTED_SMARTSHEET_ACCESS_TOKEN')
SHEET_ID = os.getenv('SHEET_ID')
COLUMN_TITLES_ID = '0'


# Initialize logging
logging.getLogger().setLevel(getattr(logging, LOG_LEVEL))
logging.getLogger(__name__).addHandler(logging.NullHandler())


# Initialize AWS Key Management System (KMS) interface
kms = boto3.client('kms')


# Initialize SmartSheet interface
smartsheet_access_token = kms.decrypt(
    CiphertextBlob=b64decode(ENCRYPTED_SMARTSHEET_ACCESS_TOKEN))['Plaintext']
smartsheet = ssdbsync.SmartSheetInterface(smartsheet_access_token)


# Initialize DynamoDB interface
dynamodb = ssdbsync.DynamoDBInterface()


# Helper functions
def enable_logging_to_console(log_level=logging.WARNING):
    """Enable console logging."""
    global console_handler
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        logging.Formatter('[%(levelname)-8s] %(name)s:  %(message)s'))
    root_logger.addHandler(console_handler)


# Core functions


def create_table():
    """Create the DynamoDB table."""
    logger.info("Creating a new DynamoDB table '{}'.".format(SHEET_ID))
    table = dynamodb.create_table(
        TableName=SHEET_ID,
        KeySchema=[
            {
                'AttributeName': 'id',
                'KeyType': 'HASH'
            },
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'id',
                'AttributeType': 'S'
            },
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': DEFAULT_READ_CAPACITY_UNITS,
            'WriteCapacityUnits': DEFAULT_WRITE_CAPACITY_UNITS
        }
    )
    # Wait until the table exists.
    table.meta.client.get_waiter('table_exists').wait(TableName=SHEET_ID)
    return table


def get_table():
    """Get the DynamoDB table."""
    logger.info("Getting the DynamoDB table '{}'.".format(SHEET_ID))
    if SHEET_ID not in [table.name for table in dynamodb.tables.all()]:
        logger.info("Table '{}' not found.".format(SHEET_ID))
        return create_table()
    return dynamodb.Table(SHEET_ID)


def update_table(table, data):
    logger.info("Begin batch table update.")
    with table.batch_writer() as batch:
        for data_row in data:
            logger.debug("Adding Item ID: {id}".format(**data_row))
            batch.put_item(Item=data_row)
    logger.info("Batch table update complete.")


# Main
def main():
    data = smartsheet.extract_data(SHEET_ID)
    update_table(table, data)
    return (sheet, data, table)


# AWS Lambda Function
def handler(event, context):
    main()
    return {"statusCode": 200}


if __name__ == "__main__":
    enable_logging_to_console(logging.INFO)
    test_smartsheet_connection()
    sheet, data, table = main()
