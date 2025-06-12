# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Timur Tsedik

import logging
import re
import os
import argparse

from dotenv import load_dotenv

from bitrix import BitrixFillInData
from jira import JiraFetchData


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),                            # консоль
        logging.FileHandler('migration.log', encoding='utf-8')  # файл
    ]
)

def ensureUser(in_bitrix: BitrixFillInData, in_email: str, in_name: str) -> int:
    bitrixId = in_bitrix.findBitrixUserByEmail(in_email)
    if bitrixId:
        logging.info(f"{in_email!r} already exists (ID={bitrixId})")
        return bitrixId
    first, *rest = in_name.split(maxsplit=1)
    last = rest[0] if rest else ""
    return in_bitrix.addBitrixUser({
        "email": in_email,
        "name": first,
        "lastName": last,
    })['id']

def mapUsers(jira: JiraFetchData) ->dict:
    userMap = {}
    for user in jira.fetchJiraUsers(''):
        userMap[user['key']] = user['email']
    assignees = jira.collectAssigneeKeys()
    # combine unique assignees with their emails
    for assignee in assignees:
        userMap[assignee[1]] = assignee[0]

    # Create NULL user for cases when assignee not specified
    userMap['Nobody'] = "nobody@example.com"

    return userMap

def migrateUsers(in_extraKeys: list, in_jira: JiraFetchData, in_bitrix: BitrixFillInData) -> dict:
    """Migrate Jira users to Bitrix24 portal users and return mapping of Jira key to Bitrix ID."""
    userMap, seen = {}, set()
    # Scan by prefix
    for letter in 'abcdefghijklmnopqrstuvwxyz':
        for user in in_jira.fetchJiraUsers(letter):
            if user['key'] in seen or not user['active']:
                continue
            seen.add(user['key'])
            email = user['email']
            name = user['displayName']
            bitrixId = ensureUser(in_bitrix, email, name)
            userMap[user['key']] = bitrixId

    # Handle assignees not covered by prefix scan
    for key in in_extraKeys:
        if key[1] in seen:
            continue
        seen.add(key[1])
        name = key[1]
        email = key[0]
        bitrixId = ensureUser(in_bitrix, email, name)
        userMap[key[1]] = bitrixId
    # Create NULL user for cases when assignee not specified
    email = "nobody@example.com"
    name = "Nobody"
    bitrixId = in_bitrix.findBitrixUserByEmail(email)
    if bitrixId:
        logging.info(f"User with email {email} already exists as ID {bitrixId}")
    else:
        user = {'active': True, 'displayName': name, 'email': email, 'key': name}
        bitrixId = in_bitrix.addBitrixUser(user)
        logging.info(f"Created Bitrix24 user {bitrixId} for Jira user {user['key']}")
    userMap[name] = bitrixId
    return userMap

def sanitizeMessage(in_msg: str) -> str:
    """Remove special/control characters from the message."""
    # Replace non-breaking spaces with normal spaces
    ret = in_msg.replace(' ', ' ')
    # Remove other control chars (0x00-0x1F and 0x7F)
    ret = re.sub(r'[\x00-\x1F\x7F]', '', ret)
    return ret

def migrateIssues(in_contactMap: dict, in_jira: JiraFetchData, in_bitrix: BitrixFillInData,
                  in_projectId: str = None, in_taskGroup: int = None):
    """Migrate Jira issues (tasks) into Bitrix24."""
    projects = in_jira.fetchJiraProjects()
    counter = 0
    for proj in projects:
        key = proj['key']
        if in_projectId and in_projectId == key:
            issues = in_jira.fetchJiraIssues(key)
            for issue in issues:
                taskId = in_bitrix.createBitrixTask(issue, in_contactMap, in_deleteIfExist=True, in_taskGroup=in_taskGroup)
                counter += 1
                logging.info(f"Issue # {counter}")
                # migrate comments if needed
                comments = in_jira.fetchComments(issue['key'])
                for c in comments:
                    if isinstance(taskId, dict):
                        taskId = taskId['task']['id']
                    body = sanitizeMessage(c.get('body'))
                    params = [taskId,
                         {'POST_MESSAGE': body,
                                'AUTHOR_ID': in_contactMap.get(c.get('author', {}).get('name'))}]
                    in_bitrix.callBitrixMethod('task.commentitem.add', params)
                    logging.info(f"params: {params}")


def main():
    load_dotenv()
    args = parse_args()
    jiraUrl = os.getenv('JIRA_URL')
    jiraUserName = os.getenv('JIRA_USER')
    jiraUserPass = os.getenv('JIRA_TOKEN')
    maxResults = int(os.getenv('MAX_RESULTS', '50'))
    webHook = os.getenv('BITRIX_WEBHOOK')

    jira = JiraFetchData(in_jiraUrl=jiraUrl, in_jiraPass=jiraUserPass, in_jiraUserName=jiraUserName, in_maxResults=maxResults)
    bitrix = BitrixFillInData(webHook)

    logging.info("Starting migration from Jira to Bitrix24...")

    if args.step in ('users', 'all'):
        assignees = jira.collectAssigneeKeys()
        userMap = migrateUsers(assignees, in_jira=jira, in_bitrix=bitrix)
        logging.info(f"user map: {userMap}")
    if args.step in ('issues', 'all'):
        userMap = mapUsers(jira)
        migrateIssues(userMap, in_projectId=args.project, in_taskGroup=args.group, in_jira=jira, in_bitrix=bitrix)
        logging.info("Migration completed.")


def parse_args():
    parser = argparse.ArgumentParser(
        description='Migrate Jira data to Bitrix24 portal.'
    )
    parser.add_argument(
        '--step',
        choices=['users', 'issues', 'all'],
        default='all',
        help='Which step to run: users, issues or all'
    )
    parser.add_argument(
        '--project',
        help='Jira project key to migrate (issues only)'
    )
    parser.add_argument(
        '--group',
        type=int,
        help='Bitrix24 workgroup ID for created tasks'
    )

    return parser.parse_args()

if __name__ == '__main__':
    main()